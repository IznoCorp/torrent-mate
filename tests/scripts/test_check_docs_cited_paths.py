"""Tests for scripts/check-docs-cited-paths.py — a directive cites only what git holds (B-251)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-docs-cited-paths.py"


def _load():
    """Import the guard as a module (its file name is not importable)."""
    spec = importlib.util.spec_from_file_location("check_docs_cited_paths", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _directive(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "PLAN.md"
    path.write_text(text, encoding="utf-8")
    return path


def _run(module, directive: Path, tracked: set[str] | None) -> int:
    with (
        patch.object(module, "DIRECTIVES", (directive,)),
        patch.object(module, "ROOT", directive.parent),
        patch.object(module, "tracked_paths", return_value=tracked),
    ):
        return module.arm_cited_paths()


def test_a_cited_path_git_holds_is_clean(tmp_path: Path) -> None:
    """`docs/x/DESIGN.md` in backticks, present in the index → 0."""
    module = _load()
    directive = _directive(tmp_path, "See `docs/features/x/DESIGN.md`.\n")
    assert _run(module, directive, {"docs/features/x/DESIGN.md"}) == 0


def test_a_cited_path_on_disk_only_is_refused(tmp_path: Path, capsys) -> None:
    """B-251: the file exists on this disk and no commit holds it → refused, not passed."""
    module = _load()
    (tmp_path / "docs" / "features" / "x").mkdir(parents=True)
    (tmp_path / "docs" / "features" / "x" / "REPORT.md").write_text("on disk\n", encoding="utf-8")
    directive = _directive(tmp_path, "See `docs/features/x/REPORT.md`.\n")
    assert _run(module, directive, set()) == 1
    assert "no commit holds" in capsys.readouterr().err


def test_an_archived_path_cited_live_is_refused(tmp_path: Path) -> None:
    """The file moved under docs/archive/ and the citation did not."""
    module = _load()
    directive = _directive(tmp_path, "Evidence in `docs/features/maquette-l01/DESIGN.md`.\n")
    assert _run(module, directive, {"docs/archive/features/maquette-l01/DESIGN.md"}) == 1


def test_bare_names_are_not_read(tmp_path: Path) -> None:
    """`MODEL.md` alone is a relative citation this guard does not judge — but a read of zero is refused."""
    module = _load()
    directive = _directive(tmp_path, "Read `MODEL.md` and `docs/x/a.md`.\n")
    assert module.cited_paths(directive) == ["docs/x/a.md"]


def test_an_empty_read_is_refused(tmp_path: Path, capsys) -> None:
    """A directive citing nothing the pattern reads is unread, and unread is not clean."""
    module = _load()
    directive = _directive(tmp_path, "No path here.\n")
    assert _run(module, directive, {"docs/x/a.md"}) == 1
    assert "zero citations" in capsys.readouterr().err


def test_git_unreachable_is_refused(tmp_path: Path) -> None:
    """`git ls-files` failing must not read as clean."""
    module = _load()
    directive = _directive(tmp_path, "See `docs/x/a.md`.\n")
    assert _run(module, directive, None) == 1


def _run_history(module, directive: Path, tracked: set[str] | None, verdicts: dict) -> int:
    """Like `_run`, with `held_by_commit` answering from `verdicts` — None for an unknown commit."""
    with (
        patch.object(module, "DIRECTIVES", (directive,)),
        patch.object(module, "ROOT", directive.parent),
        patch.object(module, "tracked_paths", return_value=tracked),
        patch.object(module, "held_by_commit", side_effect=lambda sha, path: verdicts.get((sha, path))),
    ):
        return module.arm_cited_paths()


def test_a_history_citation_the_commit_holds_is_clean(tmp_path: Path) -> None:
    """`docs/archive/x/DESIGN.md@5322c2fa` — the commit holds the path → 0, and the read is not empty."""
    module = _load()
    directive = _directive(tmp_path, "Design: `docs/archive/features/x/DESIGN.md@5322c2fa`.\n")
    assert module.cited_history(directive) == [("docs/archive/features/x/DESIGN.md", "5322c2fa")]
    assert module.cited_paths(directive) == []
    assert _run_history(module, directive, set(), {("5322c2fa", "docs/archive/features/x/DESIGN.md"): True}) == 0


def test_a_history_citation_the_commit_does_not_hold_is_refused(tmp_path: Path, capsys) -> None:
    """The sha is a commit, the path was never in it → refused, naming the citation."""
    module = _load()
    directive = _directive(tmp_path, "See `docs/archive/features/x/DESIGN.md@5322c2fa`.\n")
    assert _run_history(module, directive, set(), {("5322c2fa", "docs/archive/features/x/DESIGN.md"): False}) == 1
    assert "does not hold" in capsys.readouterr().err


def test_a_history_citation_with_an_unknown_commit_is_refused(tmp_path: Path, capsys) -> None:
    """A sha that is not one unambiguous commit → refused, not passed."""
    module = _load()
    directive = _directive(tmp_path, "See `docs/archive/features/x/DESIGN.md@abcdef12`.\n")
    assert _run_history(module, directive, set(), {}) == 1
    assert "not one commit" in capsys.readouterr().err


def test_history_citations_count_as_a_read(tmp_path: Path) -> None:
    """A directive whose only citations are `@sha` ones is read, not empty."""
    module = _load()
    directive = _directive(tmp_path, "Only `docs/archive/a.md@5322c2fa` here.\n")
    assert _run_history(module, directive, set(), {("5322c2fa", "docs/archive/a.md"): True}) == 0


def test_a_bare_citation_still_needs_the_index(tmp_path: Path) -> None:
    """The `@sha` form does not loosen the bare form: an untracked bare path is still refused."""
    module = _load()
    directive = _directive(tmp_path, "`docs/archive/a.md@5322c2fa` and `docs/x/b.md`.\n")
    assert _run_history(module, directive, set(), {("5322c2fa", "docs/archive/a.md"): True}) == 1


def _run_arm(module, arm: str, tracked: set[str] | None) -> int:
    with patch.object(module, "tracked_paths", return_value=tracked):
        return getattr(module, arm)()


def test_a_tracked_path_under_a_history_tree_is_refused(capsys) -> None:
    """`docs/archive/x.md` back in the index — a tool that still archives — is named and refused."""
    module = _load()
    assert _run_arm(module, "arm_no_history_in_tree", {"docs/archive/x.md", "docs/reference/a.md"}) == 1
    assert "docs/archive/x.md" in capsys.readouterr().err


def test_each_history_tree_is_held() -> None:
    module = _load()
    tracked = {"docs/archive/a.md", "docs/superpowers/b.md", "docs/analysis/c.md"}
    assert _run_arm(module, "arm_no_history_in_tree", tracked) == 3


def test_an_index_without_history_trees_is_clean() -> None:
    module = _load()
    assert _run_arm(module, "arm_no_history_in_tree", {"docs/reference/a.md", "docs/production/b.md"}) == 0


def test_history_arm_refuses_when_git_is_unreachable() -> None:
    module = _load()
    assert _run_arm(module, "arm_no_history_in_tree", None) == 1
