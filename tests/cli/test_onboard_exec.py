"""Tests for the detached onboarding runner's path-confinement guard (bosun §9, review-c3).

The runner :func:`kanbanmate.cli.onboard_exec.main` is the SOLE place the server-derived clone
DESTINATION is confined to ``ONBOARD_BASE_DIRS`` (the route validates only the git URL, never the
derived on-disk target — DESIGN §5.2). These tests drive ``main`` IN-PROCESS (no real spawn): they
stub ``init`` and ``subprocess.run`` so no registry write / git clone happens, and assert the guard
accepts a confined target and rejects every escape (traversal, symlink escape, target outside the
base dirs, bad mode).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kanbanmate.cli import onboard_exec


@pytest.fixture
def base_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ONBOARD_BASE_DIRS at a single tmp base for both the runner and ``path_is_confined``.

    Two bindings must agree: ``onboard_exec._clone_target`` derives under
    ``onboard_exec.ONBOARD_BASE_DIRS[0]`` (a name imported into the runner's namespace), while
    ``app.onboard.path_is_confined`` resolves its bases from ``app.onboard.ONBOARD_BASE_DIRS``.
    Patch BOTH so derivation and confinement use the same tmp base.
    """
    import kanbanmate.app.onboard as onboard

    base = (tmp_path / "dev").resolve()
    base.mkdir()
    monkeypatch.setattr(onboard, "ONBOARD_BASE_DIRS", (str(base),))
    monkeypatch.setattr(onboard_exec, "ONBOARD_BASE_DIRS", (str(base),))
    return base


def _stub_io(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub ``init`` + ``subprocess.run`` so the runner performs no registry write / real clone.

    Returns:
        A dict capturing whether ``init`` ran (``init_called``) and the recorded ``git clone`` argv
        (``clone_argv``), so a test can assert the guard short-circuited BEFORE any side effect.
    """
    captured: dict[str, Any] = {"init_called": False, "clone_argv": None}

    def _fake_init(*_a: Any, **_k: Any) -> None:
        captured["init_called"] = True

    def _fake_run(argv: list[str], *_a: Any, **_k: Any) -> Any:
        captured["clone_argv"] = argv
        return None

    monkeypatch.setattr(onboard_exec, "init", _fake_init)
    # Patch by dotted path: ``subprocess`` is an implicit module attribute on onboard_exec, so a
    # direct ``onboard_exec.subprocess`` reference trips mypy's no-implicit-reexport.
    monkeypatch.setattr("kanbanmate.cli.onboard_exec.subprocess.run", _fake_run)
    return captured


def test_clone_confined_target_passes_and_clones(
    base_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mode=clone with a valid github URL: guard passes, git clone is invoked under the base dir."""
    captured = _stub_io(monkeypatch)
    onboard_exec.main(
        mode="clone",
        root=str(base_dir / "root"),
        repo="owner/repo",
        path="",
        git_url="https://github.com/owner/repo.git",
    )
    # Cloned to <base>/repo (the derived target), then registered.
    assert captured["clone_argv"] is not None
    assert captured["clone_argv"][:3] == ["git", "clone", "--depth"]
    assert captured["clone_argv"][-1] == str(base_dir / "repo")
    assert captured["init_called"] is True


def test_clone_target_outside_base_is_refused(
    base_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A derived clone target resolving OUTSIDE the base dirs is refused (SystemExit 2), no clone.

    The runner re-checks the resolved TARGET (not its parent) — DESIGN §5.2. Force the derivation to
    return an out-of-base path and assert the confinement guard rejects it before any I/O.
    """
    captured = _stub_io(monkeypatch)
    escape = (base_dir.parent / "escaped-repo").resolve()  # sibling of base, NOT under it
    monkeypatch.setattr(onboard_exec, "_clone_target", lambda _url: escape)
    with pytest.raises(SystemExit) as exc:
        onboard_exec.main(
            mode="clone",
            root=str(base_dir / "root"),
            repo="owner/repo",
            path="",
            git_url="https://github.com/owner/repo.git",
        )
    assert exc.value.code == 2
    assert captured["clone_argv"] is None  # short-circuited before git clone
    assert captured["init_called"] is False


def test_clone_target_symlink_escape_is_refused(
    base_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A symlink under the base that escapes it makes the resolved target out-of-base → refused.

    ``path_is_confined`` resolves symlinks (``Path.resolve``), so a clone target that lands on a
    symlink pointing outside the base resolves outside it and is rejected — the symlink-escape vector.
    """
    captured = _stub_io(monkeypatch)
    outside = (base_dir.parent / "outside").resolve()
    outside.mkdir()
    link = base_dir / "linked"
    link.symlink_to(outside, target_is_directory=True)
    # Target is <base>/linked/repo — resolve() follows the symlink to <outside>/repo (out of base).
    monkeypatch.setattr(onboard_exec, "_clone_target", lambda _url: link / "repo")
    with pytest.raises(SystemExit) as exc:
        onboard_exec.main(
            mode="clone",
            root=str(base_dir / "root"),
            repo="owner/repo",
            path="",
            git_url="https://github.com/owner/repo.git",
        )
    assert exc.value.code == 2
    assert captured["clone_argv"] is None
    assert captured["init_called"] is False


def test_local_path_outside_base_is_refused(
    base_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mode=local with a --path outside the base dirs is refused (SystemExit 2), no init."""
    captured = _stub_io(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        onboard_exec.main(
            mode="local",
            root=str(base_dir / "root"),
            repo="owner/repo",
            path="/etc",
            git_url="",
        )
    assert exc.value.code == 2
    assert captured["init_called"] is False


def test_local_path_inside_base_passes(base_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """mode=local with a confined --path passes the guard and registers (init runs)."""
    captured = _stub_io(monkeypatch)
    proj = base_dir / "ProjA"
    proj.mkdir()
    onboard_exec.main(
        mode="local",
        root=str(base_dir / "root"),
        repo="owner/repo",
        path=str(proj),
        git_url="",
    )
    assert captured["init_called"] is True


def test_unknown_mode_is_refused(base_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mode other than local|clone is refused (SystemExit 2), no init / clone."""
    captured = _stub_io(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        onboard_exec.main(
            mode="bogus", root=str(base_dir / "root"), repo="owner/repo", path="", git_url=""
        )
    assert exc.value.code == 2
    assert captured["init_called"] is False
    assert captured["clone_argv"] is None


def test_clone_target_strips_dot_git_and_trailing_slash() -> None:
    """``_clone_target`` derives the repo name by stripping a trailing slash + ``.git`` suffix."""
    # The repo dir name is the last URL segment with the .git suffix and any trailing slash removed.
    assert onboard_exec._clone_target("https://github.com/owner/repo.git").name == "repo"
    assert onboard_exec._clone_target("https://github.com/owner/repo/").name == "repo"
    assert onboard_exec._clone_target("https://github.com/owner/repo").name == "repo"
