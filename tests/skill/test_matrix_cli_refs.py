"""Tests that every CLI invocation referenced in the design-conformity matrix is valid.

The design-conformity matrix at
``.claude/skills/pipeline-monitor/references/design-conformity-matrix.md``
documents expected pipeline behaviour and references specific
``personalscraper <cmd> [--flag ...]`` invocations.  If a command or flag
mentioned in the matrix no longer exists, the skill agents operate on a stale
contract and flag false positives — or miss real regressions.

This test suite:

1. Reads the matrix file from the filesystem.
2. Extracts every ``personalscraper <cmd>`` invocation (both bare commands and
   commands with flags) from backtick-quoted CLI references.
3. Runs ``personalscraper <cmd> --help`` for each extracted invocation and
   asserts exit code 0.
4. For flags that appear alongside a command (e.g. ``--dry-run``), additionally
   asserts that the flag string is present in the ``--help`` output.

Known bugs captured by this test (will flip from xfail to pass once fixed):

- DEV #20 — ``qbit-restart`` command does not exist.

Would-have-caught history:

- DEV #10 (Phase 4.6): ``library-reconcile --dry-run`` referenced in GATE 6
  of the matrix but the flag was never added to the CLI.  Fixed by Phase 4.6 —
  ``--dry-run`` and ``--read-only`` are now first-class flags.
- DEV #20 (Phase 8.3): ``qbit-restart`` command referenced in INGEST deviation
  table but the command does not exist in the CLI surface.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Matrix path resolution
# ---------------------------------------------------------------------------

# The .claude/ directory is a git submodule sitting directly inside the
# personalscraper repo root.  We locate the matrix relative to this test file
# (tests/skill/ → repo root → .claude/).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MATRIX_PATH = _REPO_ROOT / ".claude" / "skills" / "pipeline-monitor" / "references" / "design-conformity-matrix.md"

# Locate the CLI entry point.  Using the installed ``personalscraper`` shim
# (via pip install -e .) is more reliable than ``python -m personalscraper``
# because the latter requires a ``__main__.py`` module.
_CLI_BIN = shutil.which("personalscraper") or "personalscraper"


# ---------------------------------------------------------------------------
# Known-bad references
# ---------------------------------------------------------------------------

# Each key is the canonical string representation of the reference as it
# appears (or should appear) in the matrix.  The value is the reason string
# used for ``pytest.mark.xfail``.
#
# - Key format for bare commands: ``"<cmd>"``
# - Key format for commands with flags: ``"<cmd> <flag>"``
_KNOWN_BAD: dict[str, str] = {
    # DEV #20 — qbit-restart: command doesn't exist in the CLI surface.
    # Referenced in the INGEST deviation table as a remediation action.
    "qbit-restart": ("DEV #20 — qbit-restart command does not exist; fixed by Phase 8.3"),
}


# ---------------------------------------------------------------------------
# Matrix parsing helpers
# ---------------------------------------------------------------------------

# Recognises any CLI sub-command name token: letters, digits and hyphens,
# starting with a letter.  Covers both ``info`` and ``library-reconcile``.
_CMD_TOKEN = r"[a-z][a-z0-9-]+"
# Recognises a flag token: ``--<word>`` form.
_FLAG_TOKEN = r"--[a-z][a-z0-9-]+"


def _parse_cli_refs(matrix_text: str) -> list[tuple[str, str | None]]:
    """Extract ``personalscraper <cmd>`` references from *matrix_text*.

    Returns a deduplicated list of ``(command, arg_or_None)`` tuples where
    *command* is the sub-command name (e.g. ``"info"``, ``"library-reconcile"``)
    and *arg_or_None* is an optional flag (``"--dry-run"``) or positional
    argument (``"scan"`` for ``trailers scan``) to verify in the help output.

    The parser recognises these forms in backtick literals:

    - ``personalscraper info`` → ``("info", None)``
    - ``personalscraper qbit-restart`` → ``("qbit-restart", None)``
    - ``personalscraper library-reconcile --dry-run`` → ``("library-reconcile", "--dry-run")``
    - ``library-reconcile --dry-run`` (bare, without prefix) → same
    - ``trailers scan`` (inside a list item) → ``("trailers", "scan")``

    Args:
        matrix_text: Raw Markdown text of the design-conformity matrix.

    Returns:
        Deduplicated list of ``(command, optional_arg)`` tuples, sorted for
        stable test ordering.
    """
    refs: set[tuple[str, str | None]] = set()

    # ── Pattern 1: explicit ``personalscraper <cmd>`` references ──────────
    # Matches both backtick-quoted and bare-text forms (e.g. table cells).
    # Captures an optional flag token following the command.
    ps_pattern = re.compile(
        r"personalscraper\s+"
        rf"(?P<cmd>{_CMD_TOKEN})"
        rf"(?:\s+(?P<flag>{_FLAG_TOKEN}))?",
    )
    for m in ps_pattern.finditer(matrix_text):
        cmd = m.group("cmd")
        flag: str | None = m.group("flag") if m.group("flag") else None
        refs.add((cmd, flag))

    # ── Pattern 2: bare sub-command references inside backticks ───────────
    # Handles forms like ``library-reconcile --dry-run`` that appear WITHOUT
    # the ``personalscraper`` prefix but are clearly CLI invocations.
    # We restrict to ``library-`` prefix commands to avoid false positives on
    # e.g. arbitrary inline code snippets.
    bare_library_pattern = re.compile(
        r"`"
        rf"(?P<cmd>library-{_CMD_TOKEN})"
        rf"(?:\s+(?P<flag>{_FLAG_TOKEN}))?"
        r"`",
    )
    for m in bare_library_pattern.finditer(matrix_text):
        cmd = m.group("cmd")
        flag = m.group("flag") if m.group("flag") else None
        refs.add((cmd, flag))

    # ── Pattern 3: trailers sub-commands ──────────────────────────────────
    # The matrix section on ``trailers sub-commands`` lists them as
    # ``trailers scan``, ``trailers download``, … inside backtick literals.
    trailer_pattern = re.compile(r"`trailers\s+(?P<sub>scan|download|verify|purge)`")
    for m in trailer_pattern.finditer(matrix_text):
        # Map to ("trailers", "<sub>") so the test invokes
        # ``personalscraper trailers <sub> --help``.
        refs.add(("trailers", m.group("sub")))

    # Deduplicate and sort for stable parametrize ordering.
    return sorted(refs, key=lambda t: (t[0], t[1] or ""))


def _run_help(*args: str) -> tuple[int, str]:
    """Run ``personalscraper <args...> --help`` and return ``(exit_code, output)``.

    Uses the installed ``personalscraper`` shim rather than ``python -m
    personalscraper`` because the package does not expose a ``__main__``
    module.

    Args:
        *args: Sub-command tokens to pass after ``personalscraper``.

    Returns:
        A tuple ``(exit_code, combined_stdout_stderr)`` from the subprocess.
    """
    result = subprocess.run(
        [_CLI_BIN, *args, "--help"],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Test: matrix file must exist
# ---------------------------------------------------------------------------


def test_matrix_file_exists() -> None:
    """The design-conformity matrix file must be accessible from the repo root.

    If this test fails, the matrix has been moved or the .claude submodule is
    not checked out.  All downstream CLI-ref tests would be vacuous (no refs
    parsed) — a fail here surfaces the root cause immediately.
    """
    assert _MATRIX_PATH.exists(), (
        f"Matrix file not found at {_MATRIX_PATH}. Ensure the .claude/ submodule is checked out."
    )


# ---------------------------------------------------------------------------
# Test: extract at least the known commands
# ---------------------------------------------------------------------------


def test_matrix_parses_known_refs() -> None:
    """The parser must extract at least the two known-bad DEV references.

    This guards against a regression where the parser stops extracting refs
    (e.g. if the matrix format changes) — without this, all the parametrized
    tests below would be vacuous green.

    The matrix (v2.0) is known to reference at minimum:

    - ``personalscraper qbit-restart`` (DEV #20, INGEST deviation table)
    - ``library-reconcile --dry-run`` (DEV #10, GATE 6 usage note)
    - ``personalscraper info`` (invariant AU)
    """
    if not _MATRIX_PATH.exists():
        pytest.skip("Matrix file not found — covered by test_matrix_file_exists")

    matrix_text = _MATRIX_PATH.read_text(encoding="utf-8")
    refs = _parse_cli_refs(matrix_text)
    commands = {cmd for cmd, _ in refs}

    assert "qbit-restart" in commands, (
        "Parser did not extract 'qbit-restart' from the matrix. "
        "Check the regex patterns — the matrix format may have changed."
    )
    assert "info" in commands, (
        "Parser did not extract 'info' from the matrix. Check the regex patterns — the matrix format may have changed."
    )
    # Matrix v2.1 (Phase 7) replaced `--dry-run` with `--read-only` / `--enqueue-repairs`
    # aliases (DEV #10 closure). Assert the new flag is parsed instead.
    reconcile_flags = {flag for cmd, flag in refs if cmd == "library-reconcile"}
    assert reconcile_flags & {"--read-only", "--enqueue-repairs"}, (
        f"Parser did not extract --read-only / --enqueue-repairs from library-reconcile "
        f"references in the matrix. Extracted flags: {reconcile_flags!r}. "
        "DEV #10 closure (Phase 7 / matrix v2.1) replaced the old --dry-run mention."
    )


# ---------------------------------------------------------------------------
# Parametrized CLI validity tests
# ---------------------------------------------------------------------------


def _load_params() -> list[pytest.param]:
    """Build parametrized test cases from the matrix.

    Each case is a ``pytest.param`` with ``(cmd, arg_or_None)`` values.
    Known-bad references receive ``pytest.mark.xfail(strict=True)`` so they
    *must* fail (which documents the current state) and will flip to PASS once
    the underlying DEV fix ships.

    Returns:
        List of ``pytest.param`` objects ready for ``@pytest.mark.parametrize``.
    """
    if not _MATRIX_PATH.exists():
        # Return a single placeholder so pytest doesn't error on an empty
        # parametrize list.
        return [pytest.param("info", None, id="info (matrix not found — placeholder)")]

    matrix_text = _MATRIX_PATH.read_text(encoding="utf-8")
    refs = _parse_cli_refs(matrix_text)

    params: list[pytest.param] = []
    for cmd, arg in refs:
        # Build a stable, human-readable test id.
        test_id = f"{cmd}/{arg}" if arg else cmd

        # Derive the lookup key for the known-bad table.
        if arg and arg.startswith("--"):
            key = f"{cmd} {arg}"
        else:
            key = cmd

        if key in _KNOWN_BAD:
            reason = _KNOWN_BAD[key]
            params.append(
                pytest.param(
                    cmd,
                    arg,
                    id=test_id,
                    marks=pytest.mark.xfail(
                        strict=True,
                        reason=reason,
                    ),
                )
            )
        else:
            params.append(pytest.param(cmd, arg, id=test_id))

    return params


@pytest.mark.parametrize(("cmd", "arg"), _load_params())
def test_matrix_cli_ref_valid(cmd: str, arg: str | None) -> None:
    """Every CLI reference in the design-conformity matrix must resolve to a valid command.

    For each ``personalscraper <cmd>`` reference extracted from the matrix:

    - ``personalscraper <cmd> --help`` must exit 0.
    - If a flag (e.g. ``--dry-run``) was referenced alongside the command,
      its string must appear in the ``--help`` output (catches renamed or
      removed flags).
    - If a positional sub-command argument (e.g. ``"scan"`` for ``trailers
      scan``) was referenced, it is tested via
      ``personalscraper trailers scan --help`` (exit 0).

    Args:
        cmd: The sub-command name (e.g. ``"library-reconcile"``).
        arg: An optional flag (``"--dry-run"``) or positional sub-command arg
             (``"scan"``).  When present its presence/validity is also
             asserted.
    """
    if arg is None or arg.startswith("--"):
        # For bare commands and flag checks: run ``personalscraper <cmd> --help``.
        exit_code, output = _run_help(cmd)
        assert exit_code == 0, f"`personalscraper {cmd} --help` exited with code {exit_code}.\nOutput:\n{output}"
        if arg is not None:
            # Additionally verify the flag appears in the help text.
            assert arg in output, (
                f"Flag `{arg}` not found in `personalscraper {cmd} --help` output.\n"
                f"The flag may have been renamed or removed.\n"
                f"Output:\n{output}"
            )
    else:
        # Positional sub-command (e.g. trailers scan): run
        # ``personalscraper <cmd> <arg> --help``.
        exit_code, output = _run_help(cmd, arg)
        assert exit_code == 0, f"`personalscraper {cmd} {arg} --help` exited with code {exit_code}.\nOutput:\n{output}"
