"""Tests for the GitHub token loader (:mod:`kanbanmate.adapters.github.token`).

``load_token`` exposes injectable ``env`` and ``path`` parameters so every branch can be
exercised without touching the real filesystem or environment: env-var wins, file fallback,
``FileNotFoundError`` when neither source exists, and ``.strip()`` whitespace handling.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kanbanmate.adapters.github.token import TokenScopeError, fetch_token_scopes, load_token


def test_load_token_env_wins_over_file(tmp_path: Path) -> None:
    """When ``KANBAN_TOKEN`` is present in the env mapping the file is never read."""
    token_file = tmp_path / "token"
    token_file.write_text("ghp_from_file")
    env = {"KANBAN_TOKEN": " ghp_from_env "}

    token = load_token(env=env, path=token_file)

    # Env value wins and is stripped of surrounding whitespace.
    assert token == "ghp_from_env"


def test_load_token_file_fallback(tmp_path: Path) -> None:
    """When ``KANBAN_TOKEN`` is absent the token file is read as a fallback."""
    token_file = tmp_path / "token"
    token_file.write_text("  ghp_from_file  \n")
    env: dict[str, str] = {}

    token = load_token(env=env, path=token_file)

    # File content is stripped of surrounding whitespace.
    assert token == "ghp_from_file"


def test_load_token_file_not_found() -> None:
    """When neither env var nor token file exists a ``FileNotFoundError`` is raised."""
    env: dict[str, str] = {}
    missing = Path("/nonexistent/token/path")

    with pytest.raises(FileNotFoundError) as excinfo:
        load_token(env=env, path=missing)

    # The error message names the path so the operator knows where to look.
    assert str(missing) in str(excinfo.value)


def test_load_token_strips_whitespace_from_env() -> None:
    """The env-var token is ``.strip()``-ed, removing leading/trailing whitespace."""
    env = {"KANBAN_TOKEN": "\t  ghp_token  \n"}

    token = load_token(env=env, path=Path("/nonexistent"))

    assert token == "ghp_token"


def test_load_token_strips_whitespace_from_file(tmp_path: Path) -> None:
    """The file-read token is ``.strip()``-ed, removing leading/trailing whitespace."""
    token_file = tmp_path / "token"
    token_file.write_text("\n\n  ghp_file_token  \n\n")
    env: dict[str, str] = {}

    token = load_token(env=env, path=token_file)

    assert token == "ghp_file_token"


# ---------------------------------------------------------------------------
# TokenScopeError (already tested via test_client.py but ensure the type is importable)
# ---------------------------------------------------------------------------


def test_token_scope_error_is_importable() -> None:
    """Smoke test: ``TokenScopeError`` is a ``RuntimeError`` subclass reachable from this module."""
    err = TokenScopeError(frozenset({"admin:org_hook"}))
    assert isinstance(err, RuntimeError)
    assert "admin:org_hook" in str(err)


# ---------------------------------------------------------------------------
# fetch_token_scopes: reads the X-OAuth-Scopes header (network monkeypatched)
# ---------------------------------------------------------------------------


def test_fetch_token_scopes_reads_oauth_scopes_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """``fetch_token_scopes`` authenticates a ``GET /`` and parses ``X-OAuth-Scopes``."""
    seen: dict[str, object] = {}

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return b""

        def getheader(self, name: str) -> str | None:
            return "project, repo" if name == "X-OAuth-Scopes" else None

    class _Conn:
        sock = None  # no real socket → the read-timeout settimeout is skipped

        def __init__(self, host: str, *, timeout: float) -> None:
            seen["host"] = host
            seen["connect_timeout"] = timeout

        def request(
            self, method: str, url: str, body: object = None, headers: dict[str, str] | None = None
        ) -> None:
            seen["method"] = method
            seen["url"] = url
            seen["auth"] = (headers or {}).get("Authorization")

        def getresponse(self) -> _Resp:
            return _Resp()

        def close(self) -> None:
            seen["closed"] = True

    import http.client

    monkeypatch.setattr(http.client, "HTTPSConnection", _Conn)

    scopes = fetch_token_scopes("ghp_demo")

    assert scopes == frozenset({"project", "repo"})
    assert seen["host"] == "api.github.com"
    assert (seen["method"], seen["url"]) == ("GET", "/")
    assert seen["auth"] == "Bearer ghp_demo"
    assert seen["closed"] is True


def test_fetch_token_scopes_empty_header_yields_empty_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing ``X-OAuth-Scopes`` header (fine-grained PAT) yields the empty set."""

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return b""

        def getheader(self, name: str) -> str | None:
            return None

    class _Conn:
        sock = None

        def __init__(self, host: str, *, timeout: float) -> None:
            pass

        def request(
            self, method: str, url: str, body: object = None, headers: dict[str, str] | None = None
        ) -> None:
            pass

        def getresponse(self) -> _Resp:
            return _Resp()

        def close(self) -> None:
            pass

    import http.client

    monkeypatch.setattr(http.client, "HTTPSConnection", _Conn)

    assert fetch_token_scopes("github_pat_xxx") == frozenset()


def test_fetch_token_scopes_raises_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 401 (dead/expired token) raises ``TokenAuthError`` rather than reporting empty scopes (#1).

    Before #1 the 401 response's (absent) scope header parsed to ``frozenset()``, which doctor then
    mistook for a fine-grained-PAT advisory PASS — so an expired token looked healthy.
    """
    from kanbanmate.adapters.github.token import TokenAuthError

    class _Resp:
        status = 401

        def read(self) -> bytes:
            return b'{"message": "Bad credentials"}'

        def getheader(self, name: str) -> str | None:
            return None

    class _Conn:
        sock = None

        def __init__(self, host: str, *, timeout: float) -> None:
            pass

        def request(
            self, method: str, url: str, body: object = None, headers: dict[str, str] | None = None
        ) -> None:
            pass

        def getresponse(self) -> _Resp:
            return _Resp()

        def close(self) -> None:
            pass

    import http.client

    monkeypatch.setattr(http.client, "HTTPSConnection", _Conn)

    with pytest.raises(TokenAuthError) as excinfo:
        fetch_token_scopes("ghp_expired")
    assert excinfo.value.status == 401
