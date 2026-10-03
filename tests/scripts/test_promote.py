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
elif args[:2] == ["pr", "merge"] and answers.get("refuse_merge"):
    sys.exit(1)
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

    def commit(self, branch: str, version: str, message: str, files: dict[str, str] | None = None) -> str:
        """Commits a version on `branch` in the seed clone and pushes it.

        Args:
            branch: The branch to commit on (checked out from origin if needed).
            version: The `__version__` the commit carries.
            message: The commit subject.
            files: Other files the commit writes, path to content.

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
        for path, content in (files or {}).items():
            (self.seed / path).write_text(content, encoding="utf-8")
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


@pytest.mark.parametrize(
    ("field", "value"),
    [(("base", "ref"), "prod"), (("merged_at",), None)],
    ids=["pr-into-prod", "pr-not-merged"],
)
def test_rule_3_refuses_a_commit_whose_pr_is_not_a_merge_into_develop(
    flow: Flow, field: tuple[str, ...], value: object
) -> None:
    """The commit's PR must be MERGED into `develop`: one into another base, or closed unmerged, proves nothing."""
    sha = flow.merged_pr("0.1.1")
    pull = flow.answers[f"repos/{{owner}}/{{repo}}/commits/{sha}/pulls"][0]  # type: ignore[index]
    target = pull
    for key in field[:-1]:
        target = target[key]
    target[field[-1]] = value
    done = flow.promote("main")
    assert done.returncode == 1, _out(done)
    assert "is no merged PR into develop" in done.stderr
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


def test_rule_4_names_the_release_bump(flow: Flow) -> None:
    """A PR leaves the version alone: a released version is raised by `release`, which the refusal names."""
    flow.merged_pr("0.1.1")
    assert flow.promote("main").returncode == 0
    assert flow.promote("staging").returncode == 0
    assert flow.promote("prod").returncode == 0
    flow.merged_pr("0.1.1")
    assert flow.promote("main").returncode == 0
    assert flow.promote("staging").returncode == 0
    done = flow.promote("prod")
    assert done.returncode == 1, _out(done)
    assert "run scripts/promote.sh release" in done.stderr


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
    """Prod's tip, merged with develop, lands on backport/<name>; its PR targets develop, auto-merge by MERGE commit."""
    develop = flow.merged_pr("0.1.1")
    hotfix = flow.commit("prod", "0.1.0.1", "fix: urgent (#7)")
    done = flow.promote("backport", "urgent")
    assert done.returncode == 0, _out(done)
    assert "auto-merge armed" in done.stdout
    backport = flow.tip("backport/urgent")
    assert _git(flow.origin, "rev-parse", f"{backport}^1", f"{backport}^2").split() == [hotfix, develop]
    calls = flow.gh_calls()
    create = next(c for c in calls if c[:2] == ["pr", "create"])
    assert create[create.index("--base") + 1] == "develop"
    assert create[create.index("--head") + 1] == "backport/urgent"
    merge = next(c for c in calls if c[:2] == ["pr", "merge"])
    assert "--auto" in merge and "--merge" in merge and "--squash" not in merge


def test_backport_resolves_the_version_conflict_to_develops_version(flow: Flow) -> None:
    """Prod's X.Y.Z.1 against develop's X.Y.(Z+n): the branch carries develop's version as it is, and the hotfix."""
    flow.merged_pr("0.1.4")
    flow.commit("prod", "0.1.0.1", "fix: urgent (#7)")
    done = flow.promote("backport", "urgent")
    assert done.returncode == 0, _out(done)
    backport = flow.tip("backport/urgent")
    init = _git(flow.origin, "show", f"{backport}:personalscraper/__init__.py")
    assert init == '__version__ = "0.1.4"'
    assert _git(flow.origin, "show", f"{backport}:fix-0.1.0.1.txt") == "fix: urgent (#7)"
    assert _git(flow.origin, "show", f"{backport}:feat-0.1.4.txt") == "feat: change 0.1.4 (#101)"
    assert len(_git(flow.work, "worktree", "list").splitlines()) == 1


