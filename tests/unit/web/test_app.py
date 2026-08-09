"""Unit tests for FastAPI application route registration.

Verifies that all expected routers are mounted under ``guarded_api``
(require_session perimeter) when ``create_app()`` builds the application.
"""

from __future__ import annotations

from typing import Any

from starlette.routing import BaseRoute


def _collect_paths(routes: list[BaseRoute]) -> list[str]:
    """Recursively collect path strings from a route list.

    Starlette/FastAPI nests sub-routers as ``_IncludedRouter`` objects
    wrapping an ``APIRouter`` whose ``.routes`` holds the actual leaf
    ``APIRoute`` entries (or further ``_IncludedRouter`` wrappers for
    deeply-nested guards like ``guarded_api``).
    """
    paths: list[str] = []
    for r in routes:
        # Leaf route — has a .path attribute (Route, Mount, APIRoute).
        if hasattr(r, "path"):
            paths.append(getattr(r, "path"))
        # Recursion case 1: direct .routes attribute (Mount, etc.).
        if hasattr(r, "routes"):
            paths.extend(_collect_paths(getattr(r, "routes")))
        # Recursion case 2: _IncludedRouter wraps original_router (APIRouter).
        if hasattr(r, "original_router") and hasattr(getattr(r, "original_router"), "routes"):
            paths.extend(_collect_paths(getattr(r, "original_router").routes))
    return paths


def test_responses_are_compressed(test_config: Any) -> None:
    """Responses above 1 KB ship compressed.

    Measured on staging 2026-08-08: the SPA served 1.05 MB of JS with NO
    ``content-encoding`` — seconds of blank screen on a phone. The app owns
    the compression so it survives a reverse-proxy reconfiguration.
    """
    from starlette.middleware.gzip import GZipMiddleware

    from personalscraper.config import Settings
    from personalscraper.web.app import create_app

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    app = create_app(test_config, settings)

    gzip_layers = [m for m in app.user_middleware if m.cls is GZipMiddleware]
    assert len(gzip_layers) == 1, "the app must compress exactly once"
    # The threshold is part of the contract: compressing tiny JSON costs more
    # CPU than it saves bytes.
    assert gzip_layers[0].kwargs.get("minimum_size") == 1024


def test_decisions_router_registered(test_config: Any) -> None:
    """Decisions router is mounted at /api/decisions under the guarded perimeter."""
    from personalscraper.config import Settings
    from personalscraper.web.app import create_app

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    app = create_app(test_config, settings)

    route_paths = _collect_paths(app.router.routes)

    assert any(p.startswith("/api/decisions") for p in route_paths), (
        f"Expected /api/decisions routes in app; got: {sorted(route_paths)}"
    )

    # Specific routes from the decisions router.
    assert "/api/decisions/" in route_paths
    assert "/api/decisions/{decision_id}" in route_paths
    assert "/api/decisions/{decision_id}/search" in route_paths
    assert "/api/decisions/{decision_id}/resolve" in route_paths
    assert "/api/decisions/{decision_id}/dismiss" in route_paths


def test_all_guarded_routers_registered(test_config: Any) -> None:
    """Every expected guarded router is present — regression gate for mount order."""
    from personalscraper.config import Settings
    from personalscraper.web.app import create_app

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    app = create_app(test_config, settings)

    route_paths = _collect_paths(app.router.routes)

    expected_prefixes = [
        "/api/version",
        "/api/pipeline",
        "/api/maintenance",
        "/api/config",
        "/api/decisions",
    ]
    for prefix in expected_prefixes:
        assert any(p.startswith(prefix) for p in route_paths), f"Missing guarded router prefix: {prefix}"
