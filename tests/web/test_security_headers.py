"""v0's ``create_app`` — the process that mounts v1 and the SPA — sets the security headers itself."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("path", ["/api/health", "/some/page"], ids=["v0-api", "v0-spa"])
def test_the_v0_application_carries_the_headers(make_web_client: Callable[..., TestClient], path: str) -> None:
    """Both headers, with their exact values, on an API route and on a page of the SPA fallback."""
    response = make_web_client().get(path)

    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"
