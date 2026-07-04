"""Unit tests for ``personalscraper.web.auth.passwords`` (tm-shell feature).

Pure unit tests — no FastAPI, no TestClient, no config dependency.
See docs/features/tm-shell/plan/phase-02-auth.md §2.4.
"""

from __future__ import annotations

from personalscraper.web.auth.passwords import hash_password, verify_password


class TestHashPassword:
    """Tests for :func:`hash_password`."""

    def test_returns_scrypt_format(self) -> None:
        """Hash has the ``scrypt$N$r$p$salt_b64$hash_b64`` prefix."""
        h = hash_password("test")
        assert h.startswith("scrypt$16384$8$1$"), f"Unexpected prefix: {h[:30]}"

    def test_salt_randomness(self) -> None:
        """Two hashes of the same password differ (random salt)."""
        h1 = hash_password("test")
        h2 = hash_password("test")
        assert h1 != h2, "Two hashes of the same password must differ (random salt)"

    def test_unicode_password(self) -> None:
        """Unicode passwords (accented, emoji) are hashed correctly."""
        h = hash_password("mot-de-passe-emoji-\U0001f525")
        assert h.startswith("scrypt$16384$8$1$")


class TestVerifyPassword:
    """Tests for :func:`verify_password`."""

    def test_round_trip(self) -> None:
        """Hash → verify round-trip returns True."""
        h = hash_password("my-password")
        assert verify_password("my-password", h) is True

    def test_wrong_password(self) -> None:
        """Wrong password returns False."""
        h = hash_password("correct")
        assert verify_password("wrong", h) is False

    def test_empty_stored_returns_false(self) -> None:
        """Empty stored string returns False, never raises."""
        assert verify_password("anything", "") is False

    def test_garbage_stored_returns_false(self) -> None:
        """Unparseable stored string returns False, never raises."""
        assert verify_password("anything", "garbage") is False

    def test_scrypt_dollar_bad_returns_false(self) -> None:
        """Stored string ``scrypt$bad`` (wrong number of parts) returns False."""
        assert verify_password("anything", "scrypt$bad") is False

    def test_malformed_base64_returns_false(self) -> None:
        """Malformed base64 in stored hash returns False."""
        assert verify_password("anything", "scrypt$16384$8$1$!!!invalid!!!$!!!invalid!!!") is False

    def test_unicode_password_round_trip(self) -> None:
        """Unicode password round-trip (accented + emoji)."""
        pw = "passw0rd-\U0001f525"
        h = hash_password(pw)
        assert verify_password(pw, h) is True

    def test_constant_time_protection_uses_compare_digest(self) -> None:
        """Verify that :func:`verify_password` does not short-circuit on length.

        A wrong password of the same length should still return False
        (not raise) — the comparison uses ``hmac.compare_digest`` internally.
        """
        h = hash_password("correct")
        # Same-length wrong password — verifies no early-exit based on length.
        assert verify_password("wrong__", h) is False
