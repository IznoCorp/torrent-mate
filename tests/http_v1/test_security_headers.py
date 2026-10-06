"""The served application sets its own security headers; the reverse proxy is not relied on.

``X-Content-Type-Options: nosniff`` and ``Strict-Transport-Security`` ride every response of
the v1 application, of the standalone process that mounts it and the SPA's static pages (v0's ``create_app``
is read in ``tests/web``). The Content-Security-Policy is not set here yet: its text is the
operator's ruling.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.http_v1.security_headers import CONTENT_SECURITY_POLICY, SECURITY_HEADERS, SecurityHeaders
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


def _directives(policy: str) -> dict[str, list[str]]:
    """Read a policy into its directives.

    Args:
        policy: The header's value.

    Returns:
        Each directive's name and its sources.
    """
    parsed = (part.strip().split() for part in policy.split(";") if part.strip())
    return {name: sources for name, *sources in parsed}


def allows(policy: str, directive: str, url: str, *, page: str = "https://tm.example.org") -> bool:
    """Whether a policy lets a page load a URL under a resource directive (origins and ``'self'`` only).

    Args:
        policy: The header's value.
        directive: The directive, e.g. ``img-src``.
        url: The address to load.
        page: The page's own origin.

    Returns:
        True when the directive, or ``default-src`` when it has none, names the URL's origin.
    """
    rules = _directives(policy)
    sources = rules.get(directive, rules.get("default-src", []))
    parts = urlsplit(url)
    origin = f"{parts.scheme}:" if not parts.netloc else f"{parts.scheme}://{parts.netloc}"
    return origin in sources or ("'self'" in sources and origin == page)


def test_the_policy_is_exactly_the_one_the_operator_ruled() -> None:
    """The text is pinned: a closed list, no ``'unsafe-inline'``, nothing looser without a ruling."""
    assert CONTENT_SECURITY_POLICY == (
        "default-src 'self'; "
        "img-src 'self' https://image.tmdb.org https://artworks.thetvdb.com https://plex.tv "
        "https://assets.plex.tv https://www.gravatar.com; "
        "frame-src https://www.youtube.com; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    assert "unsafe" not in CONTENT_SECURITY_POLICY


@pytest.mark.parametrize(
    "url",
    [
        "https://image.tmdb.org/t/p/w500/poster.jpg",
        "https://artworks.thetvdb.com/banners/poster.jpg",
        "https://plex.tv/users/0123456789abcdef/avatar?c=1",
        "https://assets.plex.tv/avatars/0123456789abcdef.jpg?1655775273",
        "https://www.gravatar.com/avatar/00000000000000000000000000000000",
        "https://tm.example.org/assets/poster.webp",
    ],
)
def test_the_policy_allows_the_images_the_interface_shows(url: str) -> None:
    """A poster from TMDB or TVDB, an avatar from plex.tv or Gravatar and the app's own artwork load."""
    assert allows(CONTENT_SECURITY_POLICY, "img-src", url)


@pytest.mark.parametrize("url", ["https://evil.example.net/p.jpg", "data:image/png;base64,AAAA"])
def test_the_policy_refuses_any_other_image(url: str) -> None:
    """Anything off the closed list, a ``data:`` image included, does not load."""
    assert not allows(CONTENT_SECURITY_POLICY, "img-src", url)


def test_the_policy_scopes_the_trailer_embed_and_the_rest_to_the_origin() -> None:
    """Only YouTube may be framed; scripts, styles and connections fall back to the origin."""
    assert allows(CONTENT_SECURITY_POLICY, "frame-src", "https://www.youtube.com/embed/abc")
    assert not allows(CONTENT_SECURITY_POLICY, "frame-src", "https://evil.example.net/")
    for directive in ("script-src", "style-src", "connect-src", "font-src"):
        assert not allows(CONTENT_SECURITY_POLICY, directive, "https://image.tmdb.org/x")


def test_a_v1_route_and_the_standalone_process_carry_the_policy(
    v1_client: Callable[..., TestClient], test_config: Config
) -> None:
    """The policy rides v1's answers, a refusal included, and the standalone parent's own 404."""
    assert v1_client().get("/version").headers.get("content-security-policy") == CONTENT_SECURITY_POLICY
    assert v1_client(role=None).get("/auth/me").headers.get("content-security-policy") == CONTENT_SECURITY_POLICY
    with TestClient(build_standalone_v1_app(test_config, Settings(_env_file=None))) as standalone:  # type: ignore[call-arg]
        assert standalone.get("/nothing-here").headers.get("content-security-policy") == CONTENT_SECURITY_POLICY


def test_a_static_page_without_the_policy_flag_carries_none(tmp_path: Path) -> None:
    """The middleware adds the policy only when asked: v0's pages are not under it."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>SPA</html>")
    app = FastAPI()
    mount_spa(app, static_dir, dev_mode=False)
    app.add_middleware(SecurityHeaders)

    assert "content-security-policy" not in TestClient(app).get("/some/page").headers
