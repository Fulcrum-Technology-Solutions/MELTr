"""Package download, extraction, and installation utilities."""

import json
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import yaml

from meltr.community.client import CommunityAPIClient
from meltr.core.paths import get_backups_path
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


class PackageError(Exception):
    """Base exception for package operations."""

    pass


class PackageValidationError(PackageError):
    """Package validation failed."""

    pass


def _safe_extractall(tar: tarfile.TarFile, dest: Path) -> None:
    """Extract tar members only under ``dest`` (blocks path traversal).

    Validates each member resolves inside ``dest``. On Python 3.12+ also
    passes ``filter='data'`` to ``extractall``.
    """
    dest = dest.resolve()
    for member in tar.getmembers():
        # Reject absolute paths and parent-directory escapes before resolve()
        name = member.name.replace("\\", "/")
        if name.startswith("/") or name.startswith("../") or "/../" in f"/{name}/":
            raise PackageError(f"Unsafe path in archive: {member.name!r}")
        target = (dest / member.name).resolve()
        try:
            target.relative_to(dest)
        except ValueError as e:
            raise PackageError(f"Unsafe path in archive: {member.name!r}") from e

    extract_kwargs: dict = {}
    if sys.version_info >= (3, 12):
        extract_kwargs["filter"] = "data"
    tar.extractall(dest, **extract_kwargs)


class PackageInstallError(PackageError):
    """Package installation failed."""

    pass


def extract_forge_package(
    package_path: Path,
    extract_to: Path,
    validate: bool = True,
) -> Path:
    """Extract .forge package (tar.gz) to target directory.

    Args:
        package_path: Path to .forge package file
        extract_to: Directory to extract to
        validate: Whether to validate package structure

    Returns:
        Path to extracted vendor directory

    Raises:
        PackageError: If extraction fails
        PackageValidationError: If validation fails
    """
    if not package_path.exists():
        raise PackageError(f"Package file not found: {package_path}")

    logger.info(f"Extracting package: {package_path}")

    try:
        # Open tar.gz archive
        with tarfile.open(package_path, "r:gz") as tar:
            extract_to.mkdir(parents=True, exist_ok=True)
            _safe_extractall(tar, extract_to)

        # Find vendor directory (should be first/only top-level directory)
        extracted_items = list(extract_to.iterdir())

        if not extracted_items:
            raise PackageValidationError("Package is empty")

        vendor_dir = None
        for item in extracted_items:
            if item.is_dir():
                vendor_dir = item
                break

        if not vendor_dir:
            raise PackageValidationError("No vendor directory found in package")

        # Validate vendor.yaml exists
        if validate:
            vendor_yaml = vendor_dir / "vendor.yaml"
            if not vendor_yaml.exists():
                logger.warning(f"vendor.yaml not found in {vendor_dir}, but continuing")
            else:
                logger.debug(f"Found vendor.yaml: {vendor_yaml}")

        logger.info(f"Extracted package to: {vendor_dir}")
        return vendor_dir

    except tarfile.TarError as e:
        raise PackageError(f"Failed to extract package: {e}") from e
    except Exception as e:
        raise PackageError(f"Unexpected error extracting package: {e}") from e


def validate_package_structure(vendor_dir: Path) -> bool:
    """Validate package structure matches expected format.

    Args:
        vendor_dir: Path to vendor directory from extracted package

    Returns:
        True if valid, raises PackageValidationError if not
    """
    # Check vendor.yaml exists
    vendor_yaml = vendor_dir / "vendor.yaml"
    if not vendor_yaml.exists():
        raise PackageValidationError("vendor.yaml not found")

    # Check vendor.yaml is valid YAML
    try:
        with open(vendor_yaml) as f:
            vendor_data = yaml.safe_load(f)
            if not isinstance(vendor_data, dict):
                raise PackageValidationError("vendor.yaml is not a valid YAML dictionary")
    except yaml.YAMLError as e:
        raise PackageValidationError(f"Invalid vendor.yaml: {e}") from e

    # Check for at least one product directory
    product_dirs = [d for d in vendor_dir.iterdir() if d.is_dir() and d.name != "__pycache__"]
    if not product_dirs:
        raise PackageValidationError("No product directories found in package")

    logger.debug(f"Package structure validated: {len(product_dirs)} products found")
    return True


