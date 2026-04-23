"""Tests for scripts/check_logging.py — logging convention audit script."""

# Import the public API directly so tests do not shell out.
# The script lives outside the package but is importable because pyproject.toml
# adds "." to pythonpath for pytest.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from check_logging import analyze_file, analyze_paths, main  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Source snippets that each trigger exactly one finding
_PRINT_SNIPPET = """\
def greet(name):
    print(f"Hello {name}")
"""

_STDLIB_LOGGER_SNIPPET = """\
import logging

logger = logging.getLogger(__name__)
"""

_FSTRING_LOG_SNIPPET = """\
from personalscraper.logger import get_logger

log = get_logger("mymod")

def run(item):
    log.info(f"processing {item}")
"""

# A file that triggers all three findings at once
_ALL_OFFENDERS_SNIPPET = """\
import logging
from personalscraper.logger import get_logger

log = get_logger("combined")

def process(item):
    print(item)
    logger2 = logging.getLogger(__name__)
    log.debug(f"processing {item}")
"""

# A perfectly clean file — no findings expected
_CLEAN_SNIPPET = """\
from personalscraper.logger import get_logger

log = get_logger("clean")


def run(item):
    log.info("processing item", item=item)
"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    """Write *content* to *tmp_path/name* and return the resulting Path.

    Args:
        tmp_path: Temporary directory provided by pytest.
        name: Filename (relative) to create inside tmp_path.
        content: Text content to write.

    Returns:
        Path to the newly created file.
    """
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# analyze_file tests
# ---------------------------------------------------------------------------


class TestAnalyzeFilePrint:
    """Tests for the no-print rule."""

    def test_flags_bare_print(self, tmp_path: Path) -> None:
        """A bare print() call is flagged as ERROR no-print.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "module.py", _PRINT_SNIPPET)
        findings = analyze_file(p)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == "ERROR"
        assert f.rule == "no-print"
        assert f.line == 2

    def test_no_false_positive_clean_file(self, tmp_path: Path) -> None:
        """A clean file produces no findings.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "clean.py", _CLEAN_SNIPPET)
        findings = analyze_file(p)
        assert findings == []


class TestAnalyzeFileStdlibLogger:
    """Tests for the no-stdlib-logger rule."""

    def test_flags_logging_get_logger(self, tmp_path: Path) -> None:
        """logging.getLogger() is flagged as ERROR no-stdlib-logger.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "module.py", _STDLIB_LOGGER_SNIPPET)
        findings = analyze_file(p)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == "ERROR"
        assert f.rule == "no-stdlib-logger"

    def test_logger_py_is_exempt(self, tmp_path: Path) -> None:
        """The file named logger.py is exempt from the no-stdlib-logger rule.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "logger.py", _STDLIB_LOGGER_SNIPPET)
        findings = analyze_file(p)
        assert all(f.rule != "no-stdlib-logger" for f in findings)


class TestAnalyzeFileFstringLog:
    """Tests for the no-fstring-log rule."""

    def test_flags_fstring_on_structlog_var(self, tmp_path: Path) -> None:
        """f-string argument to a structlog bound-logger is flagged as WARN.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "module.py", _FSTRING_LOG_SNIPPET)
        findings = analyze_file(p)
        fstring_findings = [f for f in findings if f.rule == "no-fstring-log"]
        assert len(fstring_findings) == 1
        assert fstring_findings[0].severity == "WARN"

    def test_no_fstring_warning_for_keyword_args(self, tmp_path: Path) -> None:
        """Keyword-arg style structlog calls produce no no-fstring-log warning.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "clean.py", _CLEAN_SNIPPET)
        findings = analyze_file(p)
        assert all(f.rule != "no-fstring-log" for f in findings)


# ---------------------------------------------------------------------------
# Fixture tree: three findings in one file
# ---------------------------------------------------------------------------


class TestThreeFindingsFixture:
    """Fixture tree with one print, one logging.getLogger, one f-string log — expect 3 findings."""

    def test_three_findings(self, tmp_path: Path) -> None:
        """All three rules fire on the combined offenders snippet.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "offenders.py", _ALL_OFFENDERS_SNIPPET)
        findings = analyze_file(p)
        rules = {f.rule for f in findings}
        assert "no-print" in rules
        assert "no-stdlib-logger" in rules
        assert "no-fstring-log" in rules
        assert len(findings) == 3

    def test_severities(self, tmp_path: Path) -> None:
        """Print and logging.getLogger are ERROR; f-string log is WARN.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "offenders.py", _ALL_OFFENDERS_SNIPPET)
        findings = analyze_file(p)
        by_rule = {f.rule: f for f in findings}
        assert by_rule["no-print"].severity == "ERROR"
        assert by_rule["no-stdlib-logger"].severity == "ERROR"
        assert by_rule["no-fstring-log"].severity == "WARN"


# ---------------------------------------------------------------------------
# analyze_paths tests
# ---------------------------------------------------------------------------


class TestAnalyzePaths:
    """Tests for analyze_paths — directory recursion."""

    def test_scans_directory_recursively(self, tmp_path: Path) -> None:
        """analyze_paths recurses into subdirectories.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        sub = tmp_path / "sub"
        sub.mkdir()
        _write(sub, "bad.py", _PRINT_SNIPPET)
        findings = analyze_paths([tmp_path])
        assert any(f.rule == "no-print" for f in findings)

    def test_clean_tree_zero_findings(self, tmp_path: Path) -> None:
        """A tree of clean files yields zero findings.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        _write(tmp_path, "a.py", _CLEAN_SNIPPET)
        _write(tmp_path, "b.py", _CLEAN_SNIPPET)
        findings = analyze_paths([tmp_path])
        assert findings == []


# ---------------------------------------------------------------------------
# main() / exit-code tests
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for the main() entry point and exit codes."""

    def test_exits_1_on_errors(self, tmp_path: Path) -> None:
        """main() returns 1 when ERROR-severity findings are present.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "bad.py", _PRINT_SNIPPET)
        result = main(argv=[str(p)])
        assert result == 1

    def test_exits_0_report_only(self, tmp_path: Path) -> None:
        """main() returns 0 with --report-only even when errors are present.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "bad.py", _PRINT_SNIPPET)
        result = main(argv=["--report-only", str(p)])
        assert result == 0

    def test_exits_0_clean_tree(self, tmp_path: Path) -> None:
        """main() returns 0 when no ERROR-severity findings exist.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "clean.py", _CLEAN_SNIPPET)
        result = main(argv=[str(p)])
        assert result == 0

    def test_exits_0_warn_only(self, tmp_path: Path) -> None:
        """main() returns 0 when findings are WARN-only (no ERRORs).

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        # A file with only an f-string log (WARN, not ERROR).
        snippet = """\
from personalscraper.logger import get_logger

log = get_logger("x")

def run(x):
    log.info(f"running {x}")
"""
        p = _write(tmp_path, "warn_only.py", snippet)
        result = main(argv=[str(p)])
        assert result == 0
