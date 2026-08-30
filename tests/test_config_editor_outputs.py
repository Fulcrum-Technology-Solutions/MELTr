"""Config editor output management tests."""

from meltr.cli import config_editor as ce
from meltr.core.config import GeneratorConfig, OutputDefinition, create_default_config
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME


def _config_with_referenced_output(tmp_path):
    config = create_default_config(tmp_path)
    config.outputs.definitions.append(
        OutputDefinition(name="file-out", type="file", path="/tmp/out.log")
    )
    for gen in config.generators:
        if gen.name == INTERNAL_LOGS_GENERATOR_NAME:
            gen.outputs = ["file-out"]
            break
    config.generators.append(
        GeneratorConfig(
            name="user-gen",
            template="vendor/product/source/event",
            enabled=True,
            outputs=["file-out"],
        )
    )
    return config


def test_remove_output_cancelled_when_generators_reference_it(tmp_path, monkeypatch):
    config = _config_with_referenced_output(tmp_path)
    before = len(config.outputs.definitions)

    prompts = iter([1])
    monkeypatch.setattr(ce.IntPrompt, "ask", lambda *a, **k: next(prompts))
    confirms = iter([False])
    monkeypatch.setattr(ce.Confirm, "ask", lambda *a, **k: next(confirms, False))

    updated = ce._remove_output_interactive(config)

    assert len(updated.outputs.definitions) == before
    assert any(o.name == "file-out" for o in updated.outputs.definitions)


def test_remove_output_proceeds_when_user_confirms_despite_references(tmp_path, monkeypatch):
    config = _config_with_referenced_output(tmp_path)

    prompts = iter([1])
    monkeypatch.setattr(ce.IntPrompt, "ask", lambda *a, **k: next(prompts))
    confirms = iter([True, True])
    monkeypatch.setattr(ce.Confirm, "ask", lambda *a, **k: next(confirms, False))

    updated = ce._remove_output_interactive(config)

    assert not any(o.name == "file-out" for o in updated.outputs.definitions)
