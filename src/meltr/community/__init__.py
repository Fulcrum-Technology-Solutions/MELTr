"""Community Integration module."""

from meltr.community.client import (
    CommunityAPIClient,
    CommunityAPIError,
    CommunityAPINotFoundError,
    CommunityAPIRateLimitError,
)
from meltr.community.package import (
    PackageError,
    PackageInstallError,
    PackageValidationError,
    download_and_install_product,
    download_and_install_vendor,
    extract_mtb_package,
    get_local_collection_version,
    install_package,
    validate_package_structure,
)
from meltr.community.updates import find_stale_updates
from meltr.community.version import (
    compare_versions,
    format_version_status,
    is_update_available,
)

__all__ = [
    # Client
    "CommunityAPIClient",
    "CommunityAPIError",
    "CommunityAPINotFoundError",
    "CommunityAPIRateLimitError",
    # Package
    "PackageError",
    "PackageInstallError",
    "PackageValidationError",
    "download_and_install_vendor",
    "download_and_install_product",
    "extract_mtb_package",
    "get_local_collection_version",
    "install_package",
    "validate_package_structure",
    # Updates
    "find_stale_updates",
    # Version
    "compare_versions",
    "format_version_status",
    "is_update_available",
]
