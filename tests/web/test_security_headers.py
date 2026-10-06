"""v0's ``create_app`` — the process that mounts v1 and the SPA — sets the security headers itself."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1.security_headers import CONTENT_SECURITY_POLICY
from personalscraper.web.app import create_app


@pytest.mark.parametrize("path", ["/api/health", "/some/page"], ids=["v0-api", "v0-spa"])
def test_the_v0_application_carries_the_headers(make_web_client: Callable[..., TestClient], path: str) -> None:
    """Both headers, with their exact values, on an API route and on a page of the SPA fallback."""
    response = make_web_client().get(path)

    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"


@pytest.mark.parametrize("path", ["/api/health", "/some/page"], ids=["v0-api", "v0-spa"])
def test_the_v0_pages_are_not_under_the_policy(make_web_client: Callable[..., TestClient], path: str) -> None:
    """v0's API and its SPA (``frontend/``, dead at the switchover) carry no Content-Security-Policy."""
    assert "content-security-policy" not in make_web_client().get(path).headers


def test_v1_mounted_in_v0_keeps_its_policy(test_config: Config) -> None:
    """Under v0's ``create_app`` the mounted v1 answers with the policy, while v0's own routes do not."""
    config = test_config.model_copy(update={"web": test_config.web.model_copy(update={"v1_enabled": True})})
    client = TestClient(create_app(config, Settings(web_jwt_secret="testsecret", _env_file=None)))  # type: ignore[call-arg]

    assert client.get("/api/v1/anything").headers.get("content-security-policy") == CONTENT_SECURITY_POLICY
    assert "content-security-policy" not in client.get("/api/health").headers
