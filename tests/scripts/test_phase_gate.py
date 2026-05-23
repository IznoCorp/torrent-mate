"""Tests for scripts/phase-gate.sh (sub-phase 5.10.2).

Invokes the bash script in synthetic temp-git repos to verify:
- Detects commits in the current phase range correctly.
- Idempotent on an already-gated phase.
- Invokes drift-detect (or silently skips when unavailable).
- Skips (exits 0) when no new commits exist for the phase.
- Gate commit is created with the correct subject format.
- IMPL.md row is updated with the real SHA.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Script under test.
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "phase-gate.sh"

# ---------------------------------------------------------------------------
# Synthetic git-repo helpers.
# ---------------------------------------------------------------------------

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


def _git(repo: Path, *args: str) -> str:
    """Run a git command in *repo* and return stdout.

    Args:
        repo: Working tree.
        *args: git arguments.

    Returns:
        Stripped stdout string.

    Raises:
        subprocess.CalledProcessError: On non-zero exit.
    """
    env = {**os.environ, **_GIT_ENV}
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str, *, filename: str | None = None) -> str:
    """Touch a file, stage it, and create a commit. Return short SHA.

    Args:
        repo: Working tree.
        message: Commit message.
        filename: File to create (auto-generated when omitted).

    Returns:
        7-char short SHA.
    """
    name = filename or f"f_{len(list(repo.iterdir()))}.txt"
    (repo / name).write_text(message + "\n", encoding="utf-8")
    _git(repo, "add", name)
    env = {**os.environ, **_GIT_ENV}
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", message],
        check=True,
        capture_output=True,
        env=env,
    )
    return _git(repo, "rev-parse", "--short", "HEAD")


def _init_repo(path: Path) -> Path:
    """Initialise a git repo at *path* with minimal required structure.

    Args:
        path: Directory to initialise.

    Returns:
        Same *path* (for chaining).
    """
    path.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **_GIT_ENV}
    subprocess.run(
        ["git", "-C", str(path), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
        env=env,
    )
    return path


def _commit_all(repo: Path, message: str) -> str:
    """Stage all changes (tracked + untracked) and create a commit.

    Args:
        repo: Working tree.
        message: Commit message.

    Returns:
        7-char short SHA.
    """
    env = {**os.environ, **_GIT_ENV}
    subprocess.run(
        ["git", "-C", str(repo), "add", "-A"],
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", message],
        check=True,
        capture_output=True,
        env=env,
    )
    return _git(repo, "rev-parse", "--short", "HEAD")


def _make_impl_md(
    repo: Path,
    phases: list[dict[str, str]],
    *,
    extra_content: str = "",
) -> Path:
    """Write a minimal IMPLEMENTATION.md with a phases table.

    Args:
        repo: Repository root.
        phases: List of row dicts with keys: num, title, file, effort, status.
        extra_content: Additional text appended after the table.

    Returns:
        Path to the created IMPLEMENTATION.md.
    """
    rows = [
        "| #   | Phase       | File               | Effort | Status |",
        "| --- | ----------- | ------------------ | ------ | ------ |",
    ]
    for p in phases:
        row = (
            f"| {p['num']} | {p.get('title', 'Phase')} "
            f"| {p.get('file', 'phase-XX.md')} "
            f"| {p.get('effort', '1 j')} "
            f"| {p.get('status', '[ ]')} |"
        )
        rows.append(row)
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# Implementation\n\n" + "\n".join(rows) + "\n" + extra_content,
        encoding="utf-8",
    )
    return impl


def _make_acceptance_md(repo: Path, content: str = "") -> Path:
    """Write a minimal ACCEPTANCE.md.

    Args:
        repo: Repository root.
        content: File body (after the header).

    Returns:
        Path to the created file.
    """
    acc_dir = repo / "docs" / "features" / "tech-debt"
    acc_dir.mkdir(parents=True, exist_ok=True)
    acc_file = acc_dir / "ACCEPTANCE.md"
    acc_file.write_text(
        "# ACCEPTANCE\n\n" + content,
        encoding="utf-8",
    )
    return acc_file


def _run_phase_gate(
    repo: Path,
    phase_num: str | int,
    *,
    extra_env: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Invoke phase-gate.sh in *repo* for *phase_num* (non-interactive via pipe).

    Passes ``echo y`` via stdin to confirm the prompt automatically.

    Args:
        repo: Repository root.
        phase_num: Phase number argument for the script.
        extra_env: Additional env vars to merge.
        timeout: Max seconds to wait.

    Returns:
        CompletedProcess with stdout, stderr, returncode.
    """
    env = {**os.environ, **_GIT_ENV}
    if extra_env:
        env.update(extra_env)
    # Feed "y\n" to auto-confirm the prompt; non-interactive detection in script
    # auto-proceeds when stdin is not a tty (pipe).
    result = subprocess.run(
        ["bash", str(SCRIPT), str(phase_num)],
        cwd=str(repo),
        input="y\n",
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPhaseGateBasicFlow:
    """Happy-path: script creates a gate commit and updates IMPL.md."""

    def test_gate_commit_created(self, tmp_path: Path) -> None:
        """Running the script creates a gate commit with the correct message format."""
        repo = _init_repo(tmp_path)
        # Bootstrap with an initial commit so HEAD exists.
        _commit(repo, "chore: initial setup")

        # Phase 5 previous gate.
        _commit(repo, "chore(tech-debt): phase 4 gate — path cleanup", filename="gate4.txt")

        # Phase 5 work commits.
        _commit(repo, "feat(tech-debt): add library-gc CLI (SH-7)", filename="w1.txt")
        _commit(repo, "refactor(tech-debt): drop monolithic Protocols (DEV #38)", filename="w2.txt")

        # Write IMPL.md with phase 5 as ungated.
        _make_impl_md(
            repo,
            phases=[
                {
                    "num": "4",
                    "title": "Path cleanup",
                    "file": "phase-04.md",
                    "effort": "1 j",
                    "status": "[x] gate `abc1234`",
                },
                {"num": "5", "title": "Conformity", "file": "phase-05.md", "effort": "2 j", "status": "[ ]"},
            ],
        )
        _make_acceptance_md(repo)

        # Initial commit for IMPL.md and ACCEPTANCE.md.
        _commit_all(repo, "docs: add IMPLEMENTATION and ACCEPTANCE")

        result = _run_phase_gate(repo, 5)

        assert result.returncode == 0, f"exit {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"

        # Check a gate commit was created.
        log = _git(repo, "log", "--pretty=format:%s", "-5")
        gate_subjects = [line for line in log.splitlines() if "phase 5 gate" in line]
        assert gate_subjects, f"No gate commit found. Log:\n{log}"

    def test_impl_md_updated_with_sha(self, tmp_path: Path) -> None:
        """IMPL.md row for phase N shows [x] gate with a real SHA after the script."""
        repo = _init_repo(tmp_path)
        _commit(repo, "chore: initial")
        _commit(repo, "feat(tech-debt): add library-gc CLI (SH-7)", filename="w1.txt")

        _make_impl_md(
            repo,
            phases=[
                {"num": "6", "title": "Format docs", "file": "phase-06.md", "effort": "3 j", "status": "[ ]"},
            ],
        )
        _make_acceptance_md(repo)
        _commit_all(repo, "docs: add impl and acceptance")

        result = _run_phase_gate(repo, 6)
        assert result.returncode == 0, result.stderr

        impl_content = (repo / "IMPLEMENTATION.md").read_text(encoding="utf-8")
        # Should have [x] and a backtick-wrapped SHA (7+ hex chars).
        import re

        gate_pattern = re.compile(r"\[x\].*gate.*`[0-9a-f]{7,}`")
        assert gate_pattern.search(impl_content), f"[x] gate `<sha>` not found in IMPL.md:\n{impl_content}"
        # No placeholder left.
        assert "__GATE_SHA__" not in impl_content


class TestIdempotence:
    """Already-gated phase exits 0 without creating a new commit."""

    def test_already_gated_exits_clean(self, tmp_path: Path) -> None:
        """When IMPL.md already has [x] gate `<sha>`, the script exits 0 immediately."""
        repo = _init_repo(tmp_path)
        _commit(repo, "chore: initial")
        gate_sha = _commit(repo, "chore(tech-debt): phase 3 gate — observability", filename="gate3.txt")

        _make_impl_md(
            repo,
            phases=[
                {
                    "num": "3",
                    "title": "Observability",
                    "file": "phase-03.md",
                    "effort": "2 j",
                    "status": f"[x] gate `{gate_sha}`",
                },
            ],
        )
        _make_acceptance_md(repo)
        _commit_all(repo, "docs: add impl")

        commit_count_before = len(_git(repo, "log", "--oneline").splitlines())

        result = _run_phase_gate(repo, 3)

        assert result.returncode == 0, result.stderr
        assert "already gated" in result.stdout.lower(), result.stdout

        commit_count_after = len(_git(repo, "log", "--oneline").splitlines())
        assert commit_count_before == commit_count_after, "Expected no new commits for already-gated phase"

    def test_idempotent_without_sha_present(self, tmp_path: Path) -> None:
        """Already-gated detection requires a backtick SHA — a bare [x] triggers the gate."""
        repo = _init_repo(tmp_path)
        _commit(repo, "chore: initial")
        _commit(repo, "feat(tech-debt): something for phase 2", filename="w.txt")

        # Row has [x] but NO sha — should still proceed to create a gate.
        _make_impl_md(
            repo,
            phases=[
                {"num": "2", "title": "CLI gaps", "file": "phase-02.md", "effort": "2 j", "status": "[x] (no sha yet)"},
            ],
        )
        _make_acceptance_md(repo)
        _commit_all(repo, "docs: add impl")

        result = _run_phase_gate(repo, 2)
        # The script should NOT say "already gated" — it proceeds (or at least exits 0).
        assert result.returncode == 0, result.stderr
        assert "already gated" not in result.stdout.lower(), (
            "Bare [x] without SHA should not be treated as already-gated"
        )


class TestNoCommits:
    """When there are no new commits in range, the script exits 0 gracefully."""

    def test_no_commits_in_range(self, tmp_path: Path) -> None:
        """Exits 0 with a message when no commits exist for the requested phase."""
        repo = _init_repo(tmp_path)
        _commit(repo, "chore: initial")

        # Write IMPL.md + ACCEPTANCE.md BEFORE the gate commit so they don't
        # appear as phase-6 work commits.
        _make_impl_md(
            repo,
            phases=[
                {"num": "5", "title": "Conformity", "file": "phase-05.md", "effort": "2 j", "status": "[ ]"},
                {"num": "6", "title": "Format", "file": "phase-06.md", "effort": "3 j", "status": "[ ]"},
            ],
        )
        _make_acceptance_md(repo)
        _commit_all(repo, "docs: add impl and acceptance")

        # Phase 5 gate — no commits after this one for phase 6.
        _commit(repo, "chore(tech-debt): phase 5 gate — conformity", filename="gate5.txt")

        result = _run_phase_gate(repo, 6)
        assert result.returncode == 0, f"exit {result.returncode}\n{result.stderr}"
        assert "nothing to gate" in result.stdout.lower(), result.stdout


class TestDriftDetectInvocation:
    """drift-detect integration: script runs it and surfaces findings."""

    def test_drift_detect_section_appears(self, tmp_path: Path) -> None:
        """The drift-detect section is present in output (even if detect is unavailable)."""
        repo = _init_repo(tmp_path)
        _commit(repo, "chore: initial")
        _commit(repo, "feat(tech-debt): add something for phase 7", filename="w.txt")

        _make_impl_md(
            repo,
            phases=[
                {"num": "7", "title": "Matrix", "file": "phase-07.md", "effort": "2 j", "status": "[ ]"},
            ],
        )
        _make_acceptance_md(repo)
        _commit_all(repo, "docs: impl")

        result = _run_phase_gate(repo, 7)
        assert result.returncode == 0, result.stderr
        # The drift-detect section header should appear in output.
        assert "drift-detect" in result.stdout.lower(), f"drift-detect section missing from output:\n{result.stdout}"


class TestCommitRangeDetection:
    """The script correctly identifies commits belonging to the requested phase."""

    def test_commits_after_prev_gate_are_in_range(self, tmp_path: Path) -> None:
        """Commits after the previous gate commit appear in the phase summary."""
        repo = _init_repo(tmp_path)
        _commit(repo, "chore: initial")
        _commit(repo, "chore(tech-debt): phase 1 gate — foundations", filename="gate1.txt")
        # Phase 2 work.
        _commit(repo, "feat(tech-debt): library-gc CLI (DEV #22)", filename="phase2_work.txt")

        _make_impl_md(
            repo,
            phases=[
                {
                    "num": "1",
                    "title": "Foundations",
                    "file": "phase-01.md",
                    "effort": "3 j",
                    "status": "[x] gate `abc1234`",
                },
                {"num": "2", "title": "CLI gaps", "file": "phase-02.md", "effort": "2 j", "status": "[ ]"},
            ],
        )
        _make_acceptance_md(repo)
        _commit_all(repo, "docs: impl")

        result = _run_phase_gate(repo, 2)
        assert result.returncode == 0, result.stderr
        # The phase 2 work commit should appear in the output.
        assert "library-gc" in result.stdout, f"Phase 2 work commit not in output:\n{result.stdout}"


class TestArgumentValidation:
    """Bad arguments are rejected with a non-zero exit."""

    def test_no_arg_exits_nonzero(self, tmp_path: Path) -> None:
        """Calling without arguments exits 1."""
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0

    def test_non_integer_phase_exits_nonzero(self, tmp_path: Path) -> None:
        """Calling with a non-integer phase number exits 1."""
        repo = _init_repo(tmp_path)
        _commit(repo, "chore: initial")

        result = subprocess.run(
            ["bash", str(SCRIPT), "5.10"],
            cwd=str(repo),
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0, "Non-integer phase should fail but it didn't"
