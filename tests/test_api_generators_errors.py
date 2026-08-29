"""Tests for generator API error sanitization."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from meltr.api.endpoints import generators as generators_module


@pytest.fixture
def generator_client() -> TestClient:
    app = FastAPI()
    app.include_router(generators_module.router)

    engine = MagicMock()
    gen = MagicMock()
    gen.name = "gen-a"
    gen.state = MagicMock(value="ERROR")
    engine.get_all_generators.return_value = [gen]
    engine.restart_generator.side_effect = RuntimeError(
        "Generator gen-a loop failed to start: /secret/path/template.j2"
    )

    app.state.engine = engine
    return TestClient(app)


def test_restart_all_redacts_exception_message(generator_client: TestClient) -> None:
    response = generator_client.post("/api/generators/restart-all")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["results"][0]["success"] is False
    assert body["results"][0]["error"] == "Restart generator gen-a failed"
    assert "template.j2" not in body["results"][0]["error"]
