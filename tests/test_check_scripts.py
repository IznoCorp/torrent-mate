"""Tests for bin/check-pr-ready.sh and bin/check-merge-ready.sh (Phase 15.8).

Structural + env-guard + exit-code contract tests. No network — the scripts'
env-guard assertions (``: "${KANBAN_REPO:?}"`` / ``: "${KANBAN_BRANCH:?}"``)
are tested without ``gh`` on PATH.  The scripts now feed JSON via an _KM_JSON
env var (not stdin) so the heredoc-overrides-pipe bug is fixed — stub-gh tests
run on ALL platforms including macOS bash 3.2.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


# The gate scripts are shipped as kanbanmate PACKAGE DATA (defect 1, PoC ``_SKILL_ROOT``
# parity): a relative ``script:`` entry resolves against ``src/kanbanmate/`` so the gates
# are found regardless of which clone the daemon drives and survive clone re-creation. The
# tests read the canonical package copy (not a repo-root duplicate that could drift).
_PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "src" / "kanbanmate"
CHECK_PR_READY = _PACKAGE_ROOT / "bin" / "check-pr-ready.sh"
CHECK_MERGE_READY = _PACKAGE_ROOT / "bin" / "check-merge-ready.sh"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _clean_env() -> dict[str, str]:
    """Return os.environ stripped of every KANBAN_* variable.

    The returned dict still has PATH so bash and python3 can be found, but the
    ``: "${KANBAN_REPO:?}"`` / ``: "${KANBAN_BRANCH:?}"`` guards will fire.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("KANBAN_")}


# --------------------------------------------------------------------------- #
# Existence + executable bit
# --------------------------------------------------------------------------- #


def test_check_pr_ready_exists_and_executable() -> None:
    """The shipped check-pr-ready.sh must be present and chmod +x."""
    assert CHECK_PR_READY.exists(), f"{CHECK_PR_READY} is missing"
    assert os.access(CHECK_PR_READY, os.X_OK), f"{CHECK_PR_READY} is not executable"


def test_check_merge_ready_exists_and_executable() -> None:
    """The shipped check-merge-ready.sh must be present and chmod +x."""
    assert CHECK_MERGE_READY.exists(), f"{CHECK_MERGE_READY} is missing"
    assert os.access(CHECK_MERGE_READY, os.X_OK), f"{CHECK_MERGE_READY} is not executable"


# --------------------------------------------------------------------------- #
# Structural / content assertions (ported from PoC tests/cli/test_check_scripts.py)
# --------------------------------------------------------------------------- #


def test_check_pr_ready_has_shebang_and_pipefail() -> None:
    """The script must follow shell conventions: shebang + set -euo pipefail."""
    src = CHECK_PR_READY.read_text()
    assert src.startswith("#!/usr/bin/env bash"), "missing shebang"
    assert "set -euo pipefail" in src, "missing set -euo pipefail"


def test_check_merge_ready_has_shebang_and_pipefail() -> None:
    """The script must follow shell conventions: shebang + set -euo pipefail."""
    src = CHECK_MERGE_READY.read_text()
    assert src.startswith("#!/usr/bin/env bash"), "missing shebang"
    assert "set -euo pipefail" in src, "missing set -euo pipefail"


def test_check_pr_ready_uses_gh_not_merge() -> None:
    """Must use ``gh pr view``/``gh pr checks`` — never ``gh pr merge``."""
    src = CHECK_PR_READY.read_text()
    assert "gh pr view" in src or "gh pr checks" in src, (
        "check-pr-ready.sh does not reference gh pr view or gh pr checks"
    )
    assert "pr merge" not in src, (
        "check-pr-ready.sh must not call gh pr merge — it inspects, not merges"
    )


def test_check_merge_ready_uses_gh_not_merge() -> None:
    """Must use ``gh pr view``/``gh pr checks`` — never ``gh pr merge``."""
    src = CHECK_MERGE_READY.read_text()
    assert "gh pr view" in src or "gh pr checks" in src, (
        "check-merge-ready.sh does not reference gh pr view or gh pr checks"
    )
    assert "pr merge" not in src, (
        "check-merge-ready.sh must not call gh pr merge — it inspects, not merges"
    )