def backup_vendor_directory(
    vendor_dir: Path,
    vendor_id: str,
    backup_count: int = 5,
) -> Path:
    """Backup vendor directory to backups location with rotation.

    Args:
        vendor_dir: Path to vendor directory to backup
        vendor_id: Vendor identifier
        backup_count: Number of backups to keep

    Returns:
        Path to backup directory

    Raises:
        PackageError: If backup fails
    """
    backups_path = get_backups_path()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{vendor_id}-{timestamp}"
    backup_dir = backups_path / backup_name

    try:
        # Create backup
        logger.info(f"Creating backup: {backup_dir}")
        shutil.copytree(vendor_dir, backup_dir)

        # Get all backups for this vendor (sorted by name, which includes timestamp)
        vendor_backups = sorted(
            [
                d
                for d in backups_path.iterdir()
                if d.is_dir() and d.name.startswith(f"{vendor_id}-")
            ],
            key=lambda p: p.name,
            reverse=True,
        )

        # Remove oldest backups if we exceed backup_count
        if len(vendor_backups) > backup_count:
            for old_backup in vendor_backups[backup_count:]:
                logger.debug(f"Removing old backup: {old_backup}")
                # Try to compress before removing
                try:
                    backup_tar = old_backup.with_suffix(".tar.gz")
                    with tarfile.open(backup_tar, "w:gz") as tar:
                        tar.add(old_backup, arcname=old_backup.name)
                    shutil.rmtree(old_backup)
                    logger.debug(f"Compressed old backup to: {backup_tar}")
                except Exception as e:
                    logger.warning(
                        f"Failed to compress backup {old_backup}, removing directly: {e}"
                    )
                    shutil.rmtree(old_backup, ignore_errors=True)

        logger.info(f"Backup created successfully: {backup_dir}")
        return backup_dir

    except Exception as e:
        raise PackageError(f"Failed to create backup: {e}") from e


