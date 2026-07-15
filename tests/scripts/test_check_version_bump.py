"""Tests for scripts/check_version_bump.py — the §10-3 version-bump CI guard."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_version_bump.py"


def _load():
    """Import the check_version_bump script module."""
    spec = importlib.util.spec_from_file_location("check_version_bump", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_version_reads_dotted_tuple() -> None:
    """__version__ = "0.49.10" → (0, 49, 10)."""
    mod = _load()
    assert mod._parse_version('__version__ = "0.49.10"\n') == (0, 49, 10)


def test_parse_version_none_when_absent() -> None:
    """A file without __version__ → None."""
    mod = _load()
    assert mod._parse_version("x = 1\n") is None


def test_bump_present_exits_zero(tmp_path: Path) -> None:
    """HEAD > base → exit 0."""
    mod = _load()
    (tmp_path / "personalscraper").mkdir()
    init = tmp_path / "personalscraper" / "__init__.py"
    init.write_text('__version__ = "0.49.10"\n', encoding="utf-8")
    with (
        patch.object(mod, "_INIT_PATH", str(init)),
        patch.object(mod, "_base_version", return_value=(0, 49, 9)),
        patch("sys.argv", ["check_version_bump.py", "--base", "origin/main"]),
    ):
        assert mod.main() == 0


def test_missing_bump_exits_one(tmp_path: Path) -> None:
    """HEAD == base → exit 1 (no bump)."""
    mod = _load()
    init = tmp_path / "init.py"
    init.write_text('__version__ = "0.49.9"\n', encoding="utf-8")
    with (
        patch.object(mod, "_INIT_PATH", str(init)),
        patch.object(mod, "_base_version", return_value=(0, 49, 9)),
        patch("sys.argv", ["check_version_bump.py"]),
    ):
        assert mod.main() == 1


def test_base_unavailable_skips(tmp_path: Path) -> None:
    """No base version (unreachable ref) → exit 0 (cannot prove a regression)."""
    mod = _load()
    init = tmp_path / "init.py"
    init.write_text('__version__ = "0.49.10"\n', encoding="utf-8")
    with (
        patch.object(mod, "_INIT_PATH", str(init)),
        patch.object(mod, "_base_version", return_value=None),
        patch("sys.argv", ["check_version_bump.py"]),
    ):
        assert mod.main() == 0