def test_backport_refuses_any_other_conflict_and_pushes_nothing(flow: Flow) -> None:
    """A conflict beyond `__version__` is the hand's: no branch, no PR, the file named."""
    flow.commit("develop", "0.1.1", "feat: a (#101)", files={"shared.txt": "develop's\n"})
    flow.commit("prod", "0.1.0.1", "fix: b (#7)", files={"shared.txt": "prod's\n"})
    done = flow.promote("backport", "urgent")
    assert done.returncode == 1, _out(done)
    assert "shared.txt" in done.stderr
    assert flow.tip("backport/urgent") == ""
    assert len(_git(flow.work, "worktree", "list").splitlines()) == 1
    assert not any(c[:1] == ["pr"] for c in flow.gh_calls())


def test_backport_says_when_arming_auto_merge_failed(flow: Flow) -> None:
    """The PR is open but not armed: said with its number and a non-zero exit, never « armed »."""
    flow.merged_pr("0.1.1")
    flow.commit("prod", "0.1.0.1", "fix: urgent (#7)")
    flow.answers["refuse_merge"] = True
    done = flow.promote("backport", "urgent")
    assert done.returncode == 1, _out(done)
    assert "armed" not in done.stdout
    assert "pull/900" in done.stderr and "backport/urgent" in done.stderr
    assert flow.tip("backport/urgent") != ""


def test_backport_refuses_when_prod_is_already_on_develop(flow: Flow) -> None:
    """Nothing to bring back: no branch pushed, no PR opened."""
    done = flow.promote("backport", "nothing")
    assert done.returncode == 1, _out(done)
    assert flow.tip("backport/nothing") == ""
    assert not any(c[:1] == ["pr"] for c in flow.gh_calls())


def test_rule_3_counts_a_skipped_check_as_github_does(flow: Flow) -> None:
    """A required check skipped at the head (harness-full off the maquette) passes, as on GitHub."""
    flow.merged_pr("0.1.1", checks="skipped")
    done = flow.promote("main")
    assert done.returncode == 0, _out(done)


def test_rule_3_refuses_a_required_check_that_never_ran(flow: Flow) -> None:
    """A required check absent from the head's runs proves nothing: refused."""
    sha = flow.merged_pr("0.1.1")
    head = flow.answers[f"repos/{{owner}}/{{repo}}/commits/{sha}/pulls"][0]["head"]["sha"]  # type: ignore[index]
    flow.answers[f"repos/{{owner}}/{{repo}}/commits/{head}/check-runs?per_page=100"] = {
        "check_runs": [{"name": "lint", "conclusion": "success"}]
    }
    done = flow.promote("main")
    assert done.returncode == 1, _out(done)
    assert "not green at its head: test" in done.stderr


def _check_runs(flow: Flow, sha: str, runs: list[dict[str, object]]) -> None:
    """Replaces the check runs GitHub reports at the head of the PR that merged `sha`.

    Args:
        flow: The flow under test.
        sha: The merge commit of the PR.
        runs: The check runs to report, each with `name`, `conclusion`, `completed_at`, `id`.
    """
    head = flow.answers[f"repos/{{owner}}/{{repo}}/commits/{sha}/pulls"][0]["head"]["sha"]  # type: ignore[index]
    flow.answers[f"repos/{{owner}}/{{repo}}/commits/{head}/check-runs?per_page=100"] = {"check_runs": runs}


def _runs(name: str, *conclusions: str) -> list[dict[str, object]]:
    """Successive runs of one check, oldest first, as GitHub lists them (newest first).

    Args:
        name: The check's name.
        *conclusions: The conclusion of each run, oldest first.

    Returns:
        The runs, newest first, each completed a minute after the previous one.
    """
    runs: list[dict[str, object]] = [
        {"name": name, "conclusion": c, "completed_at": f"2026-10-01T00:0{i}:00Z", "id": 1000 + i}
        for i, c in enumerate(conclusions)
    ]
    return list(reversed(runs))


