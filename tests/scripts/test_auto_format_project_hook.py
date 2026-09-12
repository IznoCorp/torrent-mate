"""The project's formatter hook, held to the tracked tree (B-387).

WHAT IT PAID FOR. On 2026-09-11 the hook forwarded to the global formatter a
`.py` that a review reader had written under the untracked `.review/` directory
of its own worktree, and the formatter rewrote it. An instrument rewritten by a
hook is an instrument its author did not write, and the reader had no reason to
suspect the file it was reading was not the file it had produced.

Every test here builds a throwaway git repository in a `tmp_path` and drives the
hook's own `main()` with a stub standing in for the global formatter, so what is
measured is whether the payload was HANDED ON — not whether some formatter
happened to change the bytes of a file it was given.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "auto_format_project.py"

UNFORMATTED = "def  f( x ):\n  return   x\n"


def load_hook() -> ModuleType:
    """Import the hook by path — it lives outside any package.

    Returns:
        The imported module.
    """
    specification = importlib.util.spec_from_file_location("auto_format_project", HOOK)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def make_repository(tmp_path: Path) -> Path:
    """Build a throwaway repository with one tracked file and one ignored directory.

    Args:
        tmp_path: The pytest scratch directory.

    Returns:
        The repository's root.
    """
    repository = tmp_path / "repository"
    repository.mkdir()
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")
    }
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "tester@example.invalid"],
        ["git", "config", "user.name", "tester"],
    ):
        subprocess.run(command, cwd=repository, check=True, env=environment)
    (repository / ".gitignore").write_text(".review/\n", encoding="utf-8")
    (repository / "tracked.py").write_text(UNFORMATTED, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repository, check=True, env=environment)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repository, check=True, env=environment)
    return repository


def drive(module: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: Path) -> tuple[str, bool]:
    """Run the hook on one path with a stub global formatter, and report what happened.

    Args:
        module: The imported hook.
        monkeypatch: The fixture used to replace stdin and the global hook.
        tmp_path: The scratch directory holding the stub and its witness.
        target: The file the tool claims to have edited.

    Returns:
        What the hook said on stderr, and whether the global formatter was reached.
    """
    witness = tmp_path / "the-global-formatter-ran"
    stub = tmp_path / "stub_formatter.py"
    stub.write_text(
        f"import pathlib, sys\npathlib.Path({str(witness)!r}).write_text(sys.stdin.read())\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "GLOBAL_HOOK", stub)
    payload = json.dumps({"tool_input": {"file_path": str(target)}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    errors = io.StringIO()
    monkeypatch.setattr(sys, "stderr", errors)
    module.main()
    return errors.getvalue(), witness.exists()


def test_a_file_under_an_ignored_directory_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE DEFECT THIS FILE WAS WRITTEN FOR: `.review/` is a reader's, not the hook's."""
    repository = make_repository(tmp_path)
    review = repository / ".review"
    review.mkdir()
    reader_tool = review / "walk.py"
    reader_tool.write_text(UNFORMATTED, encoding="utf-8")

    module = load_hook()
    said, reached = drive(module, monkeypatch, tmp_path, reader_tool)

    assert not reached, "the ignored file was handed to the global formatter"
    assert "git ignores it" in said, said
    assert reader_tool.read_text(encoding="utf-8") == UNFORMATTED


def test_an_untracked_file_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Outside the tracked tree by the other door: never added, so never rewritten."""
    repository = make_repository(tmp_path)
    stranger = repository / "stranger.py"
    stranger.write_text(UNFORMATTED, encoding="utf-8")

    module = load_hook()
    said, reached = drive(module, monkeypatch, tmp_path, stranger)

    assert not reached, "an untracked file was handed to the global formatter"
    assert "git does not track it" in said, said
    assert stranger.read_text(encoding="utf-8") == UNFORMATTED


def test_a_file_outside_any_repository_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No repository can vouch for it, so nothing here may rewrite it."""
    orphan = tmp_path / "orphan"
    orphan.mkdir()
    stray = orphan / "stray.py"
    stray.write_text(UNFORMATTED, encoding="utf-8")

    module = load_hook()
    said, reached = drive(module, monkeypatch, tmp_path, stray)

    assert not reached, "a file outside every repository was handed to the formatter"
    assert "git does not track it" in said, said


def test_a_tracked_file_still_reaches_the_formatter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The hook must still do its job — a filter that refuses everything is broken.

    This is the hold that makes the three above mean something: without it the
    whole file passes over a hook that has simply stopped forwarding anything.
    """
    repository = make_repository(tmp_path)

    module = load_hook()
    said, reached = drive(module, monkeypatch, tmp_path, repository / "tracked.py")

    assert reached, f"the tracked file never reached the formatter: {said}"
    assert said == "", said


def test_the_skipped_extensions_are_still_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The filter this hook was written for is untouched by B-387's repair."""
    repository = make_repository(tmp_path)
    register = repository / "BUGS.md"
    register.write_text("# not prettier-shaped\n", encoding="utf-8")

    module = load_hook()
    said, reached = drive(module, monkeypatch, tmp_path, register)

    assert not reached
    assert "not prettier-shaped" in said, said
