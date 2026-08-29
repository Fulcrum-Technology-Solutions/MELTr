"""Integration tests for multi-template pipelines."""

import json
import shutil
import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from meltr.api.server import APIServer
from meltr.core.config import (
    AuthConfig,
    OutputDefinition,
    PipelineConfig,
    PipelineStreamConfig,
    ScheduleConfig,
    create_default_config,
)
from meltr.core.engine import Engine
from meltr.core.generator import GeneratorState
from meltr.core.pipeline import Pipeline
from meltr.entities.registry import EntityRegistry

FIXTURES = Path(__file__).parent / "fixtures" / "templates"
SAMPLE_ENTITIES = Path(__file__).parent.parent / "src" / "meltr" / "data" / "entities.sample.yaml"


def _install_two_stream_templates(base: Path) -> tuple[str, str]:
    """Install two high-rate templates under default/ layout."""
    templates_root = base / "templates"
    default_root = templates_root / "default"
    events_dir = default_root / "testvendor" / "testproduct" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)

    (default_root / "testvendor" / "testproduct" / "collection.json").write_text(
        json.dumps({"version": "1.0.0", "templates": ["events/stream_a", "events/stream_b"]}),
        encoding="utf-8",
    )

    meta_base = (
        "vendor: testvendor\n"
        "product: testproduct\n"
        "data_source: events\n"
        "description: Pipeline test template\n"
        "format: JSON\n"
        "is_generator: true\n"
        "base_frequency: 360000\n"
    )

    for name, marker in [("stream_a", "stream-a"), ("stream_b", "stream-b")]:
        (events_dir / f"{name}.j2").write_text(
            f'{{{{ {{"stream": "{marker}", "org": registry.get_organization().name}} | tojson }}}}\n',
            encoding="utf-8",
        )
        (events_dir / f"{name}.meta.yaml").write_text(meta_base, encoding="utf-8")

    return (
        "testvendor/testproduct/events/stream_a",
        "testvendor/testproduct/events/stream_b",
    )


def _setup_home(tmp_path: Path, monkeypatch, *, file_a: Path, file_b: Path) -> tuple:
    """Create MELTR_HOME with entities, templates, and pipeline config."""
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    stream_a, stream_b = _install_two_stream_templates(tmp_path)
    shutil.copy(SAMPLE_ENTITIES, tmp_path / "entities.yaml")

    config = create_default_config(tmp_path)
    config.outputs.definitions = [
        OutputDefinition(name="file-a", type="file", path=str(file_a)),
        OutputDefinition(name="file-b", type="file", path=str(file_b)),
    ]
    config.pipelines = [
        PipelineConfig(
            name="lab-pipeline",
            enabled=True,
            outputs=["file-a", "file-b"],
            schedule=ScheduleConfig(mode="burst", count=50, duration="30s"),
            streams=[
                PipelineStreamConfig(template=stream_a, weight=1.0),
                PipelineStreamConfig(template=stream_b, weight=1.0),
            ],
        )
    ]

    config_path = tmp_path / "config.yaml"
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(config.model_dump(mode="json"), handle, default_flow_style=False)

    registry = EntityRegistry(config)
    engine = Engine(config, registry)
    return config, registry, engine, stream_a, stream_b


def test_pipeline_two_streams_write_to_file_outputs(tmp_path, monkeypatch) -> None:
    """Pipeline with two streams should emit to both configured file outputs."""
    file_a = tmp_path / "out-a.log"
    file_b = tmp_path / "out-b.log"
    _config, _registry, engine, _stream_a, _stream_b = _setup_home(
        tmp_path, monkeypatch, file_a=file_a, file_b=file_b
    )

    try:
        engine.start_pipeline("lab-pipeline")

        deadline = time.time() + 15.0
        while time.time() < deadline:
            if file_a.exists() and file_b.exists():
                if file_a.read_text().strip() and file_b.read_text().strip():
                    break
            time.sleep(0.1)
        else:
            pytest.fail("timed out waiting for pipeline file outputs")

        assert "stream-a" in file_a.read_text() or "stream-b" in file_a.read_text()
        assert "stream-a" in file_b.read_text() or "stream-b" in file_b.read_text()
    finally:
        engine.stop_pipeline("lab-pipeline")
        engine.shutdown()


