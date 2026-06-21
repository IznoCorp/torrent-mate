"""Tests for app/control_state sentinel helpers (tiller §1.4)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from kanbanmate.app.control_state import (
    is_attached,
    remove_sentinel,
    sentinel_path,
    write_sentinel,
)


def test_sentinel_path_shape(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 7)
    assert p == tmp_path / "control" / "ticket-7.attached"


def test_write_creates_file(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 3)
    write_sentinel(p)
    assert p.exists()


def test_is_attached_returns_true_when_fresh(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 3)
    write_sentinel(p)
    assert is_attached(p, stale_minutes=5) is True


def test_is_attached_returns_false_when_absent(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 99)
    assert is_attached(p, stale_minutes=5) is False


def test_stale_sentinel_removed_and_returns_false(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 4)
    write_sentinel(p)
    # Back-date the mtime by 10 minutes
    past = time.time() - 600
    os.utime(p, (past, past))
    result = is_attached(p, stale_minutes=5)
    assert result is False
    assert not p.exists()  # removed by is_attached


def test_remove_sentinel_is_idempotent(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 5)
    remove_sentinel(p)  # absent — must not raise
    write_sentinel(p)
    remove_sentinel(p)
    assert not p.exists()
