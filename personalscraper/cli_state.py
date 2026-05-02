"""Shared CLI state and context objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from rich.console import Console

if TYPE_CHECKING:
    from personalscraper.conf.models import Config


@dataclass
class AppCtx:
    """Application context passed through Typer's ctx.obj.

    Attributes:
        config: Loaded and validated Config instance. None only for init-config.
        config_override: Path passed via --config CLI option, if any.
    """

    config: Config | None
    config_override: Path | None


class State(TypedDict):
    """Typed shape of the global CLI state dict."""

    console: Console
    verbose: bool
    quiet: bool


state: State = {"console": Console(), "verbose": False, "quiet": False}

__all__ = ["AppCtx", "State", "state"]
