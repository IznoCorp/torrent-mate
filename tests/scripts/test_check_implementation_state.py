"""Tests for scripts/check-implementation-state.py — the « In flight » row's two holds.

The arm reads two facts a row may carry, a version and a pull-request number,
and holds each against what `main` carries: its package version, and the
subjects of its history. Both lookups are patched here so the tests read a
row and a fake `main`, never this clone's.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-implementation-state.py"


def _load():
    """Import the guard as a module (its file name is not importable)."""
    spec = importlib.util.spec_from_file_location("check_implementation_state", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _state(tmp_path: Path, cell: str) -> Path:
    """Write an IMPLEMENTATION.md holding one « In flight » row with `cell`."""
    state = tmp_path / "IMPLEMENTATION.md"
    state.write_text(f"| **Last landed** | L10 |\n| **In flight** | {cell} |\n", encoding="utf-8")
    return state


MAIN_SUBJECTS = [
    "docs(steward): the steward runs on the operator's machine (#526)",
    "docs(maquette-l10-ter): the post-merge gesture (#522)",
    "L10-ter: the survey, the frame's model, and the plan re-cut around it (#521)",
]


@pytest.fixture
def guard(tmp_path: Path):
    """The module with `main` faked: version 0.98.53, the three subjects above."""
    module = _load()
    with (
        patch.object(module, "version_on_main", return_value=("0.98.53", None)),
        patch.object(module, "subjects_on_main", return_value=(MAIN_SUBJECTS, None)),
    ):
        yield module, tmp_path


def _run(module, state: Path) -> int:
    with patch.object(module, "STATE", state):
        return module.arm_in_flight()


def test_none_row_is_a_legible_silence(guard, capsys) -> None:
    """Between waves the row reads *none*: exit 0, and what was read is printed."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, "**none.** A wave writes its own row here")) == 0
    assert "nothing is in flight" in capsys.readouterr().out


def test_version_main_has_reached_is_refused(guard) -> None:
    """`main` at 0.98.53 has passed a row naming 0.98.51: that wave landed."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, "L10-bis, version 0.98.51, PR #999")) == 1


def test_version_ahead_of_main_is_in_flight(guard) -> None:
    """A row ahead of `main` is the one legitimate in-flight state."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, "L15, version 0.98.60, PR #999")) == 0


def test_versionless_row_whose_pull_request_main_holds_is_refused(guard, capsys) -> None:
    """B-238: a prose-only wave names no version; its pull request still lands in a subject."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, "L10-ter, no release (prose only), PR **#521**")) == 1
    assert "#521" in capsys.readouterr().err


def test_versionless_row_whose_pull_request_is_open_is_in_flight(guard) -> None:
    """A prose-only wave whose pull request `main` does not hold is in flight."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, "L15, PR #999, prose only")) == 0


def test_the_first_pull_request_number_is_the_waves(guard) -> None:
    """A row citing an older, merged pull request AFTER its own is not stale for it."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, "L15, PR #999 — clears what #522 left")) == 0


def test_row_naming_neither_version_nor_pull_request_is_refused(guard, capsys) -> None:
    """A row in flight that nothing can hold is refused, not passed in silence."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, "L15 — the frame, branch `feat/maquette-l15`")) == 1
    assert "neither" in capsys.readouterr().err


def test_unreachable_history_is_refused_not_passed(tmp_path: Path) -> None:
    """No `main` to read: refused, because « cannot check » must not read as clean."""
    module = _load()
    with (
        patch.object(module, "subjects_on_main", return_value=(None, "none of origin/main, main is reachable")),
    ):
        assert _run(module, _state(tmp_path, "L15, PR #999")) == 1


def test_squash_subject_is_matched_by_its_number_only(guard) -> None:
    """« (#52) » must not be read as #521 landed, nor « #5210 » as #521."""
    module = _load()
    assert module.pull_request_landed(521, ["x (#52)", "y (#5210)"]) is False
    assert module.pull_request_landed(521, ["z (#521)"]) is True
    assert module.pull_request_landed(521, ["Merge pull request #521 from a/b"]) is True


# B-246 — the version arm read `version 0.98.55` and not `version **0.98.55**`,
# while every row of that table writes its pull request in bold. The row was
# then held by ONE of the two arms, and the guard said so about neither: the
# no-version branch exited 0 in silence, which in a log is indistinguishable
# from a `no-version-bump` wave legitimately declaring none.
#
# Both tests below fail against the guard as it stood before the fix: the first
# because a bold version was not parsed at all (exit 0 over a version `main`
# has passed), the second because nothing was printed to compare.


@pytest.mark.parametrize(
    "cell",
    [
        "L10-bis, version 0.98.51, PR #999",
        "L10-bis, version **0.98.51**, PR #999",
        "L10-bis, version *0.98.51*, PR #999",
        "L10-bis, version `0.98.51`, PR #999",
    ],
)
def test_emphasis_is_part_of_the_versions_spelling(guard, cell: str) -> None:
    """A version `main` has passed is refused however the row emphasises it."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, cell)) == 1


def test_a_row_naming_no_version_says_so_rather_than_passing_mutely(guard, capsys) -> None:
    """« declares no version » and « I could not parse one » must not be one silence."""
    module, tmp_path = guard
    assert _run(module, _state(tmp_path, "L15, PR #999, prose only")) == 0
    assert "no version" in capsys.readouterr().out
