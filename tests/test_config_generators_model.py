from pathlib import Path

from meltr.core.config import Config, create_default_config, ensure_internal_logs_generator
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME


def test_default_config_has_disabled_internal_logs_generator(tmp_path: Path):
    cfg = create_default_config(tmp_path)
    assert not hasattr(cfg, "pipelines") or "pipelines" not in Config.model_fields
    assert "internal_logs" not in Config.model_fields
    names = [g.name for g in cfg.generators]
    assert names.count(INTERNAL_LOGS_GENERATOR_NAME) == 1
    il = next(g for g in cfg.generators if g.name == INTERNAL_LOGS_GENERATOR_NAME)
    assert il.enabled is False
    assert il.outputs == []
    assert il.template == "__internal__"


def test_ensure_injects_internal_logs_when_missing(tmp_path: Path):
    cfg = create_default_config(tmp_path)
    cfg.generators = [g for g in cfg.generators if g.name != INTERNAL_LOGS_GENERATOR_NAME]
    cfg = ensure_internal_logs_generator(cfg)
    assert any(g.name == INTERNAL_LOGS_GENERATOR_NAME for g in cfg.generators)


def test_ensure_does_not_duplicate_internal_logs(tmp_path: Path):
    cfg = create_default_config(tmp_path)
    cfg = ensure_internal_logs_generator(cfg)
    cfg = ensure_internal_logs_generator(cfg)
    assert sum(1 for g in cfg.generators if g.name == INTERNAL_LOGS_GENERATOR_NAME) == 1
