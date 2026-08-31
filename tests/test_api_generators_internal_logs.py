"""API tests: list_generators with InternalLogGenerator loaded."""

from fastapi.testclient import TestClient

from meltr.api.server import APIServer
from meltr.core.config import AuthConfig, OutputDefinition, create_default_config
from meltr.core.engine import Engine
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME
from meltr.entities.registry import EntityRegistry


def _enable_internal_logs(config, output_name: str = "stdout") -> None:
    config.outputs.definitions.append(
        OutputDefinition(name=output_name, type="console", stream="stdout", format="json")
    )
    for gen in config.generators:
        if gen.name == INTERNAL_LOGS_GENERATOR_NAME:
            gen.enabled = True
            gen.outputs = [output_name]
            return
    raise AssertionError("default config missing reserved internal-logs generator")


def test_list_generators_with_internal_logs_enabled(tmp_path, monkeypatch) -> None:
    """GET /api/generators succeeds when internal-logs generator is loaded."""
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("LOGFORGE_API_KEY", raising=False)

    config = create_default_config(tmp_path)
    config.api.auth = AuthConfig(enabled=False, key=None)
    _enable_internal_logs(config)

    registry = EntityRegistry(config)
    engine = Engine(config, registry)

    server = APIServer(config)
    server.app.state.registry = registry
    server.app.state.engine = engine

    client = TestClient(server.app)
    response = client.get("/api/generators")

    assert response.status_code == 200
    body = response.json()
    assert "generators" in body
    names = {item["name"] for item in body["generators"]}
    assert INTERNAL_LOGS_GENERATOR_NAME in names

    internal = next(g for g in body["generators"] if g["name"] == INTERNAL_LOGS_GENERATOR_NAME)
    assert internal["template"] == "_internal"
    assert internal["enabled"] is True
    assert internal["vendor"] is None
    assert internal["product"] is None
    assert internal["data_source"] is None
