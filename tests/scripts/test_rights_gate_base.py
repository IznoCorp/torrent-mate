"""The base branch R427 compares the host's `login:markup` region against.

After the git flow's cut-over the dev checkout serving tm-design stands on
`develop` (docs/features/git-flow/DESIGN.md § 3.6): the harness reads
`origin/develop` when that branch exists, and `origin/main` before it does.
Every test builds its own origin in `tmp_path`; nothing here reads the real one.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from _repo_paths import HARNESS

sys.path.insert(0, str(HARNESS))

# The CI `test` job installs no Playwright (only the harness jobs do); the rule's
# browser half is not exercised here, so a bare stand-in lets the module import.
try:
    import playwright.async_api  # noqa: F401
except ImportError:
    _stand_in = types.ModuleType("playwright.async_api")
    _stand_in.async_playwright = None  # type: ignore[attr-defined]
    sys.modules.setdefault("playwright", types.ModuleType("playwright"))
    sys.modules["playwright.async_api"] = _stand_in

import rights_gate  # noqa: E402

INDEX = "frontend/maquette/design/index.html"


def _env(root: Path) -> dict[str, str]:
    """An environment isolating git from the machine's configuration and hooks.

    Args:
        root: The test's scratch directory, where the empty global config sits.

    Returns:
        The environment.
    """
    (root / "gitconfig").touch()
    return {
        **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        "GIT_CONFIG_GLOBAL": str(root / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }


def _git(cwd: Path, root: Path, *args: str) -> None:
    """Runs git in `cwd`, isolated.

    Args:
        cwd: The repository to run in.
        root: The test's scratch directory.
        *args: The git arguments.
    """
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=_env(root))


def _region(word: str) -> str:
    """A `login:markup` region holding one word.

    Args:
        word: What the region says.

    Returns:
        The region, markers included.
    """
    return f"<!-- login:markup:start -->{word}<!-- login:markup:end -->"


def _origin(root: Path, *, develop: bool) -> Path:
    """A bare origin whose `main` says « main », and whose `develop`, when made, says « develop ».

    Args:
        root: The test's scratch directory.
        develop: Whether origin has a `develop` branch.

    Returns:
        The bare repository.
    """
    origin = root / "origin.git"
    _git(root, root, "init", "-q", "--bare", str(origin))
    seed = root / "seed"
    _git(root, root, "init", "-q", "-b", "main", str(seed))
    page = seed / INDEX
    page.parent.mkdir(parents=True)
    page.write_text(_region("main"), encoding="utf-8")
    _git(seed, root, "add", "-A")
    _git(seed, root, "commit", "-q", "-m", "main")
    _git(seed, root, "push", "-q", str(origin), "HEAD:refs/heads/main")
    if develop:
        page.write_text(_region("develop"), encoding="utf-8")
        _git(seed, root, "commit", "-q", "-am", "develop")
        _git(seed, root, "push", "-q", str(origin), "HEAD:refs/heads/develop")
    return origin


def _checkout(root: Path, origin: Path, *, fetched: bool) -> Path:
    """A checkout whose `frontend/maquette` is the harness's root.

    Args:
        root: The test's scratch directory.
        origin: The bare origin.
        fetched: Whether the checkout knows origin's branches (a full clone) or none (a CI checkout).

    Returns:
        The `frontend/maquette` directory of the checkout.
    """
    work = root / "work"
    if fetched:
        _git(root, root, "clone", "-q", str(origin), str(work))
    else:
        _git(root, root, "init", "-q", str(work))
        _git(work, root, "remote", "add", "origin", str(origin))
    (work / "frontend" / "maquette").mkdir(parents=True, exist_ok=True)
    return work / "frontend" / "maquette"


def _isolate(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Points the harness's own git calls, which inherit the environment, at the isolated config.

    Args:
        monkeypatch: The test's monkeypatch.
        root: The test's scratch directory.
    """
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(key)
    for key, value in _env(root).items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("fetched", [True, False], ids=["clone", "ci-checkout"])
def test_reads_develop_when_it_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: bool) -> None:
    """Once `develop` exists, the region is develop's — known locally or fetched."""
    maquette = _checkout(tmp_path, _origin(tmp_path, develop=True), fetched=fetched)
    _isolate(monkeypatch, tmp_path)
    assert rights_gate.base_region(maquette) == _region("develop")


@pytest.mark.parametrize("fetched", [True, False], ids=["clone", "ci-checkout"])
def test_reads_main_before_develop_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fetched: bool) -> None:
    """Before the cut-over there is no `develop`: the region is main's."""
    maquette = _checkout(tmp_path, _origin(tmp_path, develop=False), fetched=fetched)
    _isolate(monkeypatch, tmp_path)
    assert rights_gate.base_region(maquette) == _region("main")
