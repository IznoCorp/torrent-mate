"""The served application sets its own security headers; the reverse proxy is not relied on.

``X-Content-Type-Options: nosniff`` and ``Strict-Transport-Security`` ride every response of
the v1 application, of the standalone process that mounts it and the SPA's static pages (v0's ``create_app``
is read in ``tests/web``). The Content-Security-Policy is not set here yet: its text is the
operator's ruling.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1.security_headers import SECURITY_HEADERS, SecurityHeaders
from personalscraper.http_v1.standalone import build_standalone_v1_app
from personalscraper.web.static import mount_spa

_EXPECTED = {
    "x-content-type-options": "nosniff",
    "strict-transport-security": "max-age=31536000; includeSubDomains",
}


def _assert_headers(response: object) -> None:
    """Assert both headers, with their exact values, on a response.

    Args:
        response: The HTTP response.
    """
    headers = response.headers  # type: ignore[attr-defined]
    for name, value in _EXPECTED.items():
        assert headers.get(name) == value, name


def test_the_register_holds_exactly_the_two_headers() -> None:
    """The register is the contract: nothing else rides without a ruling."""
    assert {name.lower(): value for name, value in SECURITY_HEADERS.items()} == _EXPECTED


def test_a_v1_route_carries_the_headers(v1_client: Callable[..., TestClient]) -> None:
    """A signed-in v1 read answers both headers."""
    response = v1_client().get("/version")
    assert response.status_code == 200
    _assert_headers(response)


def test_a_v1_refusal_carries_the_headers(v1_client: Callable[..., TestClient]) -> None:
    """A 401 Problem answer carries them too: a refusal is a response."""
    response = v1_client(role=None).get("/auth/me")
    assert response.status_code == 401
    _assert_headers(response)


def test_a_static_page_carries_the_headers(tmp_path: Path) -> None:
    """The SPA's index and an asset, served by ``mount_spa``, carry them."""
    static_dir = tmp_path / "static"
    (static_dir / "assets").mkdir(parents=True)
    (static_dir / "index.html").write_text("<html>SPA</html>")
    (static_dir / "assets" / "app.js").write_text("console.log('hello');")
    app = FastAPI()
    mount_spa(app, static_dir, dev_mode=False)
    app.add_middleware(SecurityHeaders)
    client = TestClient(app)

    _assert_headers(client.get("/some/page"))
    _assert_headers(client.get("/assets/app.js"))


def test_the_standalone_process_carries_the_headers(test_config: Config) -> None:
    """The parent application of the standalone server answers them on a path v1 does not own."""
    with TestClient(build_standalone_v1_app(test_config, Settings(_env_file=None))) as client:  # type: ignore[call-arg]
        response = client.get("/nothing-here")

    assert response.status_code == 404
    _assert_headers(response)