@pytest.mark.parametrize("script", [CHECK_PR_READY, CHECK_MERGE_READY])
def test_check_scripts_query_bucket_not_conclusion(script: Path) -> None:
    """Gate scripts must read the CI roll-up via ``bucket``, never the non-existent ``conclusion``.

    ``gh pr checks --json`` exposes no ``conclusion`` field (only ``bucket``/``state``/…); requesting
    it makes gh exit non-zero on every call, so a gate keyed on ``conclusion`` ALWAYS failed and
    stranded the card in PR/CI. This is a static regression guard for that engine bug.
    """
    # Ignore comment lines (which legitimately mention 'conclusion' to explain the fix); only the
    # operative shell/python code must be free of it.
    code = "\n".join(
        line for line in script.read_text().splitlines() if not line.lstrip().startswith("#")
    )
    assert "conclusion" not in code, (
        f"{script.name} uses 'conclusion' in code — gh pr checks has no such field; use 'bucket'"
    )
    assert "bucket" in code, f"{script.name} must read the CI verdict via the 'bucket' roll-up"


# --------------------------------------------------------------------------- #
# Env-guard assertions — scripts bail before calling gh, no stub needed
# --------------------------------------------------------------------------- #


def test_check_pr_ready_fails_without_kanban_repo() -> None:
    """Without KANBAN_REPO the ``:?`` guard fires → non-zero exit."""
    env = _clean_env()
    result = subprocess.run(
        [str(CHECK_PR_READY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0, (
        f"expected non-zero exit without KANBAN_REPO; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


def test_check_pr_ready_fails_without_kanban_branch() -> None:
    """With KANBAN_REPO but no KANBAN_BRANCH (and no KANBAN_PR) → non-zero exit."""
    env = {**_clean_env(), "KANBAN_REPO": "owner/repo"}
    result = subprocess.run(
        [str(CHECK_PR_READY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0, (
        f"expected non-zero exit with only KANBAN_REPO; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


def test_check_merge_ready_fails_without_kanban_repo() -> None:
    """Without KANBAN_REPO the ``:?`` guard fires → non-zero exit."""
    env = _clean_env()
    result = subprocess.run(
        [str(CHECK_MERGE_READY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0, (
        f"expected non-zero exit without KANBAN_REPO; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


def test_check_merge_ready_fails_without_kanban_branch() -> None:
    """With KANBAN_REPO but no KANBAN_BRANCH (and no KANBAN_PR) → non-zero exit."""
    env = {**_clean_env(), "KANBAN_REPO": "owner/repo"}
    result = subprocess.run(
        [str(CHECK_MERGE_READY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0, (
        f"expected non-zero exit with only KANBAN_REPO; got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


# --------------------------------------------------------------------------- #
# Stub gh tests — canned JSON, no network round-trip
# --------------------------------------------------------------------------- #


class TestStubGh:
    """Exit-code contract exercised with a stub ``gh`` on PATH.

    Each test writes a ``gh`` shim (chmod +x) into *tmp_path*, prepends it to
    ``PATH``, sets KANBAN_REPO + KANBAN_BRANCH, and asserts the expected exit
    code.  No network — the stub echoes canned JSON matching the real GitHub
    API shape.
    """

    # Canned fixtures covering every JSON field either check script inspects.
    _GREEN_PR_VIEW = (
        '{"number":1,"state":"OPEN",'
        '"url":"https://github.com/owner/repo/pull/1",'
        '"headRefName":"feat/test",'
        '"reviewDecision":"APPROVED","mergeStateStatus":"CLEAN",'
        '"reviews":[]}'
    )
    # Real ``gh pr checks --json`` shape: a ``bucket`` roll-up (pass/fail/pending/skipping/cancel)
    # + ``state`` — and NO ``conclusion`` field (the old stub invented one, masking the engine bug).
    _GREEN_CHECKS = '[{"name":"build","bucket":"pass","state":"SUCCESS"}]'

    @staticmethod
    def _write_gh_stub(
        tmp_path: Path,
        *,
        pr_view_json: str = _GREEN_PR_VIEW,
        pr_checks_json: str = _GREEN_CHECKS,
    ) -> Path:
        """Write a ``gh`` shell shim that echoes canned JSON for pr-view / pr-checks.

        Args:
            tmp_path: pytest temporary directory.
            pr_view_json: JSON string for ``gh pr view …``.
            pr_checks_json: JSON string for ``gh pr checks …``.

        Returns:
            Path to the shim (already chmod +x).
        """
        stub = tmp_path / "gh"
        stub.write_text(f"""#!/bin/sh
# Stub gh — never hits the network. Returns canned JSON for testing check scripts.
case "$1" in
  pr)
    case "$2" in
      view)  echo '{pr_view_json}' ;;
      checks)
        # Real gh validates --json fields and rejects unknown ones; ``conclusion`` is NOT a
        # ``pr checks`` field (regression guard: a script requesting it must fail the gate).
        case "$*" in
          *conclusion*) echo 'Unknown JSON field: "conclusion"' >&2; exit 1 ;;
        esac
        echo '{pr_checks_json}' ;;
      *) echo '{{}}' ;;
    esac
    ;;
  *) echo '{{}}' ;;
esac
exit 0
""")
        stub.chmod(0o755)
        return stub

    @staticmethod
    def _stub_env(tmp_path: Path) -> dict[str, str]:
        """Build a subprocess env with the stub ``gh`` on PATH + KANBAN_* vars."""
        return {
            **_clean_env(),
            "KANBAN_REPO": "owner/repo",
            "KANBAN_BRANCH": "feat/test",
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        }

    # -- Happy-path ----------------------------------------------------------

    def test_pr_ready_passes_with_green_ci(self, tmp_path: Path) -> None:
        """With a stub gh returning a green PR+CI, check-pr-ready exits 0."""
        self._write_gh_stub(tmp_path)
        env = self._stub_env(tmp_path)
        result = subprocess.run(
            [str(CHECK_PR_READY)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"expected exit 0 (green CI); got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_merge_ready_passes_when_approved_and_green(self, tmp_path: Path) -> None:
        """With a stub gh returning approved reviews + green CI, check-merge-ready exits 0."""
        self._write_gh_stub(tmp_path)
        env = self._stub_env(tmp_path)
        result = subprocess.run(
            [str(CHECK_MERGE_READY)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"expected exit 0 (approved + green); got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    # -- Failure-path ---------------------------------------------------------

    def test_pr_ready_fails_when_ci_not_green(self, tmp_path: Path) -> None:
        """With a stub gh returning a FAILURE check, check-pr-ready exits non-zero."""
        failing_checks = '[{"name":"build","bucket":"fail","state":"FAILURE"}]'
        self._write_gh_stub(tmp_path, pr_checks_json=failing_checks)
        env = self._stub_env(tmp_path)
        result = subprocess.run(
            [str(CHECK_PR_READY)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0, (
            f"expected non-zero exit (failing CI); got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_pr_ready_fails_when_ci_pending(self, tmp_path: Path) -> None:
        """A check still in the ``pending`` bucket (queued/running) must block the gate."""
        pending_checks = '[{"name":"build","bucket":"pending","state":"IN_PROGRESS"}]'
        self._write_gh_stub(tmp_path, pr_checks_json=pending_checks)
        env = self._stub_env(tmp_path)
        result = subprocess.run(
            [str(CHECK_PR_READY)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0, (
            f"expected non-zero exit (pending CI); got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_pr_ready_passes_when_no_checks_reported(self, tmp_path: Path) -> None:
        """A PR with NO CI checks configured passes with a recap note (defect 9 zero-checks policy).

        ``gh pr checks`` exits non-zero with "no checks reported" on a branch with no CI; the gate
        must treat that as GREEN (exit 0) so a checkless repo never strands the campaign in PR/CI —
        NOT as a real error.
        """
        # A custom gh stub: pr view succeeds (green PR), but `pr checks` exits non-zero with the
        # "no checks reported" message (the gh behaviour on a checkless branch).
        stub = tmp_path / "gh"
        stub.write_text(
            f"""#!/bin/sh
case "$1 $2" in
  "pr view")   echo '{self._GREEN_PR_VIEW}'; exit 0 ;;
  "pr checks") echo 'no checks reported on the feat/test branch' >&2; exit 1 ;;
  *) echo '{{}}'; exit 0 ;;
esac
"""
        )
        stub.chmod(0o755)
        env = self._stub_env(tmp_path)
        result = subprocess.run(
            [str(CHECK_PR_READY)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"expected exit 0 (no checks → zero-checks policy green); got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "zero-checks policy" in (result.stdout + result.stderr)

    def test_merge_ready_fails_when_changes_requested(self, tmp_path: Path) -> None:
        """With a stub gh returning CHANGES_REQUESTED, check-merge-ready exits non-zero."""
        changes_pr_view = self._GREEN_PR_VIEW.replace(
            '"reviewDecision":"APPROVED"',
            '"reviewDecision":"CHANGES_REQUESTED"',
        )
        self._write_gh_stub(tmp_path, pr_view_json=changes_pr_view)
        env = self._stub_env(tmp_path)
        result = subprocess.run(
            [str(CHECK_MERGE_READY)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0, (
            f"expected non-zero exit (CHANGES_REQUESTED); got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
