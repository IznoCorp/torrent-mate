"""Shared builders for the v1 sub-application's tests."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import FastAPI

from personalscraper.app.composition import build_app_services
from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1.app import create_v1_app
from personalscraper.http_v1.perimeter import ActorResolver


@pytest.fixture
def make_v1_app(test_config: Config) -> Callable[..., FastAPI]:
    """Return a factory building the v1 sub-application over the synthetic config.

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.

    Returns:
        A callable ``make(resolver=None)`` returning ``create_v1_app``'s application.
    """

    def _make(resolver: ActorResolver | None = None) -> FastAPI:
        """Build the sub-application over the synthetic config and its inert ``AppServices``.

        Args:
            resolver: The actor resolver; ``None`` keeps the default (nobody signed in).

        Returns:
            The v1 sub-application.
        """
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        return create_v1_app(test_config, settings, build_app_services(test_config, settings), resolver=resolver)

    return _make
