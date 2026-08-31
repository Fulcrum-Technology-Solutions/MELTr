"""Config editor generator helpers (continuous-first, internal-logs rules)."""

from __future__ import annotations

from meltr.cli import config_editor as ce
from meltr.core.config import (
    GeneratorConfig,
    OutputDefinition,
    ScheduleConfig,
    create_default_config,
)
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME


def _config_with_output(tmp_path):
    config = create_default_config(tmp_path)
    config.outputs.definitions.append(
        OutputDefinition(name="file-out", type="file", path="/tmp/out.log")
    )
    return config


def test_cannot_remove_internal_logs(tmp_path):
    config = create_default_config(tmp_path)
    assert any(g.name == INTERNAL_LOGS_GENERATOR_NAME for g in config.generators)

    updated, removed = ce._remove_generator(config, INTERNAL_LOGS_GENERATOR_NAME)

    assert removed is False
    assert any(g.name == INTERNAL_LOGS_GENERATOR_NAME for g in updated.generators)
    assert len(updated.generators) == len(config.generators)


def test_remove_user_generator(tmp_path):
    config = _config_with_output(tmp_path)
    config.generators.append(
        GeneratorConfig(
            name="user-gen",
            template="vendor/product/source/event",
            enabled=True,
            outputs=["file-out"],
        )
    )
    before = len(config.generators)

    updated, removed = ce._remove_generator(config, "user-gen")

    assert removed is True
    assert len(updated.generators) == before - 1
    assert not any(g.name == "user-gen" for g in updated.generators)
    assert any(g.name == INTERNAL_LOGS_GENERATOR_NAME for g in updated.generators)


def test_add_generator_omits_schedule_by_default(tmp_path, monkeypatch):
    config = _config_with_output(tmp_path)
    monkeypatch.setattr(ce, "_select_template_interactive", lambda *a, **k: "v/p/s/e")
    monkeypatch.setattr(
        ce,
        "_generate_generator_name",
        lambda *a, **k: "my_gen",
    )
    monkeypatch.setattr(ce.TemplateLoader, "__init__", lambda self, cfg: None)
    monkeypatch.setattr(
        ce.TemplateLoader,
        "resolve_template",
        lambda self, tid: None,
    )
    prompts = iter(["my_gen", "1"])
    monkeypatch.setattr(ce.Prompt, "ask", lambda *a, **k: next(prompts, k.get("default", "")))
    monkeypatch.setattr(ce.Confirm, "ask", lambda *a, **k: True)

    gen = ce._create_generator_interactive(config)

    assert gen is not None
    assert gen.schedule is None
    assert gen.enabled is True
    assert gen.outputs == ["file-out"]
    assert gen.template == "v/p/s/e"


def test_prompt_schedule_continuous_clears_optional_fields(monkeypatch):
    prompts = iter(["continuous"])
    monkeypatch.setattr(ce.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(ce.Prompt, "ask", lambda *a, **k: next(prompts))

    schedule = ce._prompt_schedule_config(
        ScheduleConfig(mode="window", days=["mon"], time="09:00-17:00", timezone="UTC")
    )

    assert schedule is not None
    assert schedule.mode == "continuous"


def test_prompt_schedule_window_fields(monkeypatch):
    prompts = iter(["window", "mon,tue", "09:00-17:00", "America/New_York"])
    monkeypatch.setattr(ce.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(ce.Prompt, "ask", lambda *a, **k: next(prompts, k.get("default", "")))

    schedule = ce._prompt_schedule_config(None)

    assert schedule is not None
    assert schedule.mode == "window"
    assert schedule.days == ["mon", "tue"]
    assert schedule.time == "09:00-17:00"
    assert schedule.timezone == "America/New_York"


def test_prompt_schedule_burst_fields(monkeypatch):
    prompts = iter(["burst", "100", "5m", "UTC"])
    monkeypatch.setattr(ce.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(ce.Prompt, "ask", lambda *a, **k: next(prompts, k.get("default", "")))

    schedule = ce._prompt_schedule_config(None)

    assert schedule is not None
    assert schedule.mode == "burst"
    assert schedule.count == 100
    assert schedule.duration == "5m"
    assert schedule.timezone == "UTC"


def test_prompt_schedule_none_disables(monkeypatch):
    monkeypatch.setattr(
        ce.Confirm,
        "ask",
        lambda *a, **k: False if "Configure a schedule" in a[0] else k.get("default", True),
    )

    schedule = ce._prompt_schedule_config(ScheduleConfig(mode="window", time="09:00-17:00"))

    assert schedule is None


def test_is_reserved_generator_name():
    assert ce._is_reserved_generator_name(INTERNAL_LOGS_GENERATOR_NAME) is True
    assert ce._is_reserved_generator_name("my-generator") is False


def test_edit_internal_logs_skips_template_and_schedule(tmp_path, monkeypatch):
    config = _config_with_output(tmp_path)
    internal = next(g for g in config.generators if g.name == INTERNAL_LOGS_GENERATOR_NAME)
    assert internal.enabled is False

    selects = iter([1])
    monkeypatch.setattr(ce.IntPrompt, "ask", lambda *a, **k: next(selects))
    confirms = iter([True, True])
    monkeypatch.setattr(ce.Confirm, "ask", lambda *a, **k: next(confirms))
    monkeypatch.setattr(ce.Prompt, "ask", lambda *a, **k: "1")

    updated = ce._edit_generator_interactive(config)

    edited = updated.generators[0]
    assert edited.name == INTERNAL_LOGS_GENERATOR_NAME
    assert edited.enabled is True
    assert edited.outputs == ["file-out"]
    assert edited.schedule is None


def test_set_schedule_rejects_internal_logs(tmp_path, monkeypatch):
    config = create_default_config(tmp_path)
    monkeypatch.setattr(ce.console, "print", lambda *a, **k: None)

    updated = ce._set_generator_schedule_interactive(config, INTERNAL_LOGS_GENERATOR_NAME)

    assert updated is config
    internal = next(g for g in updated.generators if g.name == INTERNAL_LOGS_GENERATOR_NAME)
    assert internal.schedule is None


def test_set_schedule_updates_user_generator(tmp_path, monkeypatch):
    config = _config_with_output(tmp_path)
    config.generators.append(
        GeneratorConfig(
            name="user-gen",
            template="vendor/product/source/event",
            enabled=True,
            outputs=["file-out"],
        )
    )
    monkeypatch.setattr(ce.console, "print", lambda *a, **k: None)
    monkeypatch.setattr(
        ce,
        "_prompt_schedule_config",
        lambda existing: ScheduleConfig(mode="burst", count=50, duration="10m"),
    )

    updated = ce._set_generator_schedule_interactive(config, "user-gen")
    gen = next(g for g in updated.generators if g.name == "user-gen")

    assert gen.schedule is not None
    assert gen.schedule.mode == "burst"
    assert gen.schedule.count == 50
