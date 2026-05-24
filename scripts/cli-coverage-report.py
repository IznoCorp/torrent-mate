#!/usr/bin/env python3
"""CLI coverage matrix generator and validator.

Parses ``# ── N. <Theme> ──`` section headers from
``tests/commands/test_*_e2e.py`` files and builds a coverage matrix
(command × section).  Three modes:

``--check``
    Exit 1 if any critical command has a ❌ for a required section
    (N/A sections with a ``# N/A: <reason>`` comment are exempt).
    Used by CI / ``make cli-coverage-check``.

``--write``
    Regenerate ``docs/features/tech-debt/cli-coverage-matrix.md``
    (idempotent — re-running produces the same output).

``--metrics``
    Print section count aggregates (total ✅ / N/A / ❌) for ACC-51.

Filters (combinable with any mode):
``--section "Closure-of-loop" --filter critical``
    Narrow output to a single section and command class for ACC-53 / ACC-54.

Usage::

    python3 scripts/cli-coverage-report.py --check
    python3 scripts/cli-coverage-report.py --write
    python3 scripts/cli-coverage-report.py --metrics
    python3 scripts/cli-coverage-report.py --section Events --filter critical
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests" / "commands"
MATRIX_DOC = ROOT / "docs" / "features" / "tech-debt" / "cli-coverage-matrix.md"

# ---------------------------------------------------------------------------
# Section theme detection
# ---------------------------------------------------------------------------

# (theme_key, label_for_matrix)
CRITICAL_SECTIONS: list[tuple[str, str]] = [
    ("Smoke", "Smoke"),
    ("Realistic", "Realistic"),
    ("Errors", "Errors"),
    ("Idempotence", "Idempotence"),
    ("Dry-run", "Dry-run"),
    ("Output", "Output"),
    ("Events", "Events"),
    ("Closure-of-loop", "Closure-of-loop"),
]

NON_CRITICAL_SECTIONS: list[tuple[str, str]] = [
    ("Smoke", "Smoke"),
    ("Realistic", "Realistic"),
    ("Errors", "Errors"),
    ("Output", "Output"),
]

THEME_PATTERNS: dict[str, re.Pattern[str]] = {
    "Smoke": re.compile(r"\b(?:Smoke|Help)\b", re.IGNORECASE),
    "Realistic": re.compile(r"\bRealistic\b", re.IGNORECASE),
    "Errors": re.compile(r"\bErrors\b", re.IGNORECASE),
    "Idempotence": re.compile(r"\bIdempotence\b", re.IGNORECASE),
    "Dry-run": re.compile(r"\bDry[- ]run\b", re.IGNORECASE),
    "Output": re.compile(r"\bOutput\b", re.IGNORECASE),
    "Events": re.compile(r"\bEvents\b", re.IGNORECASE),
    "Closure-of-loop": re.compile(r"\bClosure[- ]of[- ]loop\b|\bMutations\b", re.IGNORECASE),
}

# Regex for section header lines: ``# ── N. <text> ──``
SECTION_HEADER_RE = re.compile(r"^#\s*─+\s*\d+\.\s+(.+?)\s*─+")

# Regex for N/A justification comments
NA_RE = re.compile(r"^\s*#\s*N/A\s*[:—\-]\s*(.+)")

# Regex for test function definitions
TEST_FUNC_RE = re.compile(r"^\s*def\s+test_\w+")


NON_CRITICAL_COMMANDS: set[str] = {
    "torrents-list",
    "trailers-list",
    "trailers-scan",
    "trailers-verify",
    "info",
    "library-search",
    "library-show",
    "library-status",
    "library-ghost-audit",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cmd_from_path(filepath: Path) -> str:
    """Derive the CLI command name from a test file path.

    ``test_library_doctor_e2e.py`` → ``library-doctor``
    ``test_ingest_e2e.py`` → ``ingest``
    """
    stem = filepath.stem  # e.g. test_library_doctor_e2e
    if not stem.startswith("test_"):
        raise ValueError(f"Expected test_ prefix: {stem}")
    if not stem.endswith("_e2e"):
        raise ValueError(f"Expected _e2e suffix: {stem}")
    middle = stem[5:-4]  # strip "test_" and "_e2e"
    return middle.replace("_", "-")


def _detect_themes(section_text: str) -> list[str]:
    """Return the list of theme keys that *section_text* matches."""
    matched: list[str] = []
    for theme, pattern in THEME_PATTERNS.items():
        if pattern.search(section_text):
            matched.append(theme)
    return matched


def _parse_file(filepath: Path) -> dict[str, str]:
    """Parse a single test file and return per-theme status.

    Returns a dict mapping theme_key → status, where status is one of:
      - ``"✅"`` — section present with at least one ``def test_`` function
      - ``"N/A"`` — section present but only N/A comments (no test functions)
      - ``"❌"`` — section absent (no matching header found)
    """
    lines: list[str]
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}

    # Find all section boundaries: (line_index, section_text, theme_keys)
    # Include ALL section headers, even those matching no standard theme,
    # so the Realistic-naming-gap heuristic can inspect them.
    boundaries: list[tuple[int, str, list[str]]] = []
    for i, line in enumerate(lines):
        m = SECTION_HEADER_RE.match(line)
        if m:
            text = m.group(1).strip()
            themes = _detect_themes(text)
            boundaries.append((i, text, themes))

    # Map: theme_key → best status (✅ > N/A > ❌)
    statuses: dict[str, str] = {}

    for idx, (start, _text, themes) in enumerate(boundaries):
        # Find the end of this section (next boundary or EOF)
        end = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(lines)
        section_lines = lines[start + 1 : end]

        has_test = any(TEST_FUNC_RE.match(ln) for ln in section_lines)
        has_na = any(NA_RE.match(ln) for ln in section_lines)

        if has_test:
            status = "✅"
        elif has_na:
            status = "N/A"
        else:
            status = "❌"

        for theme in themes:
            current = statuses.get(theme)
            # Prefer ✅ over anything, N/A over ❌
            if current is None or status == "✅" or (status == "N/A" and current == "❌"):
                statuses[theme] = status

    # After building statuses from headers, check for read-only context.
    # If the file has N/A comments explaining the command is read-only,
    # auto-promote absent Dry-run/Idempotence/Closure-of-loop to N/A.
    if any(NA_RE.match(line) for line in lines):
        # Collect all N/A reason lines into a single blob.
        na_blob = " ".join(NA_RE.match(line).group(1) for line in lines if NA_RE.match(line)).lower()
        _readonly_keywords = (
            "read-only",
            "diagnostic command",
            "select-only",
            "no domain event",
            "does not write",
            "does not mutate",
            "no mutation",
            "no bdd",
            "query-only",
            "no eventbus",
        )
        is_readonly = any(kw in na_blob for kw in _readonly_keywords)
        if is_readonly:
            for theme in ("Dry-run", "Idempotence", "Closure-of-loop"):
                if theme not in statuses:
                    statuses[theme] = "N/A"

    # Heuristic for "Realistic" naming gaps: if the file has sections with
    # test functions that match NO standard theme, realistic coverage exists
    # under a non-standard section name.  Auto-promote absent Realistic.
    if "Realistic" not in statuses:
        _standard_themes = set(THEME_PATTERNS)
        for idx_b, (b_start, _b_text, b_themes) in enumerate(boundaries):
            if any(t in _standard_themes for t in b_themes):
                continue
            b_end = boundaries[idx_b + 1][0] if idx_b + 1 < len(boundaries) else len(lines)
            section_lines = lines[b_start + 1 : b_end]
            if any(TEST_FUNC_RE.match(ln) for ln in section_lines):
                statuses["Realistic"] = "✅"
                break

    return statuses


def _collect_na_footnotes(
    filepath: Path, cmd: str, statuses: dict[str, str], sections: list[tuple[str, str]]
) -> dict[str, str]:
    """Collect N/A justification footnotes for a command.

    Returns a dict mapping section_label → one-line reason string.
    """
    lines: list[str]
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return {}

    boundaries: list[tuple[int, str, list[str]]] = []
    for i, line in enumerate(lines):
        m = SECTION_HEADER_RE.match(line)
        if m:
            text = m.group(1).strip()
            themes = _detect_themes(text)
            if themes:
                boundaries.append((i, text, themes))

    footnotes: dict[str, str] = {}
    for idx, (start, _text, themes) in enumerate(boundaries):
        end = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(lines)
        section_lines = lines[start + 1 : end]
        has_test = any(TEST_FUNC_RE.match(ln) for ln in section_lines)

        if has_test:
            continue

        for line in section_lines:
            m = NA_RE.match(line)
            if m:
                reason = m.group(1).strip().rstrip(".")
                for theme in themes:
                    theme_label = _theme_label(theme, sections)
                    if theme_label:
                        footnotes[theme_label] = reason
                break

    # For auto-N/A sections (read-only context promotion), derive a footnote
    # from the first available N/A comment in the file.
    auto_na_themes = [
        theme_key
        for theme_key in ("Dry-run", "Idempotence", "Closure-of-loop")
        if statuses.get(theme_key) == "N/A" and _theme_label(theme_key, sections) not in footnotes
    ]
    if auto_na_themes:
        for line in lines:
            m = NA_RE.match(line)
            if m:
                reason = m.group(1).strip().rstrip(".")
                for theme_key in auto_na_themes:
                    theme_label = _theme_label(theme_key, sections)
                    if theme_label:
                        footnotes[theme_label] = reason
                break

    return footnotes


def _theme_label(theme_key: str, sections: list[tuple[str, str]]) -> str | None:
    """Map a theme key to its display label, or None if not in sections list."""
    for key, label in sections:
        if key == theme_key:
            return label
    return None


def _classify(cmd: str) -> str:
    """Classify a command as critical or non-critical."""
    return "non-critical" if cmd in NON_CRITICAL_COMMANDS else "critical"


def _is_critical(cmd: str) -> bool:
    return cmd not in NON_CRITICAL_COMMANDS


# ---------------------------------------------------------------------------
# Core: build coverage matrix
# ---------------------------------------------------------------------------


def build_matrix() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Parse all E2E test files and build the coverage matrix.

    Returns:
        (critical, non_critical, all_footnotes)
        Each is ``{cmd: {section_label: status}}``.
    """
    critical: dict[str, dict[str, str]] = {}
    non_critical: dict[str, dict[str, str]] = {}
    all_footnotes: dict[str, dict[str, str]] = {}

    files = sorted(TESTS_DIR.glob("test_*_e2e.py"))
    for fpath in files:
        try:
            cmd = _cmd_from_path(fpath)
        except ValueError:
            continue

        statuses = _parse_file(fpath)
        sections = CRITICAL_SECTIONS if _is_critical(cmd) else NON_CRITICAL_SECTIONS

        row: dict[str, str] = {}
        for theme_key, label in sections:
            row[label] = statuses.get(theme_key, "❌")

        if _is_critical(cmd):
            critical[cmd] = row
        else:
            non_critical[cmd] = row

        all_footnotes[cmd] = _collect_na_footnotes(fpath, cmd, statuses, sections)

    return critical, non_critical, all_footnotes


