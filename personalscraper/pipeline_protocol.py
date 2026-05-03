"""Pipeline step protocol and context bundle."""

# ruff: noqa: D102

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from rich.console import Console

    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.models import StepReport


@dataclass(frozen=True)
class StepContext:
    """Context passed to every pipeline step adapter."""

    config: "Config"
    settings: "Settings"
    dry_run: bool
    interactive: bool
    verbose: bool
    console: "Console"
    upstream: Mapping[str, "StepReport"]
    extras: MutableMapping[str, Any]


@runtime_checkable
class PipelineStep(Protocol):
    """Callable pipeline step contract."""

    name: str

    def __call__(self, ctx: StepContext) -> "StepReport | tuple[StepReport, Any]": ...


def is_pipeline_step(obj: Any) -> bool:
    """Return True when *obj* satisfies the runtime step convention."""
    if not isinstance(obj, PipelineStep):
        return False
    name = getattr(obj, "name", None)
    return isinstance(name, str) and bool(name)


__all__ = ["PipelineStep", "StepContext", "is_pipeline_step"]
