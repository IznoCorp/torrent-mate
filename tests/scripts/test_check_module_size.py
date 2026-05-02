"""Tests for the module-size advisory script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-module-size.py"


def test_script_exists() -> None:
    """The module-size script exists at the documented path."""
    assert SCRIPT.is_file()


def test_script_exits_zero_on_clean_dir(tmp_path: Path) -> None:
    """Small modules produce no warning and exit zero."""
    pkg = tmp_path / "small_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "tiny.py").write_text("x = 1\n" * 50, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "WARN" not in result.stdout


def test_script_warns_above_warn_threshold(tmp_path: Path) -> None:
    """Modules over 800 non-blank lines are reported as WARN."""
    pkg = tmp_path / "fat_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "big.py").write_text("x = 1\n" * 850, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "WARN" in result.stdout
    assert "big.py" in result.stdout


def test_script_excludes_init_and_tests(tmp_path: Path) -> None:
    """Package init files and tests directories are excluded from findings."""
    pkg = tmp_path / "pkg"
    tests = pkg / "tests"
    tests.mkdir(parents=True)
    (pkg / "__init__.py").write_text("x = 1\n" * 2000, encoding="utf-8")
    (tests / "test_huge.py").write_text("x = 1\n" * 2000, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "WARN" not in result.stdout
    assert "REPORT" not in result.stdout


def test_script_reports_above_block_threshold(tmp_path: Path) -> None:
    """Modules over 1000 non-blank lines are reported but still advisory."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "huge.py").write_text("x = 1\n" * 1100, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "REPORT" in result.stdout
    assert "huge.py" in result.stdout
