import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from meltr import __version__
from meltr.core.paths import get_logforge_home
from meltr.utils.logging import get_logger

logger = get_logger(__name__)


def telemetry_enabled() -> bool:
    """
    Opt-out switch for CLI telemetry.

    - MELTR_TELEMETRY=0 / false disables (LOGFORGE_TELEMETRY still accepted)
    """
    v = (os.getenv("MELTR_TELEMETRY") or os.getenv("LOGFORGE_TELEMETRY") or "").strip().lower()
    if v in {"0", "false", "no", "off"}:
        return False
    return True


def _telemetry_state_path(home: Path | None = None) -> Path:
    if home is None:
        home = get_logforge_home()
    return home / "telemetry.json"


def get_actor_id(home: Path | None = None) -> str:
    """
    Anonymous stable client identifier stored under MELTR_HOME.
    """
    path = _telemetry_state_path(home)
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            actor_id = data.get("actor_id")
            if isinstance(actor_id, str) and actor_id.strip():
                return actor_id.strip()
    except Exception:
        # If file is corrupt, regenerate below.
        pass

    actor_id = str(uuid.uuid4())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"actor_id": actor_id}, indent=2) + "\n", encoding="utf-8")
    except Exception:
        # Non-fatal: still return ephemeral id
        logger.debug("Failed writing telemetry.json", exc_info=True)
    return actor_id


@dataclass(frozen=True)
class TelemetryEvent:
    event_type: str
    vendor_id: str | None = None
    product_id: str | None = None
    data_source_id: str | None = None
    template_id: str | None = None
    collection_version: str | None = None
    properties: dict[str, Any] | None = None


class TelemetryClient:
    def __init__(self, base_api_url: str) -> None:
        self.base_api_url = base_api_url.rstrip("/")

    @property
    def ingest_url(self) -> str:
        # Templates-UI: POST /api/v1/telemetry/events
        return f"{self.base_api_url}/telemetry/events"

    def post_events(self, *, actor_id: str, events: list[TelemetryEvent]) -> None:
        if not telemetry_enabled():
            return

        payload = {
            "actor_id": actor_id,
            "events": [
                {
                    "event_type": e.event_type,
                    "vendor_id": e.vendor_id,
                    "product_id": e.product_id,
                    "data_source_id": e.data_source_id,
                    "template_id": e.template_id,
                    "collection_version": e.collection_version,
                    "app_version": __version__,
                    "properties": e.properties or {},
                }
                for e in events
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "X-MELTr-Client": "cli",
            "X-MELTr-Actor-Id": actor_id,
            "User-Agent": f"MELTr/{__version__}",
        }

        try:
            resp = requests.post(self.ingest_url, json=payload, headers=headers, timeout=5)
            # Don’t fail installs on telemetry failures.
            if resp.status_code >= 400:
                logger.debug("Telemetry ingest failed: %s %s", resp.status_code, resp.text[:500])
        except Exception:
            logger.debug("Telemetry ingest request failed", exc_info=True)
