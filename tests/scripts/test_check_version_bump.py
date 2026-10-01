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


def test_default_base_is_develop(tmp_path: Path) -> None:
    """With no --base, the bump is read against `origin/develop`, where every PR lands."""
    mod = _load()
    init = tmp_path / "init.py"
    init.write_text('__version__ = "0.49.10"\n', encoding="utf-8")
    with (
        patch.object(mod, "_INIT_PATH", str(init)),
        patch.object(mod, "_base_version", return_value=(0, 49, 9)) as base,
        patch("sys.argv", ["check_version_bump.py"]),
    ):
        assert mod.main() == 0
    base.assert_called_once_with("origin/develop")


def _verdict(mod, tmp_path: Path, head: str, base: tuple[int, ...]) -> int:
    """Runs the check with HEAD at `head` against a base at `base`.

    Args:
        mod: The loaded script module.
        tmp_path: Where the stand-in `__init__.py` is written.
        head: HEAD's `__version__` string.
        base: The base version tuple.

    Returns:
        The script's exit code.
    """
    init = tmp_path / "init.py"
    init.write_text(f'__version__ = "{head}"\n', encoding="utf-8")
    with (
        patch.object(mod, "_INIT_PATH", str(init)),
        patch.object(mod, "_base_version", return_value=base),
        patch("sys.argv", ["check_version_bump.py"]),
    ):
        return mod.main()


def test_hotfix_fourth_component_is_a_bump(tmp_path: Path) -> None:
    """A hotfix bumps a fourth component from prod's version: 0.98.131 → 0.98.131.1."""
    assert _verdict(_load(), tmp_path, "0.98.131.1", (0, 98, 131)) == 0


def test_develop_patch_is_above_a_hotfix(tmp_path: Path) -> None:
    """The next patch on develop outranks a hotfix of the previous one: 0.98.131.1 → 0.98.132."""
    assert _verdict(_load(), tmp_path, "0.98.132", (0, 98, 131, 1)) == 0


def test_the_reverse_order_is_refused(tmp_path: Path) -> None:
    """Back from a patch to a hotfix of an older one, or from a hotfix to its base, is no bump."""
    mod = _load()
    assert _verdict(mod, tmp_path, "0.98.131.1", (0, 98, 132)) == 1
    assert _verdict(mod, tmp_path, "0.98.131", (0, 98, 131, 1)) == 1