def test_pipeline_name_collision_with_generator_rejected(tmp_path, monkeypatch) -> None:
    """Pipeline names must not collide with standalone generator names."""
    file_a = tmp_path / "out-a.log"
    file_b = tmp_path / "out-b.log"
    config, registry, _engine, stream_a, _stream_b = _setup_home(
        tmp_path, monkeypatch, file_a=file_a, file_b=file_b
    )

    from meltr.core.config import GeneratorConfig

    config.generators = [
        GeneratorConfig(
            name="lab-pipeline",
            template=stream_a,
            enabled=False,
            outputs=["file-a"],
        )
    ]
    engine = Engine(config, registry)

    assert "lab-pipeline" not in engine._pipelines
    child_names = [name for name in engine._generators if name.startswith("lab-pipeline::")]
    assert child_names == []


def test_list_pipelines_returns_child_generators(tmp_path, monkeypatch) -> None:
    file_a = tmp_path / "out-a.log"
    file_b = tmp_path / "out-b.log"
    _config, _registry, engine, _stream_a, _stream_b = _setup_home(
        tmp_path, monkeypatch, file_a=file_a, file_b=file_b
    )

    try:
        pipelines = engine.list_pipelines()
        assert len(pipelines) == 1
        pipeline = pipelines[0]
        assert pipeline["name"] == "lab-pipeline"
        assert len(pipeline["streams"]) == 2
        assert pipeline["state"] == GeneratorState.STOPPED.value
    finally:
        engine.shutdown()


@pytest.fixture
def pipeline_api_client(tmp_path, monkeypatch) -> TestClient:
    file_a = tmp_path / "api-out-a.log"
    file_b = tmp_path / "api-out-b.log"
    config, registry, engine, _stream_a, _stream_b = _setup_home(
        tmp_path, monkeypatch, file_a=file_a, file_b=file_b
    )

    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    config.api.auth = AuthConfig(enabled=False, key=None)

    server = APIServer(config)
    server.app.state.engine = engine
    server.app.state.registry = registry
    return TestClient(server.app)


def test_api_pipelines_list_start_stop(pipeline_api_client: TestClient) -> None:
    list_resp = pipeline_api_client.get("/api/pipelines")
    assert list_resp.status_code == 200
    assert list_resp.json()["pipelines"][0]["name"] == "lab-pipeline"

    start_resp = pipeline_api_client.post("/api/pipelines/lab-pipeline/start", json={})
    assert start_resp.status_code == 200
    assert start_resp.json()["state"] in {"RUNNING", "STARTING"}

    stop_resp = pipeline_api_client.post("/api/pipelines/lab-pipeline/stop", json={})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["state"] == "STOPPED"


def test_child_generator_name_format() -> None:
    assert Pipeline.child_generator_name("lab", 0) == "lab::0"
    assert Pipeline.child_generator_name("lab", 1) == "lab::1"


def test_reload_config_preserves_pipeline_child_generators(tmp_path, monkeypatch) -> None:
    """reload_config must not tear down pipeline child generators."""
    file_a = tmp_path / "out-a.log"
    file_b = tmp_path / "out-b.log"
    config, registry, engine, _stream_a, _stream_b = _setup_home(
        tmp_path, monkeypatch, file_a=file_a, file_b=file_b
    )

    try:
        child_names_before = sorted(
            name for name in engine._generators if name.startswith("lab-pipeline::")
        )
        assert child_names_before == ["lab-pipeline::0", "lab-pipeline::1"]

        engine.start_pipeline("lab-pipeline")

        results = engine.reload_config(config.model_copy(deep=True))

        child_names_after = sorted(
            name for name in engine._generators if name.startswith("lab-pipeline::")
        )
        assert child_names_after == child_names_before
        assert "lab-pipeline" in engine._pipelines
        assert not any(name in results["removed"] for name in child_names_before)

        status = engine.get_pipeline_status("lab-pipeline")
        assert status["name"] == "lab-pipeline"
        assert len(status["streams"]) == 2
    finally:
        engine.shutdown()


def test_pipeline_child_name_collision_rejected_atomically(tmp_path, monkeypatch) -> None:
    """Pipeline load must fail atomically when a child name already exists."""
    file_a = tmp_path / "out-a.log"
    file_b = tmp_path / "out-b.log"
    config, registry, engine, stream_a, _stream_b = _setup_home(
        tmp_path, monkeypatch, file_a=file_a, file_b=file_b
    )
    engine.shutdown()

    from meltr.core.config import GeneratorConfig

    config.generators = [
        GeneratorConfig(
            name="lab-pipeline::0",
            template=stream_a,
            enabled=False,
            outputs=["file-a"],
        )
    ]
    engine = Engine(config, registry)

    try:
        assert "lab-pipeline" not in engine._pipelines
        assert "lab-pipeline::0" in engine._generators
        assert "lab-pipeline::1" not in engine._generators
    finally:
        engine.shutdown()
