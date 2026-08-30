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