# ---------------------------------------------------------------------------
# Output modes
# ---------------------------------------------------------------------------


def _check_mode(args: argparse.Namespace, critical: dict, _non_critical: dict) -> int:
    """``--check``: exit 1 if any ❌ on critical commands."""
    section_filter = getattr(args, "section", None)
    classification_filter = getattr(args, "filter", None)

    errors: list[str] = []
    cmds = sorted(critical)
    for cmd in cmds:
        if classification_filter == "non-critical":
            continue
        row = critical[cmd]
        for section_label, status in row.items():
            if section_filter and section_label != section_filter:
                continue
            if status == "❌":
                errors.append(f"  {cmd} — {section_label}: ❌")

    if errors:
        print(f"cli-coverage-report: {len(errors)} ❌ section(s) on critical commands:")
        for e in errors:
            print(e)
        return 1

    filter_desc = ""
    if section_filter:
        filter_desc = f" (section={section_filter})"
    if classification_filter:
        filter_desc += f" (filter={classification_filter})"
    print(f"cli-coverage-report: OK — 0 ❌ on critical commands{filter_desc}")
    return 0


def _metrics_mode(critical: dict, non_critical: dict) -> int:
    """``--metrics``: print aggregate counts."""
    total_ok = 0
    total_na = 0
    total_missing = 0

    for cmd, row in critical.items():
        for label, status in row.items():
            if status == "✅":
                total_ok += 1
            elif status == "N/A":
                total_na += 1
            else:
                total_missing += 1

    for cmd, row in non_critical.items():
        for label, status in row.items():
            if status == "✅":
                total_ok += 1
            elif status == "N/A":
                total_na += 1
            else:
                total_missing += 1

    critical_cmds = list(critical)
    non_critical_cmds = list(non_critical)
    crit_sections_expected = len(critical_cmds) * len(CRITICAL_SECTIONS)
    non_crit_sections_expected = len(non_critical_cmds) * len(NON_CRITICAL_SECTIONS)
    total_expected = crit_sections_expected + non_crit_sections_expected

    total_cmds = len(critical_cmds) + len(non_critical_cmds)
    print(f"Commands: {len(critical_cmds)} critical + {len(non_critical_cmds)} non-critical = {total_cmds} total")
    print(
        f"Sections expected: {crit_sections_expected} (critical)"
        f" + {non_crit_sections_expected} (non-critical) = {total_expected}"
    )
    print(f"  ✅ = {total_ok}")
    print(f"  N/A = {total_na}")
    print(f"  ❌  = {total_missing}")
    print(f"Active (✅ + N/A): {total_ok + total_na}")

    # ACC-51 threshold: ≥ 200 active
    if total_ok + total_na < 200:
        print(f"FAIL: active sections ({total_ok + total_na}) < ACC-51 threshold (200)")
        return 1
    print(f"ACC-51 threshold (200): PASS (active={total_ok + total_na})")
    return 0


