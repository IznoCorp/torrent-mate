"""FastAPI dependencies for accessing config and settings (tm-shell feature).

These are FastAPI dependency callables intended for use with ``Depends()``.
They read from ``request.app.state``, which is populated by ``create_app``.
"""

from __future__ import annotations

from typing import cast

from fastapi import Request

from personalscraper.conf.models.web import WebConfig
from personalscraper.config import Settings


def get_web_config(request: Request) -> WebConfig:
    """Dependency that extracts the WebConfig from the application state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The ``WebConfig`` instance stored on ``request.app.state.config``.
    """
    return cast(WebConfig, request.app.state.config.web)


def get_app_settings(request: Request) -> Settings:
    """Dependency that extracts the Settings from the application state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The ``Settings`` instance stored on ``request.app.state.settings``.
    """
    return cast(Settings, request.app.state.settings)
