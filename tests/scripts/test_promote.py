"""Tests for scripts/promote.sh — the only way `main`, `staging` and `prod` move.

Every test builds its own origin: a bare repository in `tmp_path`, seeded with the
git flow's four branches, and a clone the script runs in. Nothing here reaches the
real origin. The GitHub reads (develop's required checks, a commit's pull request,
a head's check runs) and the backport's PR go through `GH`, pointed at a stub that
answers from a JSON file the test writes and records every call.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "promote.sh"

_REQUIRED = ["lint", "test"]

_GH_STUB = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["TM_TEST_GH_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
answers = json.load(open(os.environ["TM_TEST_GH"], encoding="utf-8"))
if args[:1] == ["api"]:
    path = args[1]
    if path in answers:
        print(json.dumps(answers[path]))
    elif path.endswith("/check-runs?per_page=100"):
        print(json.dumps({"check_runs": []}))
    else:
        print("[]")
elif args[:2] == ["pr", "create"]:
    print("https://github.test/pull/900")
"""


def _git(cwd: Path, *args: str) -> str:
    """Runs git in `cwd` and returns its stripped stdout.

    Args:
        cwd: The repository to run in.
        *args: The git arguments.

    Returns:
        The command's standard output, stripped.
    """
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=_git_env(cwd)
    ).stdout.strip()


