"""Community Integration module."""

from logforge.community.client import (
    CommunityAPIClient,
    CommunityAPIError,
    CommunityAPINotFoundError,
    CommunityAPIRateLimitError,
)
from logforge.community.package import (
    PackageError,
    PackageInstallError,
    PackageValidationError,
    download_and_install_vendor,
    download_and_install_product,
    extract_forge_package,
    get_local_collection_version,
    install_package,
    validate_package_structure,
)
from logforge.community.version import (
    compare_versions,
    format_version_status,
    is_update_available,
)

__all__ = [
    # Client
    'CommunityAPIClient',
    'CommunityAPIError',
    'CommunityAPINotFoundError',
    'CommunityAPIRateLimitError',
    # Package
    'PackageError',
    'PackageInstallError',
    'PackageValidationError',
    'download_and_install_vendor',
    'download_and_install_product',
    'extract_forge_package',
    'get_local_collection_version',
    'install_package',
    'validate_package_structure',
    # Version
    'compare_versions',
    'format_version_status',
    'is_update_available',
]
