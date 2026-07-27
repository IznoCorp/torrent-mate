"""Unit tests for the ``prime`` command in the acquisition runner.

(acq-states phase 6.1 — failing-first).

Targets the runner seams:

- ``_build_argv('prime', id)`` — must yield the three-step sequence (detect →
  search → grab) instead of a single grab argv.
- ``_read_mandatory_env`` — must accept ``PERSONALSCRAPER_ACQ_COMMAND=prime``
  as a valid command and require ``PERSONALSCRAPER_GRAB_FOLLOWED_ID``.

INTENTIONALLY FAILING — the ``prime`` command is rejected today. The runner
only knows ``grab`` and ``detect``; ``_build_argv`` has no ``prime`` branch.
"""

from __future__ import annotations

import os
import sys

import pytest

from personalscraper.web.acquisition.runner import _build_argv, _read_mandatory_env


def _clear_runner_env() -> None:
    """Remove the acquisition-runner env vars between tests."""
    for k in (
        "PERSONALSCRAPER_RUN_UID",
        "PERSONALSCRAPER_ACQ_COMMAND",
        "PERSONALSCRAPER_GRAB_FOLLOWED_ID",
    ):
        os.environ.pop(k, None)


# ---------------------------------------------------------------------------
# Tests — _build_argv for the prime command
# ---------------------------------------------------------------------------


class TestBuildArgvPrime:
    """``_build_argv('prime', id)`` yields the three-step priming sequence."""

    def test_three_step_sequence(self) -> None:
        """The prime argv is three CLIs: detect → search → grab.

        Each step targets ONLY the followed series (never a global pass).
        The steps are returned as a list of argv lists so the runner can
        iterate and stop at the first non-zero exit code.
        """
        result = _build_argv("prime", 42)

        # Must return a list of three argvs, not a flat list.
        assert isinstance(result, list), f"Expected list, got {type(result).__name__}"
        assert len(result) == 3, f"Expected 3 steps, got {len(result)}"

        argv0: list[str] = result[0]
        argv1: list[str] = result[1]
        argv2: list[str] = result[2]

        # Step 1: personalscraper follow detect --series {id}
        assert argv0[:4] == [sys.executable, "-m", "personalscraper", "follow"], (
            f"Step 1 prefix mismatch: {argv0[:4]!r}"
        )
        assert "detect" in argv0, f"Step 1 missing 'detect': {argv0}"
        assert "--series" in argv0, f"Step 1 missing '--series': {argv0}"
        assert any(str(42) in a for a in argv0), f"Step 1 missing '42': {argv0}"

        # Step 2: personalscraper search --followed-id {id}
        assert argv1[:4] == [sys.executable, "-m", "personalscraper", "search"], (
            f"Step 2 prefix mismatch: {argv1[:4]!r}"
        )
        assert "--followed-id" in argv1, f"Step 2 missing '--followed-id': {argv1}"
        assert "42" in argv1, f"Step 2 missing '42': {argv1}"

        # Step 3: personalscraper grab --followed-id {id}
        assert argv2[:4] == [sys.executable, "-m", "personalscraper", "grab"], f"Step 3 prefix mismatch: {argv2[:4]!r}"
        assert "--followed-id" in argv2, f"Step 3 missing '--followed-id': {argv2}"
        assert "42" in argv2, f"Step 3 missing '42': {argv2}"

    def test_prime_falls_through_to_grab_today(self) -> None:
        """DOCUMENT the current broken state: 'prime' maps to the grab argv.

        This test is the gap the 6.2 implementation must close. Once
        ``_build_argv`` gains the ``prime`` branch, remove this test — it
        exists only to prove the failing-first gate is real.
        """
        result = _build_argv("prime", 42)

        # Today, 'prime' falls through to the grab branch — a single flat argv
        # that starts [sys.executable, -m, personalscraper, grab, ...].
        is_flat_grab = isinstance(result, list) and len(result) > 3 and result[3] == "grab"
        assert is_flat_grab, (
            "Expected 'prime' to fall through to the grab branch (current behaviour). "
            "Once 6.2 is implemented, this state should no longer hold — remove this "
            "test or flip the assertion."
        )


# ---------------------------------------------------------------------------
# Tests — env contract for the prime command
# ---------------------------------------------------------------------------


class TestEnvContractPrime:
    """The env contract accepts ``prime`` as a valid command."""

    def test_prime_is_valid_command(self) -> None:
        """_read_mandatory_env accepts PERSONALSCRAPER_ACQ_COMMAND=prime."""
        _clear_runner_env()
        os.environ["PERSONALSCRAPER_RUN_UID"] = "test-uid-prime-1"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "prime"
        os.environ["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] = "42"
        try:
            run_uid, command, followed_id = _read_mandatory_env()
            assert run_uid == "test-uid-prime-1"
            assert command == "prime", f"Expected 'prime', got {command!r}"
            assert followed_id == 42, f"Expected 42, got {followed_id!r}"
        finally:
            _clear_runner_env()

    def test_prime_rejected_as_unknown_today(self) -> None:
        """DOCUMENT the current broken state: 'prime' exits 2 as unknown.

        This test is the gap the 6.2 implementation must close. Once
        ``_read_mandatory_env`` accepts ``prime``, remove this test.
        """
        _clear_runner_env()
        os.environ["PERSONALSCRAPER_RUN_UID"] = "test-uid-prime-2"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "prime"
        os.environ["PERSONALSCRAPER_GRAB_FOLLOWED_ID"] = "42"
        try:
            with pytest.raises(SystemExit) as exc_info:
                _read_mandatory_env()
            assert exc_info.value.code == 2, (
                "Today 'prime' IS rejected with exit code 2. Once 6.2 is "
                "implemented, this SystemExit should no longer fire — remove "
                "this test or flip the assertion."
            )
        finally:
            _clear_runner_env()

    def test_prime_requires_followed_id(self) -> None:
        """A prime run without PERSONALSCRAPER_GRAB_FOLLOWED_ID exits 2.

        The followed_id is mandatory for prime (same as grab): three CLIs
        all need it. This test will fail UNTIL the env contract is updated
        in 6.2 to check for 'prime' alongside 'grab'.
        """
        _clear_runner_env()
        os.environ["PERSONALSCRAPER_RUN_UID"] = "test-uid-prime-3"
        os.environ["PERSONALSCRAPER_ACQ_COMMAND"] = "prime"
        # Deliberately omit PERSONALSCRAPER_GRAB_FOLLOWED_ID.
        try:
            with pytest.raises(SystemExit) as exc_info:
                _read_mandatory_env()
            assert exc_info.value.code == 2, (
                "Missing PERSONALSCRAPER_GRAB_FOLLOWED_ID must exit 2 for the prime command"
            )
        finally:
            _clear_runner_env()
