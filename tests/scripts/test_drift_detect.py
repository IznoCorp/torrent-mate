"""Tests for scripts/drift-detect.py (sub-phase 5.10.1).

Covers each check independently and one integration test that runs the
full script against a synthetic git tree.

Regression pin: drift-detect must catch IMPL.md SHAs that reference a
sub-phase commit instead of a phase-gate commit — this exact pattern
appeared in the real tech-debt tracker for phases 1 and 2 (e.g. the
``Phase 1 gate`` row pointing to a sub-phase fix commit subject like
``fix(tech-debt): _apply_pragmas helper (DEV #33)`` instead of the
``chore(tech-debt): phase 1 gate — ...`` commit).
"""

from __future__ import annotations

import importlib.util as _util
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the script under test (hyphen in filename → importlib).
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "drift-detect.py"

_spec = _util.spec_from_file_location("drift_detect", SCRIPT)
assert _spec is not None, f"Could not load spec from {SCRIPT}"
_mod = _util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["drift_detect"] = _mod
_spec.loader.exec_module(_mod)

check_impl_md_shas = _mod.check_impl_md_shas
check_acceptance_markers = _mod.check_acceptance_markers
check_plan_dev_coverage = _mod.check_plan_dev_coverage
check_plan_vs_phase_files = _mod.check_plan_vs_phase_files
check_xfail_audit = _mod.check_xfail_audit
check_ad_hoc_phases = _mod.check_ad_hoc_phases
run_all_checks = _mod.run_all_checks
main = _mod.main


