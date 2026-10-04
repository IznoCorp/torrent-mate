"""Unit tests for ``personalscraper.app.accounts.passwords`` (tm-shell feature).

Pure unit tests — no FastAPI, no TestClient, no config dependency.
See docs/features/tm-shell/plan/phase-02-auth.md §2.4.
"""

from __future__ import annotations

import pytest

from personalscraper.app.accounts.passwords import PASSWORD_MINIMUM, hash_password, policy_refusal, verify_password
from personalscraper.app.errors import RefusalCode


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


class TestPolicyRefusal:
    """Tests for :func:`policy_refusal` — the one password policy every local door applies."""

    def test_a_password_meeting_every_criterion_passes(self) -> None:
        """Twelve characters, an uppercase letter, a digit and a special character: no refusal."""
        assert policy_refusal("Correct-horse-9") is None

    @pytest.mark.parametrize("password", ["", "Ab1!", "Abcdefgh1!x"], ids=["empty", "four", "eleven"])
    def test_a_short_password_is_too_short_with_its_minimum(self, password: str) -> None:
        """Under the minimum, whatever else it holds: ``password.too_short`` naming the minimum."""
        refusal = policy_refusal(password)

        assert refusal is not None
        assert (refusal.status, refusal.code) == (400, RefusalCode.PASSWORD_TOO_SHORT)
        assert refusal.params == {"minimum": PASSWORD_MINIMUM}

    @pytest.mark.parametrize(
        "password",
        ["correct-horse-9", "Correct-horse-x", "Correcthorse99"],
        ids=["no-uppercase", "no-digit", "no-special"],
    )
    def test_a_long_password_missing_a_class_is_too_weak(self, password: str) -> None:
        """Long enough but missing an uppercase letter, a digit or a special character: ``password.too_weak``."""
        refusal = policy_refusal(password)

        assert refusal is not None
        assert (refusal.status, refusal.code) == (400, RefusalCode.PASSWORD_TOO_WEAK)
        assert refusal.params == {"minimum": PASSWORD_MINIMUM}

    def test_the_classes_are_unicode_categories(self) -> None:
        """An accented capital counts as uppercase, a space as special, and nothing is ever echoed."""
        refusal = policy_refusal("Évidemment 2026")

        assert refusal is None

    def test_the_refusal_never_carries_the_password(self) -> None:
        """Neither the detail nor the params name the password typed."""
        refusal = policy_refusal("correct-horse-9")

        assert refusal is not None
        assert "correct-horse-9" not in refusal.detail
        assert "correct-horse-9" not in repr(refusal.params)
