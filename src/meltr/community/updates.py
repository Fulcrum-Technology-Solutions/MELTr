"""Community template update detection helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from meltr.community.client import (
    CommunityAPIClient,
    CommunityAPIError,
    CommunityAPINotFoundError,
)
from meltr.community.package import get_local_collection_version
from meltr.community.version import is_update_available


def iter_installed_products(templates_path: Path) -> Iterator[tuple[str, str]]:
    """Yield (vendor_id, product_id) for locally installed community products."""
    default_path = templates_path / "default"
    if not default_path.is_dir():
        return

    for vendor_dir in sorted(default_path.iterdir()):
        if not vendor_dir.is_dir() or vendor_dir.name.startswith("."):
            continue
        for product_dir in sorted(vendor_dir.iterdir()):
            if not product_dir.is_dir() or product_dir.name.startswith("."):
                continue
            if (product_dir / "collection.json").is_file():
                yield vendor_dir.name, product_dir.name


def get_remote_collection_version(
    client: CommunityAPIClient,
    vendor_id: str,
    product_id: str,
    cache: dict[tuple[str, str], str | None] | None = None,
    *,
    soft_fail: bool = False,
) -> str | None:
    """Fetch remote collection version, optionally using a per-request cache.

    When ``soft_fail`` is True, registry errors return ``None`` instead of raising.
    """
    key = (vendor_id, product_id)
    if cache is not None and key in cache:
        return cache[key]

    remote_version: str | None = None
    try:
        product_info = client.get_product_detail(vendor_id, product_id)
        raw = product_info.get("collection_version")
        if raw is not None:
            remote_version = str(raw)
    except CommunityAPINotFoundError:
        remote_version = None
    except CommunityAPIError:
        if soft_fail:
            remote_version = None
        else:
            raise

    if cache is not None:
        cache[key] = remote_version
    return remote_version


def find_stale_updates(
    client: CommunityAPIClient,
    templates_path: Path,
) -> list[dict[str, str | None]]:
    """Return installed products whose remote collection version is newer."""
    stale: list[dict[str, str | None]] = []

    for vendor_id, product_id in iter_installed_products(templates_path):
        local_version = get_local_collection_version(vendor_id, product_id, templates_path)
        remote_version = get_remote_collection_version(client, vendor_id, product_id)
        if remote_version and is_update_available(local_version, remote_version):
            stale.append(
                {
                    "vendor_id": vendor_id,
                    "product_id": product_id,
                    "local_version": local_version,
                    "remote_version": remote_version,
                }
            )

    stale.sort(key=lambda row: (row["vendor_id"] or "", row["product_id"] or ""))
    return stale


class ProductVersionLookup:
    """Resolve local and remote collection versions for template API responses."""

    def __init__(
        self,
        templates_path: Path,
        client: CommunityAPIClient | None = None,
    ) -> None:
        self.templates_path = templates_path
        self.client = client
        self._remote_cache: dict[tuple[str, str], str | None] = {}

    def local_version(self, vendor_id: str, product_id: str) -> str | None:
        return get_local_collection_version(vendor_id, product_id, self.templates_path)

    def remote_version(self, vendor_id: str, product_id: str) -> str | None:
        if self.client is None:
            return None
        return get_remote_collection_version(
            self.client,
            vendor_id,
            product_id,
            cache=self._remote_cache,
            soft_fail=True,
        )

    def for_product(self, vendor_id: str, product_id: str) -> tuple[str | None, str | None]:
        return self.local_version(vendor_id, product_id), self.remote_version(vendor_id, product_id)