def _git_env(cwd: Path) -> dict[str, str]:
    """An environment isolating git from the machine's own configuration.

    Args:
        cwd: Any path under the test's `tmp_path`; the global config sits beside it.

    Returns:
        The environment, with an identity and an empty global config.
    """
    root = next(p for p in [cwd, *cwd.parents] if (p / "gitconfig").exists())
    return {
        **os.environ,
        "GIT_CONFIG_GLOBAL": str(root / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }


class Flow:
    """A bare origin with `develop`, `main`, `staging`, `prod`, and the clones that write and promote."""

    def __init__(self, tmp_path: Path) -> None:
        """Seeds origin with one commit at version 0.1.0 on all four branches.

        Args:
            tmp_path: The test's scratch directory.
        """
        self.root = tmp_path
        (tmp_path / "gitconfig").write_text(
            "[init]\n\tdefaultBranch = develop\n[commit]\n\tgpgsign = false\n[tag]\n\tgpgsign = false\n",
            encoding="utf-8",
        )
        self.origin = tmp_path / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.origin)], check=True, env=_git_env(tmp_path))
        self.seed = tmp_path / "seed"
        subprocess.run(
            ["git", "clone", "-q", str(self.origin), str(self.seed)],
            check=True,
            capture_output=True,
            env=_git_env(tmp_path),
        )
        self.base = self.commit("develop", "0.1.0", "chore: seed")
        for branch in ("main", "staging", "prod"):
            _git(self.seed, "push", "-q", "origin", f"{self.base}:refs/heads/{branch}")
        self.work = tmp_path / "work"
        subprocess.run(
            ["git", "clone", "-q", str(self.origin), str(self.work)],
            check=True,
            capture_output=True,
            env=_git_env(tmp_path),
        )
        self.answers: dict[str, object] = {
            "repos/{owner}/{repo}/rules/branches/develop": [
                {"type": "deletion"},
                {
                    "type": "required_status_checks",
                    "parameters": {"required_status_checks": [{"context": c} for c in _REQUIRED]},
                },
            ]
        }
        self._next_pr = 100

    def commit(self, branch: str, version: str, message: str) -> str:
        """Commits a version on `branch` in the seed clone and pushes it.

        Args:
            branch: The branch to commit on (checked out from origin if needed).
            version: The `__version__` the commit carries.
            message: The commit subject.

        Returns:
            The new commit's SHA.
        """
        if self._has_head():
            _git(self.seed, "fetch", "-q", "origin")
            _git(self.seed, "checkout", "-q", "-B", branch, f"origin/{branch}")
        else:
            _git(self.seed, "checkout", "-q", "-b", branch)
        init = self.seed / "personalscraper" / "__init__.py"
        init.parent.mkdir(exist_ok=True)
        init.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
        (self.seed / f"{message.split(':')[0]}-{version}.txt").write_text(message, encoding="utf-8")
        _git(self.seed, "add", "-A")
        _git(self.seed, "commit", "-q", "-m", message)
        _git(self.seed, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
        return _git(self.seed, "rev-parse", "HEAD")

    def _has_head(self) -> bool:
        """Whether the seed clone has a first commit yet."""
        return (
            subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
                cwd=self.seed,
                capture_output=True,
                env=_git_env(self.seed),
            ).returncode
            == 0
        )

    def merged_pr(self, version: str, *, checks: str = "success") -> str:
        """Lands a commit on `develop` as a merged PR whose checks concluded `checks`.

        Args:
            version: The version the commit carries.
            checks: The conclusion every required check reports at the PR's head.

        Returns:
            The merge commit's SHA.
        """
        self._next_pr += 1
        number = self._next_pr
        sha = self.commit("develop", version, f"feat: change {version} (#{number})")
        head = f"head{number}"
        self.answers[f"repos/{{owner}}/{{repo}}/commits/{sha}/pulls"] = [
            {
                "number": number,
                "merge_commit_sha": sha,
                "merged_at": "2026-10-01T00:00:00Z",
                "base": {"ref": "develop"},
                "head": {"sha": head},
            }
        ]
        self.answers[f"repos/{{owner}}/{{repo}}/commits/{head}/check-runs?per_page=100"] = {
            "check_runs": [{"name": c, "conclusion": checks} for c in _REQUIRED]
        }
        return sha

    def tip(self, branch: str) -> str:
        """The SHA origin's `branch` points at, or "" when absent.

        Args:
            branch: A branch or a `refs/tags/...` name.

        Returns:
            The SHA, or an empty string.
        """
        ref = branch if branch.startswith("refs/") else f"refs/heads/{branch}"
        out = _git(self.origin, "ls-remote", str(self.origin), ref)
        return out.split()[0] if out else ""

    def promote(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Runs promote.sh in the work clone with the GH stub.

        Args:
            *args: The script's arguments.

        Returns:
            The finished process.
        """
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        stub = bin_dir / "gh"
        stub.write_text(_GH_STUB, encoding="utf-8")
        stub.chmod(0o755)
        answers = self.root / "gh.json"
        answers.write_text(json.dumps(self.answers), encoding="utf-8")
        env = {
            **_git_env(self.work),
            "GH": str(stub),
            "TM_TEST_GH": str(answers),
            "TM_TEST_GH_LOG": str(self.root / "gh.log"),
        }
        return subprocess.run(
            ["bash", str(_SCRIPT), *args], cwd=self.work, env=env, capture_output=True, text=True, timeout=60
        )

    def gh_calls(self) -> list[list[str]]:
        """Every call the GH stub received.

        Returns:
            One argument list per call.
        """
        log = self.root / "gh.log"
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


@pytest.fixture
def flow(tmp_path: Path) -> Flow:
    """A fresh origin with the four branches at one commit."""
    return Flow(tmp_path)


def _out(done: subprocess.CompletedProcess[str]) -> str:
    """Both streams of a finished run, for an assertion's message.

    Args:
        done: The finished process.

    Returns:
        Its stdout followed by its stderr.
    """
    return done.stdout + done.stderr


# ── the three promotions ─────────────────────────────────────────────────────


def test_main_fast_forwards_to_develop_when_every_pr_is_green(flow: Flow) -> None:
    """The merged, green PRs of develop reach main by a fast-forward to develop's tip."""
    flow.merged_pr("0.1.1")
    tip = flow.merged_pr("0.1.2")
    done = flow.promote("main")
    assert done.returncode == 0, _out(done)
    assert flow.tip("main") == tip
    assert "#101 #102" in done.stdout


def test_main_promotes_a_prefix_of_develop(flow: Flow) -> None:
    """An explicit commit promotes develop only up to it."""
    first = flow.merged_pr("0.1.1")
    flow.merged_pr("0.1.2")
    done = flow.promote("main", first)
    assert done.returncode == 0, _out(done)
    assert flow.tip("main") == first


def test_staging_fast_forwards_to_main(flow: Flow) -> None:
    """Staging follows main, and the output says how to read the deploy."""
    tip = flow.merged_pr("0.1.1")
    assert flow.promote("main").returncode == 0
    done = flow.promote("staging")
    assert done.returncode == 0, _out(done)
    assert flow.tip("staging") == tip
    assert "/api/version" in done.stdout


def test_prod_fast_forwards_to_staging_and_tags_the_version(flow: Flow) -> None:
    """Prod moves to staging's tip and carries the annotated tag v<__version__>."""
    tip = flow.merged_pr("0.1.1")
    assert flow.promote("main").returncode == 0
    assert flow.promote("staging").returncode == 0
    done = flow.promote("prod")
    assert done.returncode == 0, _out(done)
    assert flow.tip("prod") == tip
    assert _git(flow.origin, "rev-parse", "v0.1.1^{commit}") == tip
    assert _git(flow.origin, "cat-file", "-t", "v0.1.1") == "tag"


def test_tag_arm_tags_prods_tip(flow: Flow) -> None:
    """After a hotfix PR moved prod, `tag` tags its tip alone."""
    hotfix = flow.commit("prod", "0.1.0.1", "fix: urgent (#7)")
    done = flow.promote("tag")
    assert done.returncode == 0, _out(done)
    assert _git(flow.origin, "rev-parse", "v0.1.0.1^{commit}") == hotfix


def test_already_there_is_no_move(flow: Flow) -> None:
    """Promoting a branch to the commit it is at is said, not refused."""
    done = flow.promote("staging")
    assert done.returncode == 0, _out(done)
    assert "nothing to promote" in done.stdout


# ── the four refusals ────────────────────────────────────────────────────────


def test_rule_1_refuses_a_commit_not_on_the_source(flow: Flow) -> None:
    """Staging is promoted from main only: a commit only develop has is refused."""
    only_on_develop = flow.merged_pr("0.1.1")
    done = flow.promote("staging", only_on_develop)
    assert done.returncode == 1, _out(done)
    assert "not on origin/main" in done.stderr
    assert flow.tip("staging") == flow.base


def test_rule_2_refuses_what_is_not_a_fast_forward(flow: Flow) -> None:
    """A hotfix on prod not yet merged back makes staging's tip a non-fast-forward for prod."""
    flow.commit("prod", "0.1.0.1", "fix: urgent (#7)")
    hotfix = flow.tip("prod")
    tip = flow.merged_pr("0.1.1")
    assert flow.promote("main").returncode == 0
    assert flow.promote("staging").returncode == 0
    done = flow.promote("prod")
    assert done.returncode == 1, _out(done)
    assert "not a fast-forward" in done.stderr
    assert flow.tip("prod") == hotfix
    assert flow.tip("staging") == tip


def test_rule_3_refuses_a_commit_with_no_pr(flow: Flow) -> None:
    """A commit pushed onto develop past review is named and refused."""
    flow.merged_pr("0.1.1")
    flow.commit("develop", "0.1.2", "chore: pushed past review")
    done = flow.promote("main")
    assert done.returncode == 1, _out(done)
    assert "chore: pushed past review" in done.stderr
    assert flow.tip("main") == flow.base


def test_rule_3_refuses_a_pr_whose_checks_were_not_green(flow: Flow) -> None:
    """A PR merged with a required check failing at its head is refused, with the check named."""
    flow.merged_pr("0.1.1", checks="failure")
    done = flow.promote("main")
    assert done.returncode == 1, _out(done)
    assert "not green" in done.stderr and "lint" in done.stderr
    assert flow.tip("main") == flow.base


def test_rule_3_refuses_when_develop_requires_no_check(flow: Flow) -> None:
    """With no required check readable, nothing proves a PR passed: refuse, never pass vacuously."""
    flow.merged_pr("0.1.1")
    flow.answers["repos/{owner}/{repo}/rules/branches/develop"] = [{"type": "deletion"}]
    done = flow.promote("main")
    assert done.returncode == 1, _out(done)
    assert flow.tip("main") == flow.base


def test_rule_4_refuses_a_version_already_tagged(flow: Flow) -> None:
    """Prod refuses a commit whose version already has its release tag."""
    _git(flow.seed, "push", "-q", "origin", f"{flow.base}:refs/tags/v0.1.1")
    flow.merged_pr("0.1.1")
    assert flow.promote("main").returncode == 0
    assert flow.promote("staging").returncode == 0
    done = flow.promote("prod")
    assert done.returncode == 1, _out(done)
    assert "v0.1.1 already exists" in done.stderr
    assert flow.tip("prod") == flow.base


# ── dry run ──────────────────────────────────────────────────────────────────


def test_dry_run_pushes_nothing(flow: Flow) -> None:
    """--dry-run checks and tells, and leaves every ref of origin where it was."""
    flow.merged_pr("0.1.1")
    done = flow.promote("main", "--dry-run")
    assert done.returncode == 0, _out(done)
    assert "dry run" in done.stdout
    assert flow.tip("main") == flow.base
    _git(flow.seed, "push", "-q", "origin", f"{flow.tip('develop')}:refs/heads/staging")
    _git(flow.seed, "push", "-q", "origin", f"{flow.tip('develop')}:refs/heads/main")
    before = _git(flow.origin, "for-each-ref", "--format=%(refname) %(objectname)")
    done = flow.promote("prod", "--dry-run")
    assert done.returncode == 0, _out(done)
    assert "would tag" in done.stdout
    assert _git(flow.origin, "for-each-ref", "--format=%(refname) %(objectname)") == before


def test_dry_run_still_refuses(flow: Flow) -> None:
    """A dry run is a full reading: a refusal is a refusal."""
    flow.commit("develop", "0.1.1", "chore: pushed past review")
    done = flow.promote("main", "--dry-run")
    assert done.returncode == 1, _out(done)


# ── the hotfix's merge-back ──────────────────────────────────────────────────


def test_backport_pushes_prod_and_opens_a_merge_pr_into_develop(flow: Flow) -> None:
    """The tip of prod lands on backport/<name>; its PR targets develop, auto-merge by MERGE commit."""
    flow.merged_pr("0.1.1")
    hotfix = flow.commit("prod", "0.1.0.1", "fix: urgent (#7)")
    done = flow.promote("backport", "urgent")
    assert done.returncode == 0, _out(done)
    assert flow.tip("backport/urgent") == hotfix
    calls = flow.gh_calls()
    create = next(c for c in calls if c[:2] == ["pr", "create"])
    assert create[create.index("--base") + 1] == "develop"
    assert create[create.index("--head") + 1] == "backport/urgent"
    merge = next(c for c in calls if c[:2] == ["pr", "merge"])
    assert "--auto" in merge and "--merge" in merge and "--squash" not in merge


def test_backport_refuses_when_prod_is_already_on_develop(flow: Flow) -> None:
    """Nothing to bring back: no branch pushed, no PR opened."""
    done = flow.promote("backport", "nothing")
    assert done.returncode == 1, _out(done)
    assert flow.tip("backport/nothing") == ""
    assert not any(c[:1] == ["pr"] for c in flow.gh_calls())