# ---------------------------------------------------------------------------
# Synthetic git-repo helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    """Run a git command in *repo*, propagating failure.

    Args:
        repo: Repo working tree.
        *args: Git args.
        env: Optional env overrides (used for author identity).
    """
    base_env = os.environ.copy()
    base_env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            # Avoid signing in test envs.
            "GIT_CONFIG_GLOBAL": "/dev/null",
        }
    )
    if env:
        base_env.update(env)
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env=base_env,
    )


def _commit(repo: Path, message: str, *, filename: str | None = None) -> str:
    """Create a commit with *message* and return its short SHA.

    Args:
        repo: Working tree.
        message: Commit subject (no body).
        filename: File to touch/add. Auto-generated when not provided.

    Returns:
        7-char short SHA of the new commit.
    """
    target = repo / (filename or f"f-{message[:8].replace(' ', '_')}.txt")
    target.write_text(message + "\n", encoding="utf-8")
    _git(repo, "add", target.name)
    _git(repo, "commit", "-m", message)
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return out


def _init_repo(tmp_path: Path) -> Path:
    """Initialise a bare git repo at *tmp_path* and return its path."""
    repo = tmp_path
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    return repo


# ---------------------------------------------------------------------------
# Individual check tests
# ---------------------------------------------------------------------------


def test_impl_md_shas_detects_stale_sha(tmp_path: Path) -> None:
    """A SHA referenced in IMPL.md but absent from git log is flagged."""
    repo = _init_repo(tmp_path)
    real_sha = _commit(repo, "chore(tech-debt): phase 1 gate — foundations")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase            | File                    | Effort | Status        |\n"
        "| --- | ---------------- | ----------------------- | ------ | ------------- |\n"
        f"| 1   | Foundations      | phase-01-foundations.md | 1 j    | [x] `{real_sha}` |\n"
        "| 2   | CLI gaps         | phase-02-cli-gaps.md    | 1 j    | [x] `deadbee` |\n",
        encoding="utf-8",
    )
    findings = check_impl_md_shas(impl, repo)
    msgs = [f.message for f in findings]
    assert any("deadbee" in m and "does not exist" in m for m in msgs), msgs
    assert all("phase 1" not in m for m in msgs), msgs


def test_impl_md_shas_detects_non_gate_subject(tmp_path: Path) -> None:
    """A SHA pointing at a non-gate commit is flagged (regression pin)."""
    repo = _init_repo(tmp_path)
    sub_phase_sha = _commit(repo, "fix(tech-debt): _apply_pragmas helper (DEV #33, #34)")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase       | File                    | Effort | Status              |\n"
        "| --- | ----------- | ----------------------- | ------ | ------------------- |\n"
        f"| 1   | Foundations | phase-01-foundations.md | 1 j    | [x] gate `{sub_phase_sha}` |\n",
        encoding="utf-8",
    )
    findings = check_impl_md_shas(impl, repo)
    assert any("not a phase-gate commit" in f.message for f in findings)


def test_acceptance_markers_detects_missing_marker(tmp_path: Path) -> None:
    """ACC mentioned in IMPL.md without a status marker is flagged."""
    repo = _init_repo(tmp_path)
    _commit(repo, "chore: initial")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\nACC-01 was shipped during phase 1.\n",
        encoding="utf-8",
    )
    acc = repo / "ACCEPTANCE.md"
    acc.write_text(
        "# ACCEPTANCE\n\n### ACC-01 — Drift detection\n\nSome body without any status marker here.\n",
        encoding="utf-8",
    )
    findings = check_acceptance_markers(acc, impl, repo)
    assert any("ACC-01" in f.message for f in findings)


def test_acceptance_markers_recognises_shipped_marker(tmp_path: Path) -> None:
    """An ACC with ``[SHIPPED commit XXX]`` marker is NOT flagged."""
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "feat: ship ACC-02")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text("ACC-02 shipped.\n", encoding="utf-8")
    acc = repo / "ACCEPTANCE.md"
    acc.write_text(
        f"# ACCEPTANCE\n\n### ACC-02 — Some ACC\n\n[SHIPPED commit {sha}]\n",
        encoding="utf-8",
    )
    findings = check_acceptance_markers(acc, impl, repo)
    assert findings == []


def test_plan_dev_coverage_detects_missing_commit_ref(tmp_path: Path) -> None:
    """DEV in a complete phase without commit reference is flagged."""
    repo = _init_repo(tmp_path)
    _commit(repo, "chore(tech-debt): phase 1 gate — foundations")
    # Note: no commit references DEV #99.
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase       | File                    | Effort | Status |\n"
        "| --- | ----------- | ----------------------- | ------ | ------ |\n"
        "| 1   | Foundations | phase-01-foundations.md | 1 j    | [x]    |\n",
        encoding="utf-8",
    )
    index = repo / "plan-INDEX.md"
    index.write_text(
        "# Plan INDEX\n\n"
        "## DEV coverage matrix\n\n"
        "| DEV | Phase | Description |\n"
        "| --- | ----- | ----------- |\n"
        "| #99 | 1     | demo DEV    |\n",
        encoding="utf-8",
    )
    findings = check_plan_dev_coverage(index, impl, repo)
    assert any("DEV #99" in f.message for f in findings)


def test_plan_dev_coverage_skips_incomplete_phase(tmp_path: Path) -> None:
    """A DEV under an incomplete phase is NOT flagged."""
    repo = _init_repo(tmp_path)
    _commit(repo, "chore: init")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase       | File                    | Effort | Status |\n"
        "| --- | ----------- | ----------------------- | ------ | ------ |\n"
        "| 1   | Foundations | phase-01-foundations.md | 1 j    | [ ]    |\n",
        encoding="utf-8",
    )
    index = repo / "plan-INDEX.md"
    index.write_text(
        "## DEV coverage matrix\n\n| #99 | 1 | demo |\n",
        encoding="utf-8",
    )
    findings = check_plan_dev_coverage(index, impl, repo)
    assert findings == []


def test_plan_vs_phase_files_detects_missing_file(tmp_path: Path) -> None:
    """A phase file referenced by IMPL.md but absent on disk is flagged."""
    repo = _init_repo(tmp_path)
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase | File                       | Effort | Status |\n"
        "| --- | ----- | -------------------------- | ------ | ------ |\n"
        "| 1   | Foo   | phase-01-missing.md        | 1 j    | [ ]    |\n",
        encoding="utf-8",
    )
    plan_dir = repo / "plan"
    plan_dir.mkdir()
    findings = check_plan_vs_phase_files(impl, plan_dir)
    assert any("phase-01-missing.md" in f.message for f in findings)


def test_plan_vs_phase_files_passes_when_file_exists(tmp_path: Path) -> None:
    """The check is silent when every referenced phase file is on disk."""
    repo = _init_repo(tmp_path)
    plan_dir = repo / "plan"
    plan_dir.mkdir()
    (plan_dir / "phase-01-foo.md").write_text("ok\n", encoding="utf-8")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase | File             | Effort | Status |\n"
        "| --- | ----- | ---------------- | ------ | ------ |\n"
        "| 1   | Foo   | phase-01-foo.md  | 1 j    | [ ]    |\n",
        encoding="utf-8",
    )
    findings = check_plan_vs_phase_files(impl, plan_dir)
    assert findings == []


def test_xfail_audit_lists_xfailed_tests(tmp_path: Path) -> None:
    """Xfail decorators in test files surface as info findings."""
    repo = _init_repo(tmp_path)
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_xfail_demo.py").write_text(
        "import pytest\n\n@pytest.mark.xfail(reason='not implemented yet')\ndef test_demo():\n    assert False\n",
        encoding="utf-8",
    )
    findings = check_xfail_audit(repo)
    assert any(f.severity == "info" and "not implemented yet" in f.message for f in findings)


def test_ad_hoc_phases_detects_unlisted_phase(tmp_path: Path) -> None:
    """A commit mentioning a phase absent from IMPL.md is flagged."""
    repo = _init_repo(tmp_path)
    _commit(repo, "chore(tech-debt): phase 99 gate — surprise")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase | File             | Effort | Status |\n"
        "| --- | ----- | ---------------- | ------ | ------ |\n"
        "| 1   | Foo   | phase-01-foo.md  | 1 j    | [ ]    |\n",
        encoding="utf-8",
    )
    findings = check_ad_hoc_phases(impl, repo)
    assert any("phase 99" in f.message for f in findings)


def test_ad_hoc_phases_silent_when_subphase_status_mentions_it(
    tmp_path: Path,
) -> None:
    """A sub-phase tracked inside the parent row's status is NOT flagged."""
    repo = _init_repo(tmp_path)
    sha = _commit(repo, "fix(tech-debt): something for phase 5.10")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase  | File                     | Effort | Status            |\n"
        "| --- | ------ | ------------------------ | ------ | ----------------- |\n"
        f"| 5   | Conf   | phase-05-conformity.md   | 1 j    | [x] (5.10 `{sha}`) |\n",
        encoding="utf-8",
    )
    findings = check_ad_hoc_phases(impl, repo)
    assert findings == []


