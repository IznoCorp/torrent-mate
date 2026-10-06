"""Tests for the branch arms of scripts/autodeploy-poll.sh and the deploy scripts' branch guards.

The git flow (docs/features/git-flow/DESIGN.md § 3.2–3.3): the prod clone follows
`prod`, the staging clone follows `staging`, both by fast-forward only. `main` deploys
nothing any more, and a `staging` rewritten on origin is a fault to see — logged, the
pass skipped, the clone left where it was — never a history followed in silence.

The poller is driven with `--once` against a bare origin and two clones in `tmp_path`,
each clone carrying stand-in deploy scripts that record what they were asked to serve.
`pm2` is stubbed on PATH so the design arm never reaches the machine's real apps. The
real `deploy.sh` and `deploy-staging.sh` are copied into a clone and run until their
branch guards decide; a missing venv stops them right after, before any build.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

_DEPLOY_STUB = """#!/usr/bin/env bash
branch="$(git rev-parse --abbrev-ref HEAD)"
printf '%s %s %s\\n' "$(basename "$0")" "$branch" "$(git rev-parse HEAD)" >> "$TM_TEST_DEPLOYS"
"""


def _env(root: Path) -> dict[str, str]:
    """An environment isolating git from the machine and stubbing pm2.

    Args:
        root: The test's scratch directory, holding `gitconfig` and `bin/`.

    Returns:
        The environment.
    """
    return {
        **os.environ,
        "PATH": f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "GIT_CONFIG_GLOBAL": str(root / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "TM_DESIGN_APP": "no-such-app-under-test",
        "TM_TEST_DEPLOYS": str(root / "deploys.txt"),
    }


class Origin:
    """A bare origin with `main`, `staging` and `prod`, a seed clone, and the two deploy clones."""

    def __init__(self, root: Path) -> None:
        """Seeds origin and clones the prod and staging checkouts on their branches.

        Args:
            root: The test's scratch directory.
        """
        self.root = root
        (root / "gitconfig").write_text(
            "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n", encoding="utf-8"
        )
        bin_dir = root / "bin"
        bin_dir.mkdir()
        pm2 = bin_dir / "pm2"
        pm2.write_text("#!/usr/bin/env bash\n[ \"$1\" = jlist ] && echo '[]'\nexit 0\n", encoding="utf-8")
        pm2.chmod(0o755)
        self.env = _env(root)
        self.origin = root / "origin.git"
        self.run(root, "git", "init", "-q", "--bare", str(self.origin))
        self.seed = root / "seed"
        self.run(root, "git", "init", "-q", str(self.seed))
        scripts = self.seed / "scripts"
        scripts.mkdir()
        for name in ("deploy.sh", "deploy-staging.sh"):
            (scripts / name).write_text(_DEPLOY_STUB, encoding="utf-8")
            (scripts / name).chmod(0o755)
        self.base = self.commit("main", "seed")
        self.git(self.seed, "remote", "add", "origin", str(self.origin))
        for branch in ("main", "staging", "prod"):
            self.git(self.seed, "push", "-q", "origin", f"{self.base}:refs/heads/{branch}")
        self.prod = self.clone("prod")
        self.staging = self.clone("staging")

    def run(self, cwd: Path, *argv: str) -> str:
        """Runs a command and returns its stripped stdout.

        Args:
            cwd: Where to run it.
            *argv: The command.

        Returns:
            Its standard output, stripped.
        """
        return subprocess.run(argv, cwd=cwd, env=self.env, check=True, capture_output=True, text=True).stdout.strip()

    def git(self, cwd: Path, *args: str) -> str:
        """Runs git in `cwd`.

        Args:
            cwd: The repository.
            *args: The git arguments.

        Returns:
            Its standard output, stripped.
        """
        return self.run(cwd, "git", *args)

    def commit(self, branch: str, message: str, *, parent: str | None = None) -> str:
        """Commits a change on `branch` in the seed clone, optionally from another parent.

        Args:
            branch: The local branch to commit on.
            message: The commit subject, also the changed file's content.
            parent: A commit to start the branch from instead of its current tip.

        Returns:
            The new commit's SHA.
        """
        if parent is not None:
            self.git(self.seed, "checkout", "-q", "-B", branch, parent)
        elif self.git(self.seed, "branch", "--list", branch):
            self.git(self.seed, "checkout", "-q", branch)
        elif self._born():
            self.git(self.seed, "checkout", "-q", "-b", branch)
        (self.seed / "change.txt").write_text(message, encoding="utf-8")
        self.git(self.seed, "add", "-A")
        self.git(self.seed, "commit", "-q", "-m", message)
        return self.git(self.seed, "rev-parse", "HEAD")

    def _born(self) -> bool:
        """Whether the seed repository has a first commit."""
        return (
            subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=self.seed, env=self.env, capture_output=True
            ).returncode
            == 0
        )

    def push(self, branch: str, sha: str, *, force: bool = False) -> None:
        """Moves origin's `branch` to `sha`.

        Args:
            branch: The branch on origin.
            sha: The commit it points at afterwards.
            force: Whether the move may rewrite history.
        """
        self.git(self.seed, "push", "-q", *(["--force"] if force else []), "origin", f"{sha}:refs/heads/{branch}")

    def clone(self, branch: str) -> Path:
        """Clones origin on `branch`.

        Args:
            branch: The branch the clone stands on.

        Returns:
            The clone's path.
        """
        path = self.root / f"clone-{branch}"
        self.run(self.root, "git", "clone", "-q", "-b", branch, str(self.origin), str(path))
        return path

    def poll(self) -> str:
        """Runs one pass of the poller over the two clones.

        Returns:
            The pass's output.
        """
        env = {**self.env, "TM_PROD_CLONE": str(self.prod), "TM_STAGING_CLONE": str(self.staging)}
        done = subprocess.run(
            ["bash", str(_SCRIPTS / "autodeploy-poll.sh"), "--once"],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert done.returncode == 0, done.stdout + done.stderr
        return done.stdout + done.stderr

    def deploys(self) -> list[str]:
        """What the stand-in deploy scripts were asked to serve, one line per call.

        Returns:
            « <script> <branch> <sha> » per deployment.
        """
        log = self.root / "deploys.txt"
        return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


@pytest.fixture
def origin(tmp_path: Path) -> Origin:
    """A fresh origin and its two deploy clones, all at one commit."""
    return Origin(tmp_path)


# ── the poller ───────────────────────────────────────────────────────────────


def test_prod_ignores_main(origin: Origin) -> None:
    """A merge into `main` deploys nothing: prod moves only with `prod`."""
    origin.push("main", origin.commit("main", "a change on main"))
    output = origin.poll()
    assert origin.git(origin.prod, "rev-parse", "HEAD") == origin.base, output
    assert not any(line.startswith("deploy.sh") for line in origin.deploys()), output


def test_prod_follows_prod(origin: Origin) -> None:
    """A promotion to `prod` fast-forwards the prod clone and runs deploy.sh on `prod`."""
    tip = origin.commit("main", "promoted")
    origin.push("prod", tip)
    output = origin.poll()
    assert origin.git(origin.prod, "rev-parse", "HEAD") == tip, output
    assert f"deploy.sh prod {tip}" in origin.deploys(), output


def test_staging_follows_a_fast_forward(origin: Origin) -> None:
    """A promotion to `staging` fast-forwards the staging clone and deploys it."""
    tip = origin.commit("main", "promoted")
    origin.push("staging", tip)
    output = origin.poll()
    assert origin.git(origin.staging, "rev-parse", "HEAD") == tip, output
    assert f"deploy-staging.sh staging {tip}" in origin.deploys(), output


def test_staging_refuses_a_rewritten_history(origin: Origin) -> None:
    """A `staging` forced onto a diverged commit is logged and NOT followed."""
    ahead = origin.commit("main", "first")
    origin.push("staging", ahead)
    origin.poll()
    diverged = origin.commit("other", "a rewrite", parent=origin.base)
    origin.push("staging", diverged, force=True)
    before = origin.deploys()
    output = origin.poll()
    assert "not a fast-forward" in output
    assert origin.git(origin.staging, "rev-parse", "HEAD") == ahead
    assert origin.deploys() == before


def test_prod_refuses_a_rewritten_history(origin: Origin) -> None:
    """The same fault on `prod` is the same refusal."""
    ahead = origin.commit("main", "first")
    origin.push("prod", ahead)
    origin.poll()
    origin.push("prod", origin.commit("other", "a rewrite", parent=origin.base), force=True)
    before = origin.deploys()
    output = origin.poll()
    assert "not a fast-forward" in output
    assert origin.git(origin.prod, "rev-parse", "HEAD") == ahead
    assert origin.deploys() == before


# ── the deploy scripts' branch guards ────────────────────────────────────────


def _real_deploy(
    origin: Origin,
    script: str,
    branch: str,
    *,
    origin_moves: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Runs the repository's real deploy script from a fresh clone on `branch`.

    The script is committed into the clone (it must sit in a clean tree) and its venv
    points nowhere, so a script that passes its branch guards stops at the venv guard.

    Args:
        origin: The test origin.
        script: `deploy.sh` or `deploy-staging.sh`.
        branch: The branch the clone stands on.
        origin_moves: Whether origin's branch advances past the clone before the run.
        extra_env: Variables added to the run's environment (they win over the defaults).

    Returns:
        The finished process.
    """
    path = origin.root / f"real-{script}-{branch}"
    origin.run(origin.root, "git", "clone", "-q", "-b", branch, str(origin.origin), str(path))
    shutil.copy(_SCRIPTS / script, path / "scripts" / script)
    origin.git(path, "commit", "-q", "-am", "the real script")
    origin.git(path, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
    if origin_moves:
        (path / "later.txt").write_text("later", encoding="utf-8")
        origin.git(path, "add", "-A")
        origin.git(path, "commit", "-q", "-m", "pushed later")
        origin.git(path, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
        origin.git(path, "reset", "-q", "--hard", "HEAD~1")
    env = {
        **origin.env,
        "TM_VENV": str(origin.root / "none"),
        "TM_STAGING_VENV": str(origin.root / "none"),
        **(extra_env or {}),
    }
    return subprocess.run(["bash", str(path / "scripts" / script)], cwd=path, env=env, capture_output=True, text=True)


def test_deploy_refuses_main(origin: Origin) -> None:
    """deploy.sh serves `prod` only: on `main` it refuses before anything is built."""
    done = _real_deploy(origin, "deploy.sh", "main")
    assert done.returncode == 1
    assert "not prod" in done.stderr, done.stderr


def test_deploy_passes_its_branch_guards_on_prod(origin: Origin) -> None:
    """On a clean `prod` in sync with origin, deploy.sh gets past the branch guards."""
    done = _real_deploy(origin, "deploy.sh", "prod")
    assert done.returncode == 1
    assert "venv not found" in done.stderr, done.stderr


def test_deploy_staging_refuses_another_branch(origin: Origin) -> None:
    """deploy-staging.sh serves `staging` only: a feature branch is no longer a playground."""
    origin.push("feat/x", origin.base)
    done = _real_deploy(origin, "deploy-staging.sh", "feat/x")
    assert done.returncode == 1
    assert "not staging" in done.stderr, done.stderr


def test_deploy_staging_passes_its_branch_guards_on_staging(origin: Origin) -> None:
    """On a clean `staging` in sync with origin, deploy-staging.sh gets past the branch guards."""
    done = _real_deploy(origin, "deploy-staging.sh", "staging")
    assert done.returncode == 1
    assert "venv not found" in done.stderr, done.stderr


def test_deploy_staging_refuses_a_clone_behind_origin(origin: Origin) -> None:
    """deploy-staging.sh serves what origin's `staging` holds, nothing older."""
    done = _real_deploy(origin, "deploy-staging.sh", "staging", origin_moves=True)
    assert done.returncode == 1
    assert "origin/staging" in done.stderr, done.stderr


def test_deploy_refuses_a_clone_behind_origin(origin: Origin) -> None:
    """deploy.sh serves what origin's `prod` holds, nothing older."""
    done = _real_deploy(origin, "deploy.sh", "prod", origin_moves=True)
    assert done.returncode == 1
    assert "≠ origin/prod" in done.stderr, done.stderr


def _stub_venv(origin: Origin) -> str:
    """Makes a venv directory that only holds an executable `bin/python`, enough to pass the venv guard.

    Args:
        origin: The test origin.

    Returns:
        The venv directory.
    """
    python = origin.root / "stub-venv" / "bin" / "python"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    return str(python.parent.parent)


@pytest.mark.parametrize(("script", "branch"), [("deploy.sh", "prod"), ("deploy-staging.sh", "staging")])
def test_deploy_refuses_without_uv_before_any_build(origin: Origin, script: str, branch: str) -> None:
    """The backend installs from the lock through uv: no uv, no build (nothing is wiped first)."""
    venv = _stub_venv(origin)
    done = _real_deploy(
        origin,
        script,
        branch,
        extra_env={"TM_VENV": venv, "TM_STAGING_VENV": venv, "TM_UV": str(origin.root / "no-uv")},
    )
    assert done.returncode == 1
    assert "uv not found" in done.stderr, done.stderr
    assert "building the SPA" not in done.stdout, done.stdout


@pytest.mark.parametrize(("script", "branch"), [("deploy.sh", "prod"), ("deploy-staging.sh", "staging")])
def test_deploy_refuses_without_the_lock_before_any_build(origin: Origin, script: str, branch: str) -> None:
    """With uv present but no uv.lock in the clone, the deploy refuses before the build."""
    venv = _stub_venv(origin)
    done = _real_deploy(
        origin, script, branch, extra_env={"TM_VENV": venv, "TM_STAGING_VENV": venv, "TM_UV": "/usr/bin/true"}
    )
    assert done.returncode == 1
    assert "uv.lock missing" in done.stderr, done.stderr
    assert "building the SPA" not in done.stdout, done.stdout
