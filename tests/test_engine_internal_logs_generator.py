"""Engine tests: internal-logs reserved generator from generators list."""

from meltr.core.config import (
    INTERNAL_LOGS_TEMPLATE_SENTINEL,
    OutputDefinition,
    create_default_config,
)
from meltr.core.engine import Engine
from meltr.core.generator import Generator
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME, InternalLogGenerator
from meltr.entities.registry import EntityRegistry
from meltr.templates.cache import TemplateCache


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


def test_enabled_internal_logs_uses_internal_generator(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    config = create_default_config(tmp_path)
    _enable_internal_logs(config)

    registry = EntityRegistry(config)
    engine = Engine(config, registry)

    gen = engine._generators[INTERNAL_LOGS_GENERATOR_NAME]
    assert isinstance(gen, InternalLogGenerator)
    assert not isinstance(gen, Generator)
    assert gen.output_handlers[0].name == "stdout"


def test_disabled_internal_logs_not_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    config = create_default_config(tmp_path)
    internal = next(g for g in config.generators if g.name == INTERNAL_LOGS_GENERATOR_NAME)
    assert internal.enabled is False
    assert internal.template == INTERNAL_LOGS_TEMPLATE_SENTINEL

    registry = EntityRegistry(config)
    engine = Engine(config, registry)

    assert INTERNAL_LOGS_GENERATOR_NAME not in engine._generators


def test_internal_logs_skips_jinja_template_lookup(tmp_path, monkeypatch):
    """Reserved generator must not call TemplateCache for __internal__ sentinel."""
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    def fail_lookup(*args, **kwargs):
        raise AssertionError("TemplateCache.get_template must not run for internal-logs")

    monkeypatch.setattr(TemplateCache, "get_template", fail_lookup)

    config = create_default_config(tmp_path)
    _enable_internal_logs(config)

    registry = EntityRegistry(config)
    engine = Engine(config, registry)

    assert isinstance(engine._generators[INTERNAL_LOGS_GENERATOR_NAME], InternalLogGenerator)


def test_engine_reload_updates_internal_logs_from_generators_entry(tmp_path, monkeypatch):
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
    assert internal_after.state.value == "STOPPED"
    for handler in internal_after.output_handlers:
        handler.close()