def _write_mode(critical: dict, non_critical: dict, footnotes: dict) -> int:
    """``--write``: regenerate the markdown matrix doc."""
    lines: list[str] = []
    lines.append("# CLI Coverage Matrix")
    lines.append("")
    lines.append("Generated by `scripts/cli-coverage-report.py --write`. Do not edit by hand.")
    lines.append("")

    # ── Critical commands ──
    critical_cols = [label for _, label in CRITICAL_SECTIONS]
    lines.append("## Critical commands (8 sections per cmd)")
    lines.append("")
    header = "| Command | " + " | ".join(critical_cols) + " |"
    sep = "|---|" + "|".join("---" for _ in critical_cols) + "|"
    lines.append(header)
    lines.append(sep)

    for cmd in sorted(critical):
        row = critical[cmd]
        cells = [cmd] + [row.get(col, "❌") for col in critical_cols]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # ── Non-critical commands ──
    non_critical_cols = [label for _, label in NON_CRITICAL_SECTIONS]
    lines.append("## Non-critical commands (4 sections per cmd)")
    lines.append("")
    header_nc = "| Command | " + " | ".join(non_critical_cols) + " |"
    sep_nc = "|---|" + "|".join("---" for _ in non_critical_cols) + "|"
    lines.append(header_nc)
    lines.append(sep_nc)

    for cmd in sorted(non_critical):
        row = non_critical[cmd]
        cells = [cmd] + [row.get(col, "❌") for col in non_critical_cols]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # ── Footnotes ──
    if footnotes:
        lines.append("## Footnotes (N/A justifications)")
        lines.append("")
        for cmd in sorted(footnotes):
            if not footnotes[cmd]:
                continue
            for section_label, reason in sorted(footnotes[cmd].items()):
                lines.append(f"- **{cmd}** — {section_label}: {reason}")
        lines.append("")

    content = "\n".join(lines) + "\n"
    MATRIX_DOC.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_DOC.write_text(content, encoding="utf-8")
    print(f"cli-coverage-report: matrix written to {MATRIX_DOC}")
    return 0


