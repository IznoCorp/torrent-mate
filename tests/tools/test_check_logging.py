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
        """``personalscraper/logger.py`` is exempt from the no-stdlib-logger rule.

        The exemption is path-suffix based (requires ``personalscraper/logger.py``),
        not just basename matching, to avoid false negatives.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        # Must mirror the real path suffix: personalscraper/logger.py
        pkg_dir = tmp_path / "personalscraper"
        pkg_dir.mkdir()
        p = pkg_dir / "logger.py"
        p.write_text(_STDLIB_LOGGER_SNIPPET, encoding="utf-8")
        findings = analyze_file(p)
        assert all(f.rule != "no-stdlib-logger" for f in findings)

    def test_non_package_logger_py_is_not_exempt(self, tmp_path: Path) -> None:
        """A ``logger.py`` outside ``personalscraper/`` is NOT exempt.

        The stricter suffix match means a bare ``logger.py`` in any other location
        still gets flagged, preventing a bypass via a same-named file.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        p = _write(tmp_path, "logger.py", _STDLIB_LOGGER_SNIPPET)
        findings = analyze_file(p)
        assert any(f.rule == "no-stdlib-logger" for f in findings)


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


# ---------------------------------------------------------------------------
# New rule: no-stdlib-logger via from-import
# ---------------------------------------------------------------------------


class TestFromLoggingImport:
    """Tests for bare ``from logging import getLogger`` detection."""

    def test_flags_bare_from_import_getLogger(self, tmp_path: Path) -> None:
        """``from logging import getLogger; getLogger(...)`` is flagged.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
from logging import getLogger

logger = getLogger(__name__)
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        rules = [f.rule for f in findings]
        assert "no-stdlib-logger" in rules

    def test_flags_aliased_from_import_getLogger(self, tmp_path: Path) -> None:
        """``from logging import getLogger as gl; gl(...)`` is flagged.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
from logging import getLogger as gl

logger = gl(__name__)
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        rules = [f.rule for f in findings]
        assert "no-stdlib-logger" in rules


# ---------------------------------------------------------------------------
# New rule: no-stdlib-logger via aliased module import
# ---------------------------------------------------------------------------


class TestAliasedLoggingModule:
    """Tests for ``import logging as lg; lg.getLogger(...)`` detection."""

    def test_flags_aliased_module_getLogger(self, tmp_path: Path) -> None:
        """``import logging as lg; lg.getLogger(...)`` is flagged as no-stdlib-logger.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
import logging as lg

logger = lg.getLogger(__name__)
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        rules = [f.rule for f in findings]
        assert "no-stdlib-logger" in rules


# ---------------------------------------------------------------------------
# New rule: no-structlog-direct
# ---------------------------------------------------------------------------


class TestStructlogDirect:
    """Tests for ``structlog.get_logger()`` / ``structlog.getLogger()`` direct call detection."""

    def test_flags_structlog_get_logger(self, tmp_path: Path) -> None:
        """``import structlog; structlog.get_logger(...)`` is flagged as no-structlog-direct.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
import structlog

log = structlog.get_logger("x")
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        rules = [f.rule for f in findings]
        assert "no-structlog-direct" in rules

    def test_flags_structlog_getLogger(self, tmp_path: Path) -> None:
        """``structlog.getLogger(...)`` is also flagged as no-structlog-direct.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
import structlog

log = structlog.getLogger("x")
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        rules = [f.rule for f in findings]
        assert "no-structlog-direct" in rules

    def test_structlog_direct_is_error_severity(self, tmp_path: Path) -> None:
        """no-structlog-direct findings are ERROR-severity.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
import structlog

log = structlog.get_logger("x")
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        direct = [f for f in findings if f.rule == "no-structlog-direct"]
        assert all(f.severity == "ERROR" for f in direct)


# ---------------------------------------------------------------------------
# print() in nested function and decorator bodies
# ---------------------------------------------------------------------------


class TestPrintInNestedScopes:
    """Tests that print() inside nested functions and decorators is flagged."""

    def test_flags_print_in_nested_function(self, tmp_path: Path) -> None:
        """print() inside a nested function body is still flagged.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
def outer():
    def inner():
        print("nested")
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        assert any(f.rule == "no-print" for f in findings)

    def test_flags_print_in_decorator_body(self, tmp_path: Path) -> None:
        """print() inside a decorator-factory body is flagged.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
def my_decorator(func):
    print("decorating")
    return func
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        assert any(f.rule == "no-print" for f in findings)


# ---------------------------------------------------------------------------
# Walrus operator get_logger binding
# ---------------------------------------------------------------------------


class TestWalrusGetLogger:
    """Tests that walrus-operator ``(log := get_logger(...))`` is tracked."""

    def test_walrus_binding_is_tracked(self, tmp_path: Path) -> None:
        """(log := get_logger("x")) is tracked; f-string on log is flagged.

        After a walrus-operator binding the variable is added to _structlog_vars,
        so an f-string call on it should trigger no-fstring-log.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
from personalscraper.logger import get_logger


def run():
    if (log := get_logger("x")):
        log.info(f"running something")
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        assert any(f.rule == "no-fstring-log" for f in findings)

    def test_walrus_binding_clean_call_no_warning(self, tmp_path: Path) -> None:
        """Walrus-bound logger with keyword-arg style produces no no-fstring-log.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        snippet = """\
from personalscraper.logger import get_logger


def run(item):
    if (log := get_logger("x")):
        log.info("running", item=item)
"""
        p = _write(tmp_path, "module.py", snippet)
        findings = analyze_file(p)
        assert all(f.rule != "no-fstring-log" for f in findings)


# ---------------------------------------------------------------------------
# SyntaxError tolerance
# ---------------------------------------------------------------------------


class TestSyntaxErrorTolerance:
    """Tests that analyze_paths continues past files with syntax errors."""

    def test_malformed_file_does_not_crash(self, tmp_path: Path) -> None:
        """A file containing a SyntaxError is skipped; scanning continues.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        bad = tmp_path / "bad.py"
        bad.write_text("def f(:\n    pass\n", encoding="utf-8")
        # Should not raise; returns empty list for the bad file.
        findings = analyze_paths([bad])
        assert isinstance(findings, list)

    def test_malformed_file_scan_continues_to_next(self, tmp_path: Path) -> None:
        """After a malformed file, remaining clean files are still scanned.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        bad = tmp_path / "bad.py"
        bad.write_text("def f(:\n    pass\n", encoding="utf-8")
        good = _write(tmp_path, "good.py", _PRINT_SNIPPET)
        findings = analyze_paths([bad, good])
        # The good file must still produce a no-print finding.
        assert any(f.rule == "no-print" for f in findings)


# ---------------------------------------------------------------------------
# Mixed file + directory path arguments
# ---------------------------------------------------------------------------


class TestMixedPaths:
    """Tests that analyze_paths accepts a mix of file and directory arguments."""

    def test_mixed_file_and_dir_both_scanned(self, tmp_path: Path) -> None:
        """A mix of a direct file path and a directory path are both scanned.

        Args:
            tmp_path: Pytest temporary directory fixture.
        """
        # Direct file with a print() violation
        file_path = _write(tmp_path, "standalone.py", _PRINT_SNIPPET)

        # Subdirectory with a stdlib-logger violation
        sub = tmp_path / "sub"
        sub.mkdir()
        _write(sub, "module.py", _STDLIB_LOGGER_SNIPPET)

        findings = analyze_paths([file_path, sub])
        rules = {f.rule for f in findings}
        assert "no-print" in rules
        assert "no-stdlib-logger" in rules
