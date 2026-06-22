"""Tests for the persistent session secret (bosun §12).

Validates ACC-11: a session token MUST survive a process restart when the secret is
pinned, and MUST be invalidated when the secret is random-per-start (the unpinned bug).
"""

from __future__ import annotations

import secrets

from kanbanmate.http.auth import AuthConfig, make_token, verify_token


def test_token_survives_restart_with_pinned_secret() -> None:
    """A token minted under one AuthConfig verifies under a fresh one built from the SAME secret."""
    secret = "pinned-deadbeef-cafef00d"
    cfg_a = AuthConfig(login="op", password="pw", secret=secret)
    token = make_token("op", cfg_a.secret)
    # Simulate a process restart: a brand-new AuthConfig from the SAME pinned secret.
    cfg_b = AuthConfig(login="op", password="pw", secret=secret)
    assert verify_token(token, cfg_b.secret) == "op"


def test_token_dies_across_restart_with_random_secret() -> None:
    """Control: distinct random secrets (the unpinned bug) invalidate the token."""
    token = make_token("op", secrets.token_hex(32))
    assert verify_token(token, secrets.token_hex(32)) is None
