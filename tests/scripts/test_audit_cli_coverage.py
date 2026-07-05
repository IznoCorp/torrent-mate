"""Tests for the CLI-coverage audit script (scripts/audit-cli-coverage.py).

Covers:
- Script exists at the documented path.
- Script exits 0 on the current codebase (fail-soft behaviour).
- Command-name extraction logic (``_extract_command_names``):
  - ``@app.command("explicit-name")`` → explicit string used.
  - ``@app.command()`` (no args) → function name converted to hyphen-case.
  - ``@app.command`` (bare, no call) → function name converted to hyphen-case.
  - Multiple commands in one file.
  - No ``@app.command`` decorators → empty list.
  - Syntax error in source → empty list (no crash).
- Documented-command extraction logic (``_extract_documented_commands``).
- Domain CLI coverage check (``check_domain_cli_coverage``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate the script
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit-cli-coverage.py"

# Import the helpers under test directly so unit tests do not need subprocess.
sys.path.insert(0, str(SCRIPT.parent))

# Use importlib so the hyphen in the filename is not a problem.
import importlib.util as _util  # noqa: E402

_spec = _util.spec_from_file_location("audit_cli_coverage", SCRIPT)
assert _spec is not None
_mod = _util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_extract_command_names = _mod._extract_command_names
_extract_documented_commands = _mod._extract_documented_commands
check_domain_cli_coverage = _mod.check_domain_cli_coverage


# ---------------------------------------------------------------------------
# 1 — Script exists
# ---------------------------------------------------------------------------


def test_script_exists() -> None:
    """The audit-cli-coverage script exists at the documented path."""
    assert SCRIPT.is_file(), f"Script not found at {SCRIPT}"


# ---------------------------------------------------------------------------
# 2 — Script exits 0 on current codebase (fail-soft)
# ---------------------------------------------------------------------------


def test_script_exits_zero_on_current_codebase() -> None:
    """The script exits 0 on the current codebase in default (fail-soft) mode.

    Findings are expected (commands.md is not fully populated in Phase 2.5)
    but the exit code must be 0 so ``make check`` stays green.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"audit-cli-coverage.py exited {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# 3 — Command-name extraction
# ---------------------------------------------------------------------------


def test_extract_explicit_name() -> None:
    """@app.command("explicit-name") returns the string literal as command name."""
    source = """
import typer
app = typer.Typer()

@app.command("my-command")
def my_func() -> None:
    pass
"""
    assert _extract_command_names(source) == ["my-command"]


def test_extract_no_arg_uses_function_name() -> None:
    """@app.command() with no args derives the name from the function name."""
    source = """
import typer
app = typer.Typer()

@app.command()
def library_scan() -> None:
    pass
"""
    assert _extract_command_names(source) == ["library-scan"]


def test_extract_bare_decorator_uses_function_name() -> None:
    """@app.command (bare, no parentheses) derives the name from the function name."""
    source = """
import typer
app = typer.Typer()

@app.command
def do_something() -> None:
    pass
"""
    assert _extract_command_names(source) == ["do-something"]


def test_extract_multiple_commands() -> None:
    """Multiple @app.command decorators in one file all get extracted."""
    source = """
import typer
app = typer.Typer()

@app.command("first-cmd")
def first() -> None:
    pass

@app.command()
def second_command() -> None:
    pass

@app.command("third")
def anything() -> None:
    pass
"""
    assert _extract_command_names(source) == ["first-cmd", "second-command", "third"]


def test_extract_no_commands_returns_empty() -> None:
    """Files with no @app.command decorators return an empty list."""
    source = """
def plain_function() -> None:
    pass
"""
    assert _extract_command_names(source) == []


def test_extract_syntax_error_returns_empty() -> None:
    """A source file with a syntax error does not crash — returns empty list."""
    source = "def broken(: -> None: pass"
    assert _extract_command_names(source) == []


def test_extract_deduplicates_names() -> None:
    """Duplicate command names (edge case) are deduplicated in the output."""
    source = """
import typer
app = typer.Typer()

@app.command("dup")
def first() -> None:
    pass

@app.command("dup")
def second() -> None:
    pass
"""
    assert _extract_command_names(source) == ["dup"]


# ---------------------------------------------------------------------------
# 4 — Documented-command extraction
# ---------------------------------------------------------------------------


def test_documented_commands_extracted_from_markdown() -> None:
    """Commands referenced as 'personalscraper <cmd>' in Markdown are extracted."""
    doc = """
# Commands

```bash
personalscraper ingest
personalscraper library-index --mode full
personalscraper run --dry-run
```

Prose: use `personalscraper info` to inspect.
"""
    result = _extract_documented_commands(doc)
    assert "ingest" in result
    assert "library-index" in result
    assert "run" in result
    assert "info" in result
    # The literal word "personalscraper" must NOT leak in as a command — a \s+
    # sub-command separator used to capture the next line's prefix (regression).
    assert "personalscraper" not in result


def test_documented_subcommands_extracted() -> None:
    """A documented 'personalscraper <group> <sub>' registers group AND leaf.

    Typer reports the leaf name (e.g. ``set-password``), so without capturing the
    second token every sub-command is a false-positive 'undocumented' finding.
    """
    doc = """
```bash
personalscraper web set-password --write
personalscraper follow remove --id 12
personalscraper seed mark a1b2c3
```
"""
    result = _extract_documented_commands(doc)
    assert {"web", "set-password", "follow", "remove", "seed", "mark"} <= result
    # A trailing option (starts with '-') is not mistaken for a sub-command.
    assert "-" not in result and "write" not in result


def test_documented_commands_empty_on_empty_doc() -> None:
    """Empty or command-free text returns an empty set."""
    assert _extract_documented_commands("# No commands here") == set()


# ---------------------------------------------------------------------------
# 5 — Domain CLI coverage (integration: real codebase)
# ---------------------------------------------------------------------------


def test_domain_cli_coverage_no_unexpected_warnings_on_current_codebase() -> None:
    """Business domains either have CLI coverage or are explicitly allowlisted.

    Verifies that every domain checked by :func:`check_domain_cli_coverage` is
    invoked by at least one CLI command, EXCEPT for known-unreachable domains
    surfaced as SH-26 findings (tracked in
    ``docs/features/tech-debt/plan/phase-08-polish.md`` §8.8 + audit
    ``docs/features/tech-debt/audit/12-dead-infrastructure.md``).

    The ``ingest`` domain (added to the audit in 0.16.0 sub-phase 8.8) is
    intentionally allowlisted here: the pipeline step exists but no standalone
    ``personalscraper <ingest-cmd>`` CLI imports from ``personalscraper.ingest``
    yet. Adding that CLI is a separate roadmap item.

    Failure here means a new domain has become unreachable from the CLI surface
    without being explicitly accepted as a SH-26 finding.
    """
    expected_uncovered_domains = {"ingest"}  # SH-26 finding surfaced by 8.8 audit
    warnings = check_domain_cli_coverage()
    unexpected = [w for w in warnings if not any(f"domain '{d}'" in w for d in expected_uncovered_domains)]
    assert unexpected == [], "Unexpected domain(s) not covered by any CLI command:\n" + "\n".join(unexpected)