# ---------------------------------------------------------------------------
# Integration test — synthetic tree, full pipeline
# ---------------------------------------------------------------------------


def test_integration_full_report_on_synthetic_tree(tmp_path: Path) -> None:
    """Run the full ``run_all_checks`` against a controlled synthetic repo."""
    repo = _init_repo(tmp_path)

    # Commit 1: legitimate gate for phase 1.
    gate1_sha = _commit(repo, "chore(tech-debt): phase 1 gate — foundations")
    # Commit 2: a phase that won't be tracked (ad-hoc).
    _commit(repo, "chore(tech-debt): phase 42 gate — surprise")
    # Commit 3: DEV-bearing sub-phase commit.
    _commit(repo, "fix(tech-debt): DEV #1 fix (DEV #1)")

    # IMPLEMENTATION.md with a phase 1 gate row (correctly pointing to gate1_sha),
    # plus a phase 2 row pointing to a non-gate (commit 3) — this drift MUST fire.
    sub_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "# IMPLEMENTATION\n\n"
        "| #   | Phase       | File                    | Effort | Status                  |\n"
        "| --- | ----------- | ----------------------- | ------ | ----------------------- |\n"
        f"| 1   | Foundations | phase-01-foundations.md | 1 j    | [x] gate `{gate1_sha}` |\n"
        f"| 2   | CLI gaps    | phase-02-cli-gaps.md    | 1 j    | [x] gate `{sub_sha}`    |\n"
        "| 3   | Missing     | phase-03-missing.md     | 1 j    | [ ]                     |\n",
        encoding="utf-8",
    )
    # Acceptance with one ACC missing a marker that IMPL.md references.
    plan_dir = repo / "docs" / "features" / "tech-debt" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "phase-01-foundations.md").write_text("p1\n", encoding="utf-8")
    (plan_dir / "phase-02-cli-gaps.md").write_text("p2\n", encoding="utf-8")
    # phase-03-missing.md intentionally absent — must be flagged.
    (plan_dir / "INDEX.md").write_text(
        "# INDEX\n\n"
        "## DEV coverage matrix\n\n"
        "| DEV | Phase | Description |\n"
        "| --- | ----- | ----------- |\n"
        "| #1  | 1     | demo        |\n"
        "| #7  | 1     | uncovered   |\n",
        encoding="utf-8",
    )
    acceptance = repo / "docs" / "features" / "tech-debt" / "ACCEPTANCE.md"
    acceptance.write_text(
        "# ACCEPTANCE\n\n### ACC-01 — Drift detection\n\nNo status marker here.\n",
        encoding="utf-8",
    )
    # IMPL.md must reference ACC-01 for the marker drift to fire.
    with impl.open("a", encoding="utf-8") as fh:
        fh.write("\nACC-01 mentioned.\n")

    report = run_all_checks(repo)
    check_ids = {f.check for f in report.errors}
    # Every error-producing check should have fired.
    assert "IMPL_MD_SHAS" in check_ids, [f.message for f in report.errors]
    assert "ACCEPTANCE_MARKERS" in check_ids
    assert "PLAN_DEV_COVERAGE" in check_ids  # DEV #7 uncovered
    assert "PLAN_VS_PHASE_FILES" in check_ids
    assert "AD_HOC_PHASES" in check_ids