def install_package(
    vendor_dir: Path,
    target_dir: Path,
    vendor_id: str | None = None,
    overwrite: bool = False,
    backup_count: int = 5,
) -> Path:
    """Install extracted package to templates directory.

    Args:
        vendor_dir: Path to extracted vendor directory
        target_dir: Target templates directory (typically default/)
        vendor_id: Expected vendor ID (for validation)
        overwrite: Whether to overwrite existing vendor directory
        backup_count: Number of backups to keep (default: 5)

    Returns:
        Path to installed vendor directory

    Raises:
        PackageInstallError: If installation fails
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine vendor ID from directory name if not provided
    if vendor_id is None:
        vendor_id = vendor_dir.name

    installed_dir = target_dir / vendor_id

    # Check if vendor already exists
    if installed_dir.exists() and not overwrite:
        raise PackageInstallError(
            f"Vendor directory already exists: {installed_dir}. "
            "Use overwrite=True to replace it."
        )

    # Backup existing directory if overwriting
    if installed_dir.exists() and overwrite:
        try:
            backup_vendor_directory(installed_dir, vendor_id, backup_count)
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}. Continuing with installation...")
        # Remove old directory after backup
        shutil.rmtree(installed_dir)

    try:
        # Copy vendor directory to target
        logger.info(f"Installing vendor package to: {installed_dir}")
        shutil.copytree(vendor_dir, installed_dir, dirs_exist_ok=True)

        logger.info(f"Package installed successfully: {installed_dir}")
        return installed_dir

    except shutil.Error as e:
        raise PackageInstallError(f"Failed to copy vendor directory: {e}") from e
    except Exception as e:
        raise PackageInstallError(f"Unexpected error installing package: {e}") from e


def get_local_collection_version(
    vendor_id: str,
    product_id: str,
    templates_path: Path,
) -> str | None:
    """Get collection version from local template installation.

    Args:
        vendor_id: Vendor identifier
        product_id: Product identifier
        templates_path: Base templates path (containing default/ or custom/)

    Returns:
        Collection version string or None if not found
    """
    # Try default/ first
    for location in ["default", "custom"]:
        product_dir = templates_path / location / vendor_id / product_id
        collection_json = product_dir / "collection.json"

        if collection_json.exists():
            try:
                with open(collection_json) as f:
                    collection_data = json.load(f)
                    version = collection_data.get("version")
                    if version:
                        return str(version)
            except (OSError, json.JSONDecodeError) as e:
                logger.debug(f"Failed to read collection.json: {e}")
                continue

    return None


def download_and_install_product(
    client: CommunityAPIClient,
    vendor_id: str,
    product_id: str,
    target_dir: Path,
    temp_dir: Path | None = None,
    overwrite: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """Download vendor package and install only specified product.

    This maintains collection.json integrity since products are
    self-contained units with their own collection.json.

    Args:
        client: CommunityAPIClient instance
        vendor_id: Vendor identifier
        product_id: Product identifier
        target_dir: Target templates directory (typically default/)
        temp_dir: Temporary directory for downloads (None = system temp)
        overwrite: Whether to overwrite existing installation
        progress_callback: Optional callback for download progress

    Returns:
        Path to installed product directory

    Raises:
        CommunityAPIError: If download fails
        PackageError: If extraction/installation fails
    """
    # Create temporary directory for download if not provided
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="meltr-product-"))
        cleanup_temp = True
    else:
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        cleanup_temp = False

    package_path = temp_dir / f"{vendor_id}.forge"

    try:
        # Download vendor package (we need it to extract the product)
        logger.info(f"Downloading vendor package to extract product '{product_id}'")
        client.download_vendor_package(vendor_id, package_path, progress_callback=progress_callback)

        # Extract package
        extract_to = temp_dir / "extracted"
        vendor_dir = extract_forge_package(package_path, extract_to, validate=False)

        # Find product in extracted vendor directory
        product_source = vendor_dir / product_id
        if not product_source.exists():
            # List available products for better error message
            available_products = [
                d.name for d in vendor_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
            ]
            raise PackageError(
                f"Product '{product_id}' not found in vendor '{vendor_id}' package. "
                f"Available products: {', '.join(available_products) if available_products else 'none'}"
            )

        # Validate product has collection.json
        collection_json = product_source / "collection.json"
        if not collection_json.exists():
            raise PackageValidationError(
                f"Product '{product_id}' missing collection.json - invalid product structure"
            )

        # Install product to target
        target_vendor_dir = target_dir / vendor_id
        target_vendor_dir.mkdir(parents=True, exist_ok=True)

        target_product_dir = target_vendor_dir / product_id

        if target_product_dir.exists() and not overwrite:
            raise PackageInstallError(
                f"Product already installed: {target_product_dir}. "
                "Use --overwrite to replace it."
            )

        if target_product_dir.exists() and overwrite:
            logger.info(f"Overwriting existing product: {target_product_dir}")
            shutil.rmtree(target_product_dir)

        # Copy vendor.meta.yaml if it doesn't exist (always ensure it's present for product installs)
        vendor_meta_source = vendor_dir / "vendor.meta.yaml"
        vendor_meta_target = target_vendor_dir / "vendor.meta.yaml"

        if vendor_meta_source.exists():
            if not vendor_meta_target.exists():
                logger.info(f"Copying vendor.meta.yaml to: {vendor_meta_target}")
                shutil.copy2(vendor_meta_source, vendor_meta_target)
            elif overwrite:
                # Update vendor.meta.yaml if overwriting (fresh install)
                logger.info("Updating vendor.meta.yaml (overwrite mode)")
                shutil.copy2(vendor_meta_source, vendor_meta_target)
            else:
                logger.debug("vendor.meta.yaml already exists, preserving existing version")
        else:
            logger.warning("vendor.meta.yaml not found in vendor package, skipping")

        # Copy product directory
        logger.info(f"Installing product '{product_id}' to: {target_product_dir}")
        shutil.copytree(product_source, target_product_dir)

        logger.info(f"Product installed successfully: {target_product_dir}")
        return target_product_dir

    finally:
        # Cleanup temporary files
        if cleanup_temp and temp_dir.exists():
            logger.debug(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)


def download_and_install_vendor(
    client: CommunityAPIClient,
    vendor_id: str,
    target_dir: Path,
    temp_dir: Path | None = None,
    overwrite: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
    backup_count: int = 5,
) -> Path:
    """Download vendor package and install it.

    Args:
        client: CommunityAPIClient instance
        vendor_id: Vendor identifier
        target_dir: Target templates directory (typically default/)
        temp_dir: Temporary directory for downloads (None = system temp)
        overwrite: Whether to overwrite existing installation
        progress_callback: Optional callback for download progress
        backup_count: Number of backups to keep (default: 5)

    Returns:
        Path to installed vendor directory

    Raises:
        CommunityAPIError: If download fails
        PackageError: If extraction/installation fails
    """
    # Create temporary directory for download if not provided
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="meltr-package-"))
        cleanup_temp = True
    else:
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        cleanup_temp = False

    package_path = temp_dir / f"{vendor_id}.forge"

    try:
        # Download package
        client.download_vendor_package(vendor_id, package_path, progress_callback=progress_callback)

        # Extract package
        extract_to = temp_dir / "extracted"
        vendor_dir = extract_forge_package(package_path, extract_to, validate=True)

        # Validate package structure
        validate_package_structure(vendor_dir)

        # Install package
        installed_dir = install_package(
            vendor_dir,
            target_dir,
            vendor_id=vendor_id,
            overwrite=overwrite,
            backup_count=backup_count,
        )

        return installed_dir

    finally:
        # Cleanup temporary files
        if cleanup_temp and temp_dir.exists():
            logger.debug(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
