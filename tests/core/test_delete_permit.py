"""Tests for core.delete_permit: Protocols + AllowAllPermit."""

from __future__ import annotations

from pathlib import Path

from personalscraper.core.delete_permit import (
    ALLOW,
    AllowAllPermit,
    DeletePermit,
)


def test_allow_all_permit_returns_allow(tmp_path: Path) -> None:
    """AllowAllPermit.may_delete always returns the ALLOW sentinel."""
    permit = AllowAllPermit()
    decision = permit.may_delete(tmp_path / "somefile.mkv")
    assert decision is ALLOW


def test_allow_all_permit_implements_protocol() -> None:
    """AllowAllPermit satisfies the DeletePermit runtime-checkable Protocol."""
    permit = AllowAllPermit()
    assert isinstance(permit, DeletePermit)


def test_permit_decision_allow_is_singleton() -> None:
    """ALLOW is a true singleton — identity equality holds."""
    assert ALLOW is ALLOW


def test_veto_carries_reason() -> None:
    """veto() returns a non-ALLOW decision whose string form includes the reason."""
    from personalscraper.core.delete_permit import veto

    decision = veto("seeding: lacale min_seed_time not met")
    assert decision is not ALLOW
    assert "lacale" in str(decision)


def test_allow_all_permit_record_dispatch_is_noop(tmp_path: Path) -> None:
    """AllowAllPermit.record_dispatch is a no-op that never raises."""
    permit = AllowAllPermit()
    permit.record_dispatch(
        staging_source=tmp_path / "staging" / "x.mkv",
        dispatched_dest=tmp_path / "library" / "x.mkv",
    )


def test_allow_all_permit_mark_breach_is_noop(tmp_path: Path) -> None:
    """AllowAllPermit.mark_breach is a no-op that never raises."""
    permit = AllowAllPermit()
    permit.mark_breach(tmp_path / "library" / "x.mkv")


def test_allow_all_permit_implements_recorder_protocol() -> None:
    """AllowAllPermit satisfies the SeedObligationRecorder runtime-checkable Protocol."""
    from personalscraper.core.delete_permit import SeedObligationRecorder

    permit = AllowAllPermit()
    assert isinstance(permit, SeedObligationRecorder)