def test_main_quiet_strict_returns_nonzero_on_drift(tmp_path: Path) -> None:
    """``main(--strict --quiet)`` returns 1 when any drift is detected."""
    repo = _init_repo(tmp_path)
    _commit(repo, "chore: init")
    # IMPL.md references a non-existent SHA → forces drift.
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text(
        "| #   | Phase | File             | Effort | Status        |\n"
        "| --- | ----- | ---------------- | ------ | ------------- |\n"
        "| 1   | Foo   | phase-01-foo.md  | 1 j    | [x] `deadbee` |\n",
        encoding="utf-8",
    )
    plan_dir = repo / "docs" / "features" / "tech-debt" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "phase-01-foo.md").write_text("ok\n", encoding="utf-8")
    (plan_dir / "INDEX.md").write_text("# INDEX\n", encoding="utf-8")
    (repo / "docs" / "features" / "tech-debt" / "ACCEPTANCE.md").write_text("# ACC\n", encoding="utf-8")
    rc = main(["--repo", str(repo), "--strict", "--quiet"])
    assert rc == 1


def test_main_strict_clean_returns_zero(tmp_path: Path) -> None:
    """``main(--strict --quiet)`` returns 0 when no drifts are present."""
    repo = _init_repo(tmp_path)
    _commit(repo, "chore: init")
    impl = repo / "IMPLEMENTATION.md"
    impl.write_text("# IMPLEMENTATION\n", encoding="utf-8")
    plan_dir = repo / "docs" / "features" / "tech-debt" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "INDEX.md").write_text("# INDEX\n", encoding="utf-8")
    (repo / "docs" / "features" / "tech-debt" / "ACCEPTANCE.md").write_text("# ACC\n", encoding="utf-8")
    rc = main(["--repo", str(repo), "--strict", "--quiet"])
    assert rc == 0


def test_main_rejects_non_git_dir(tmp_path: Path) -> None:
    """``main`` exits 2 when --repo doesn't contain a .git directory."""
    rc = main(["--repo", str(tmp_path), "--quiet"])
    assert rc == 2


@pytest.mark.parametrize("flag", ["--json", "--quiet"])
def test_main_smoke_flag_combinations(tmp_path: Path, flag: str) -> None:
    """Sanity check: ``--json`` and ``--quiet`` do not raise on a clean tree."""
    repo = _init_repo(tmp_path)
    _commit(repo, "chore: init")
    plan_dir = repo / "docs" / "features" / "tech-debt" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "INDEX.md").write_text("# INDEX\n", encoding="utf-8")
    (repo / "docs" / "features" / "tech-debt" / "ACCEPTANCE.md").write_text("# ACC\n", encoding="utf-8")
    (repo / "IMPLEMENTATION.md").write_text("# IMPL\n", encoding="utf-8")
    rc = main(["--repo", str(repo), flag])
    assert rc == 0
