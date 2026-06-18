"""Tests for :mod:`kanbanmate.core.profiles`.

Verifies that the canonical PROFILES tuple contains the expected names and that it stays in
parity with the per-profile allow-list in adapters.perms.
"""

from __future__ import annotations

from kanbanmate.core.profiles import PROFILES


def test_profiles_contains_expected_names() -> None:
    """PROFILES = the four workflow stages PLUS 'merge' (the autonomous merge stage)."""
    assert set(PROFILES) == {"docs", "prepare", "dev", "check", "merge"}


def test_profiles_is_tuple() -> None:
    """PROFILES must be a tuple (immutable, hashable)."""
    assert isinstance(PROFILES, tuple)


def test_profiles_parity_with_perms_allow_list() -> None:
    """core.profiles.PROFILES must be in exact parity with adapters.perms._PROFILE_ALLOW.

    This test is the drift guard: if a new profile is added to perms but not to
    the canonical tuple (or vice versa), the validator (V4) and the allow-list
    (perms) will disagree. The test imports _PROFILE_ALLOW directly from the
    adapters layer — that direction (test → adapters) is legal from the test suite.
    """
    from kanbanmate.adapters.perms import _PROFILE_ALLOW  # noqa: PLC2701

    assert set(PROFILES) == set(_PROFILE_ALLOW.keys()), (
        "core.profiles.PROFILES and adapters.perms._PROFILE_ALLOW are out of sync; "
        "update both when adding a new profile"
    )
