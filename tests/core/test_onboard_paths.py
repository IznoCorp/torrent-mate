"""Tests for core/onboard_paths (bosun sub-phase 4.2)."""

from __future__ import annotations

from pathlib import PurePosixPath

from kanbanmate.core.onboard_paths import is_within_base_dirs

BASES = [PurePosixPath("/home/izno/dev"), PurePosixPath("/home/izno/deploy")]


def test_under_base_accepted() -> None:
    assert is_within_base_dirs(PurePosixPath("/home/izno/dev/KanbanMate"), BASES) is True


def test_equal_base_accepted() -> None:
    assert is_within_base_dirs(PurePosixPath("/home/izno/dev"), BASES) is True


def test_outside_rejected() -> None:
    assert is_within_base_dirs(PurePosixPath("/etc/passwd"), BASES) is False


def test_sibling_prefix_not_a_match() -> None:
    # /home/izno/development must NOT match base /home/izno/dev (parents check, not str-prefix).
    assert is_within_base_dirs(PurePosixPath("/home/izno/development/x"), BASES) is False