@pytest.mark.parametrize(
    ("lint_runs", "passes"),
    [
        (("cancelled", "success"), True),
        (("failure", "success"), True),
        (("success", "failure"), False),
        (("success", "neutral"), True),
    ],
)
def test_rule_3_reads_the_latest_run_of_each_check(flow: Flow, lint_runs: tuple[str, ...], passes: bool) -> None:
    """GitHub counts a name's latest run: an earlier cancelled or failed run passes, a later failure refuses."""
    sha = flow.merged_pr("0.1.1")
    _check_runs(flow, sha, [*_runs("lint", *lint_runs), *_runs("test", "success")])
    done = flow.promote("main")
    assert (done.returncode == 0) is passes, _out(done)
    assert (flow.tip("main") == sha) is passes


def test_rule_3_breaks_a_completion_tie_by_run_id(flow: Flow) -> None:
    """Two runs completed in the same second: the higher id is the later one."""
    sha = flow.merged_pr("0.1.1")
    same = "2026-10-01T00:00:00Z"
    _check_runs(
        flow,
        sha,
        [
            {"name": "lint", "conclusion": "success", "completed_at": same, "id": 7},
            {"name": "lint", "conclusion": "failure", "completed_at": same, "id": 8},
            *_runs("test", "success"),
        ],
    )
    done = flow.promote("main")
    assert done.returncode == 1, _out(done)
    assert "not green at its head: lint" in done.stderr


def test_rule_3_refuses_a_check_still_running_after_a_success(flow: Flow) -> None:
    """A re-run not completed yet is the latest run: the earlier success does not stand for it."""
    sha = flow.merged_pr("0.1.1")
    runs = _runs("lint", "success")
    runs.insert(0, {"name": "lint", "conclusion": None, "completed_at": None, "id": 2000})
    _check_runs(flow, sha, [*runs, *_runs("test", "success")])
    done = flow.promote("main")
    assert done.returncode == 1, _out(done)
    assert "not green at its head: lint" in done.stderr


# ── the release bump ─────────────────────────────────────────────────────────


def test_release_opens_the_one_pr_that_raises_a_released_version(flow: Flow) -> None:
    """Develop's version is tagged: release/<next> carries develop plus one patch, its PR into develop is armed."""
    develop = flow.merged_pr("0.1.1")
    _git(flow.seed, "push", "-q", "origin", f"{develop}:refs/tags/v0.1.1")
    done = flow.promote("release")
    assert done.returncode == 0, _out(done)
    assert "auto-merge armed" in done.stdout
    branch = flow.tip("release/0.1.2")
    assert _git(flow.origin, "rev-parse", f"{branch}^") == develop
    assert _git(flow.origin, "show", f"{branch}:personalscraper/__init__.py") == '__version__ = "0.1.2"'
    calls = flow.gh_calls()
    create = next(c for c in calls if c[:2] == ["pr", "create"])
    assert create[create.index("--base") + 1] == "develop"
    assert create[create.index("--head") + 1] == "release/0.1.2"
    merge = next(c for c in calls if c[:2] == ["pr", "merge"])
    assert "--auto" in merge and "--squash" in merge
    assert len(_git(flow.work, "worktree", "list").splitlines()) == 1


def test_release_leaves_an_unreleased_version_as_it_is(flow: Flow) -> None:
    """Develop's version has no tag yet: nothing to raise, no branch, no PR."""
    flow.merged_pr("0.1.1")
    done = flow.promote("release")
    assert done.returncode == 0, _out(done)
    assert "not released yet" in done.stdout
    assert flow.tip("release/0.1.2") == ""
    assert not any(c[:1] == ["pr"] for c in flow.gh_calls())


def test_release_dry_run_pushes_nothing(flow: Flow) -> None:
    """--dry-run says the bump and leaves origin untouched."""
    develop = flow.merged_pr("0.1.1")
    _git(flow.seed, "push", "-q", "origin", f"{develop}:refs/tags/v0.1.1")
    before = _git(flow.origin, "for-each-ref", "--format=%(refname) %(objectname)")
    done = flow.promote("release", "--dry-run")
    assert done.returncode == 0, _out(done)
    assert "0.1.1 → 0.1.2" in done.stdout
    assert _git(flow.origin, "for-each-ref", "--format=%(refname) %(objectname)") == before
