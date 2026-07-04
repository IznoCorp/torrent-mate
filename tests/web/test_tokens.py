"""Unit tests for ``personalscraper.web.auth.tokens`` (tm-shell feature).

Pure unit tests — no FastAPI, no TestClient, no config dependency.
See docs/features/tm-shell/plan/phase-02-auth.md §2.4.
"""

from __future__ import annotations

import time

from personalscraper.web.auth.tokens import create_session_token, decode_session_token

TEST_SECRET = "test-secret-for-unit-tests"
OTHER_SECRET = "a-different-secret"


class TestCreateAndDecode:
    """Round-trip tests for :func:`create_session_token` + :func:`decode_session_token`."""

    def test_round_trip(self) -> None:
        """Encode → decode returns the original claims."""
        token = create_session_token("izno", TEST_SECRET, ttl_hours=720)
        payload = decode_session_token(token, TEST_SECRET)
        assert payload is not None
        assert payload["sub"] == "izno"

    def test_payload_has_required_claims(self) -> None:
        """Token payload carries ``sub``, ``iat``, and ``exp`` claims."""
        token = create_session_token("izno", TEST_SECRET, ttl_hours=720)
        payload = decode_session_token(token, TEST_SECRET)
        assert payload is not None
        assert "sub" in payload
        assert "iat" in payload
        assert "exp" in payload

    def test_iat_before_exp(self) -> None:
        """For a fresh token, ``iat`` is strictly before ``exp``."""
        token = create_session_token("izno", TEST_SECRET, ttl_hours=720)
        payload = decode_session_token(token, TEST_SECRET)
        assert payload is not None
        assert payload["iat"] < payload["exp"]

    def test_wrong_secret_returns_none(self) -> None:
        """Decoding with a different secret returns None."""
        token = create_session_token("izno", TEST_SECRET, ttl_hours=720)
        assert decode_session_token(token, OTHER_SECRET) is None

    def test_garbage_token_returns_none(self) -> None:
        """Decoding a garbage string returns None."""
        assert decode_session_token("not.a.valid.jwt", TEST_SECRET) is None

    def test_empty_token_returns_none(self) -> None:
        """Decoding an empty string returns None."""
        assert decode_session_token("", TEST_SECRET) is None

    def test_expired_token_returns_none(self) -> None:
        """An expired token (ttl_hours=0 + sleep) returns None.

        Uses ``ttl_hours=0`` so ``exp = iat``, then sleeps 1.1 s to ensure
        the decode timestamp is strictly after the expiration claim.
        """
        token = create_session_token("izno", TEST_SECRET, ttl_hours=0)
        time.sleep(1.1)
        assert decode_session_token(token, TEST_SECRET) is None

    def test_different_usernames_preserved(self) -> None:
        """The ``sub`` claim preserves the exact username passed at creation."""
        for username in ("izno", "admin", "user-123"):
            token = create_session_token(username, TEST_SECRET, ttl_hours=1)
            payload = decode_session_token(token, TEST_SECRET)
            assert payload is not None
            assert payload["sub"] == username
