"""Engine reload tests for output-definition driven generator recreation."""

from meltr.core.config import GeneratorConfig, OutputDefinition, create_default_config
from meltr.core.engine import Engine
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME
from meltr.entities.registry import EntityRegistry
from meltr.templates.cache import TemplateCache


def test_engine_reload_updates_generator_when_output_definition_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    # Bypass template discovery/validation (engine only checks truthiness).
    monkeypatch.setattr(TemplateCache, "get_template", lambda *a, **k: object())

    config = create_default_config(tmp_path)
    config.outputs.definitions = [
        OutputDefinition(
            name="http1",
            type="http",
            url="http://old.example/v1/events",
            method="POST",
            headers={"Authorization": "Bearer old"},
            include_metadata=False,
            buffer_overflow_policy="drop_newest",
        )
    ]
    config.generators = [
        GeneratorConfig(
            name="gen1",
            template="vendor/prod/ds/template",
            enabled=False,
            outputs=["http1"],
        )
    ]

    registry = EntityRegistry(config)
    engine = Engine(config, registry)

    gen = engine._generators["gen1"]
    assert gen.output_handlers[0].url == "http://old.example/v1/events"

    new_config = config.model_copy(deep=True)
    new_config.outputs.definitions[0] = new_config.outputs.definitions[0].model_copy(
        update={"url": "http://new.example/v1/events"}
    )

    engine.reload_config(new_config)

    gen_after = engine._generators["gen1"]
    assert gen_after.output_handlers[0].url == "http://new.example/v1/events"


def test_engine_reload_updates_internal_logs_when_output_definition_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    config = create_default_config(tmp_path)
    config.outputs.definitions = [
        OutputDefinition(
            name="http1",
            type="http",
            url="http://old.example/v1/events",
            method="POST",
            headers={"Authorization": "Bearer old"},
            include_metadata=False,
            buffer_overflow_policy="drop_newest",
        )
    ]
    for gen in config.generators:
        if gen.name == INTERNAL_LOGS_GENERATOR_NAME:
            gen.enabled = True
            gen.outputs = ["http1"]

    registry = EntityRegistry(config)
    engine = Engine(config, registry)

    internal = engine._generators[INTERNAL_LOGS_GENERATOR_NAME]
    assert internal.output_handlers[0].url == "http://old.example/v1/events"

    new_config = config.model_copy(deep=True)
    new_config.outputs.definitions[0] = new_config.outputs.definitions[0].model_copy(
        update={"url": "http://new.example/v1/events"}
    )

    engine.reload_config(new_config)

    internal_after = engine._generators[INTERNAL_LOGS_GENERATOR_NAME]
    assert internal_after.output_handlers[0].url == "http://new.example/v1/events"
