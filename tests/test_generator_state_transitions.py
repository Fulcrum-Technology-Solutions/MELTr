"""Regression tests for generator state transitions."""

from meltr.core.config import GeneratorConfig
from meltr.core.generator import Generator, GeneratorState


class _DummyTemplateLoader:
    pass


class _DummyRegistry:
    pass


class _FailingOutput:
    name = "failing-output"

    def write(self, event: str) -> None:
        raise RuntimeError("forced output failure")


def test_generator_transitions_to_degraded_when_all_outputs_fail() -> None:
    """Generator should degrade if every output write fails."""
    generator = Generator(
        name="test-generator",
        config=GeneratorConfig(
            name="test-generator",
            template="vendor/product/source/event",
            enabled=True,
            outputs=["failing-output"],
        ),
        template_loader=_DummyTemplateLoader(),
        registry=_DummyRegistry(),
        output_handlers=[_FailingOutput()],
    )

    # Put generator into RUNNING without full startup plumbing.
    generator._state = GeneratorState.RUNNING

    generator._write_to_outputs('{"k":"v"}')

    assert generator.state == GeneratorState.DEGRADED
