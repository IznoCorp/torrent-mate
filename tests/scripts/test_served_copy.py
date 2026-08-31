"""Tests for B-256's lock and stamp — the half that needs no suite running.

`frontend/maquette/harness/served_copy.py` answers two questions about
`/tmp/tm-refonte`: who is allowed to rebuild it, and which build is in it. Both
answers are decided by pure logic over a directory and a JSON file, and both
have a failure mode that is SILENT by nature — a lock handed to the wrong
process, a stamp comparison that never fires — so neither can be left to a
manual run of the suite it protects.

THE THREE CASES THAT MATTER ARE THE ONES A CASUAL READING GETS BACKWARDS:

  a release from a process that does not hold the lock must do NOTHING. `run.sh`
      releases from a trap that fires however the script ended, INCLUDING the
      path where the acquisition was refused — an unconditional release there
      would take the lock away from the session that legitimately holds it, and
      the victim would be the session that did everything right;
  a comparison against a copy that carries no stamp must PASS. A machine whose
      served copy predates this file has nothing to compare, and failing every
      rule there would teach nobody anything about the change under test;
  a stamp written twice over an UNCHANGED tree must produce two different
      tokens. Same commit, same sources, two copies — and a reader that spanned
      them read two files.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "frontend" / "maquette" / "harness"


def load():
    """Imports the module without running its command line."""
    sys.path.insert(0, str(HARNESS))
    spec = importlib.util.spec_from_file_location("served_copy", HARNESS / "served_copy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


served_copy = load()


@pytest.fixture
def copy_at(tmp_path, monkeypatch):
    """Points the module at a scratch served copy, never the real one.

    The real `/tmp/tm-refonte` is what a suite on this machine may be reading at
    this very moment, and a test that took its lock would be the exact defect
    under test.
    """
    monkeypatch.setattr(served_copy, "SERVED", tmp_path)
    monkeypatch.setattr(served_copy, "STAMP", tmp_path / "build-stamp.json")
    monkeypatch.setattr(served_copy, "LOCK", tmp_path / ".lock")
    return tmp_path


class TestTheLock:
    """Who is allowed to rebuild the served copy."""

    def test_a_second_holder_is_refused(self, copy_at):
        """A suite may not rebuild the copy another suite is reading."""
        served_copy.acquire("session A", os.getpid())
        with pytest.raises(SystemExit) as refusal:
            served_copy.acquire("session B", os.getpid())
        assert "session A" in str(refusal.value)
        assert "B-256" in str(refusal.value)

    def test_a_release_by_another_process_does_nothing(self, copy_at):
        """The trap that fires after a REFUSED acquisition gives nothing away."""
        served_copy.acquire("session A", os.getpid())
        served_copy.release(os.getpid() + 1)
        assert (copy_at / ".lock").is_dir(), "the holder's lock was given away"

    def test_a_release_against_an_unreadable_lock_does_nothing(self, copy_at):
        """The refused session's trap must not destroy the holder's lock."""
        served_copy.acquire("session A", os.getpid())
        # The window between `mkdir` and the two writes, a truncated pid, or a
        # `.lock` made by hand: `_held_by` answers None, and the first version
        # fell through that case and deleted the lock.
        (copy_at / ".lock" / "pid").unlink()
        served_copy.release(os.getpid())
        assert (copy_at / ".lock").is_dir(), "an unreadable lock was given away"

    def test_the_holder_may_release(self, copy_at):
        """And the copy is then free for the next suite."""
        served_copy.acquire("session A", os.getpid())
        served_copy.release(os.getpid())
        assert not (copy_at / ".lock").exists()
        served_copy.acquire("session B", os.getpid())

    def test_a_live_holder_is_not_stale_however_old(self, copy_at):
        """Age alone never breaks a lock: a wave gate legitimately runs 25 minutes."""
        served_copy.acquire("session A", os.getpid())
        os.utime(copy_at / ".lock", (0, 0))
        with pytest.raises(SystemExit):
            served_copy.acquire("session B", os.getpid())

    def test_a_dead_holder_that_is_old_is_broken(self, copy_at, capsys):
        """A lock nobody holds any more is broken, and the break is announced."""
        # A pid this process can prove is gone: its own child, reaped.
        gone = os.fork()
        if gone == 0:
            os._exit(0)
        os.waitpid(gone, 0)
        served_copy.acquire("session A", gone)
        os.utime(copy_at / ".lock", (0, 0))
        served_copy.acquire("session B", os.getpid())
        assert "stale" in capsys.readouterr().err

    def test_a_dead_holder_that_is_recent_is_left_alone(self, copy_at):
        """Both conditions, never either — the age is the filter, the process is the signal."""
        gone = os.fork()
        if gone == 0:
            os._exit(0)
        os.waitpid(gone, 0)
        served_copy.acquire("session A", gone)
        with pytest.raises(SystemExit):
            served_copy.acquire("session B", os.getpid())


class TestTheStamp:
    """Which build is in the copy, and whether it moved."""

    def test_two_builds_of_one_tree_are_two_tokens(self, copy_at):
        """Same commit and same sources are still two copies, and a reader spanning them read two files."""
        first = served_copy.write_stamp()["token"]
        second = served_copy.write_stamp()["token"]
        assert first != second

    def test_the_stamp_carries_what_a_human_reads(self, copy_at):
        """The commit and the dirt travel beside the token, because that is what anyone will ask."""
        written = served_copy.write_stamp()
        assert set(written) >= {"commit", "dirty", "source_stamp", "token"}
        assert json.loads((copy_at / "build-stamp.json").read_text()) == written

    def test_an_unchanged_copy_passes(self, copy_at):
        """The ordinary run says nothing."""
        served_copy.write_stamp("the-token")
        served_copy.assert_unchanged("the-token", "measuring")

    def test_a_replaced_copy_names_both_builds(self, copy_at):
        """Which two builds the reading spans is the first question anyone asks."""
        served_copy.write_stamp("the-token")
        served_copy.write_stamp("another-token")
        with pytest.raises(SystemExit) as swap:
            served_copy.assert_unchanged("the-token", "finishing back.py")
        message = str(swap.value)
        assert "the-token" in message and "another-token" in message
        assert "finishing back.py" in message
        assert "B-256" in message

    def test_a_copy_that_lost_its_stamp_is_a_swap_too(self, copy_at):
        """A wiped copy must read as a swap, never as silence."""
        # No stamp is written at all: this is the copy a second session wiped
        # rather than replaced, and it must read as a swap and not as silence.
        with pytest.raises(SystemExit) as swap:
            served_copy.assert_unchanged("the-token", "measuring")
        assert "no stamp at all" in str(swap.value)

    def test_a_reader_that_started_without_a_stamp_says_nothing(self, copy_at):
        """A machine whose copy predates this file has nothing to compare."""
        served_copy.write_stamp("appeared-later")
        served_copy.assert_unchanged(None, "measuring")