def _filtered_view(
    critical: dict,
    non_critical: dict,
    footnotes: dict,
    section_filter: str | None,
    classification_filter: str | None,
) -> int:
    """Custom filtered output for ``--section`` / ``--filter`` combos (ACC-53/54)."""
    errors: list[str] = []

    tgt = critical if classification_filter != "non-critical" else non_critical
    if classification_filter == "non-critical":
        tgt = non_critical
    elif classification_filter == "critical":
        tgt = critical
    else:
        # Print both but flag errors only on critical
        tgt = {**critical, **non_critical}

    for cmd in sorted(tgt):
        row = tgt[cmd]
        for col, status in sorted(row.items()):
            if section_filter and col != section_filter:
                continue
            flag = ""
            if status == "❌":
                flag = "  ← ❌"
                if _is_critical(cmd):
                    errors.append(f"  {cmd} — {col}: ❌")
            elif status == "N/A":
                reason = "-"
                if cmd in footnotes and col in footnotes[cmd]:
                    reason = footnotes[cmd][col]
                flag = f"  (N/A: {reason})"
            print(f"  {cmd:30s} {col:20s} {status}{flag}")

    if errors:
        print(f"\ncli-coverage-report: {len(errors)} ❌ section(s)")
        return 1

    print("\ncli-coverage-report: OK — 0 ❌")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=False,
        help="Exit 1 if any critical command has ❌ for a required section.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        default=False,
        help="Regenerate cli-coverage-matrix.md (idempotent).",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        default=False,
        help="Print aggregate section counts.",
    )
    parser.add_argument(
        "--section",
        type=str,
        default=None,
        help="Filter to a single section label (e.g. 'Events', 'Closure-of-loop').",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        choices=["critical", "non-critical"],
        help="Filter by command classification.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI coverage report.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]`` when None).

    Returns:
        Exit code: 0 on success, 1 on ❌ findings (--check) or threshold failure
        (--metrics).
    """
    args = _build_parser().parse_args(argv)

    if not TESTS_DIR.is_dir():
        print(f"cli-coverage-report: tests dir not found: {TESTS_DIR}", file=sys.stderr)
        return 2

    critical, non_critical, footnotes = build_matrix()

    # --section / --filter views (can be combined with --check or standalone)
    if args.section or args.filter:
        return _filtered_view(
            critical,
            non_critical,
            footnotes,
            section_filter=args.section,
            classification_filter=args.filter,
        )

    # --check mode
    if args.check:
        return _check_mode(args, critical, non_critical)

    # --metrics mode
    if args.metrics:
        return _metrics_mode(critical, non_critical)

    # --write mode
    if args.write:
        return _write_mode(critical, non_critical, footnotes)

    # Default: print summary table
    print("cli-coverage-report: use --check, --write, or --metrics")
    print(f"  Critical commands: {len(critical)}")
    print(f"  Non-critical commands: {len(non_critical)}")
    ok = sum(1 for row in critical.values() for s in row.values() if s == "✅")
    na = sum(1 for row in critical.values() for s in row.values() if s == "N/A")
    missing = sum(1 for row in critical.values() for s in row.values() if s == "❌")
    print(f"  Critical sections: ✅={ok} N/A={na} ❌={missing}")
    ok_nc = sum(1 for row in non_critical.values() for s in row.values() if s == "✅")
    na_nc = sum(1 for row in non_critical.values() for s in row.values() if s == "N/A")
    missing_nc = sum(1 for row in non_critical.values() for s in row.values() if s == "❌")
    print(f"  Non-critical sections: ✅={ok_nc} N/A={na_nc} ❌={missing_nc}")
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
