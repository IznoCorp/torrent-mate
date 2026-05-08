#!/usr/bin/env python3
"""Audit ``tests/feature_map/`` against the design docs they reference.

Performs a two-direction audit per DESIGN §7.2:

1. **Stale references** — anchors listed in a map file that no longer exist in
   the corresponding design doc. Severity: error from day 1 (the test doesn't
   compile against documentation).
2. **Orphan sections** — anchors present in the design doc that are not yet
   covered by any test and not waived in ``skip_audit``. Severity: warning
   without ``--strict``, error with ``--strict``.

Plus housekeeping:

- ``skip_audit`` entries with ``expires`` past today emit a warning (or an
  error with ``--strict-skip``).
- Map files referencing a missing design doc, malformed JSON, or invalid
  ``expires`` dates raise errors regardless of mode.

Exit codes:
  0 — no errors.
  1 — at least one error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ATX-style Markdown headings. Setext (``Title\n====``) is intentionally not
# supported — none of the project's docs use it for indexable sections.
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


def github_anchor(heading: str) -> str | None:
    r"""Compute the GitHub-style anchor fragment for a Markdown heading.

    Implements DESIGN §3.2.1:

    1. NFC-normalize (guards against NFD copies from macOS Finder).
    2. Lowercase.
    3. Strip characters not in ``[\\w\\s-]`` (Python regex ``\\w`` is
       Unicode-aware so accents/CJK/underscore survive; punctuation/emoji
       are removed).
    4. Replace each whitespace character with ``-`` (matches GitHub's
       per-character substitution; preserves runs as ``--``).
    5. Strip leading/trailing hyphens.

    Returns:
        The computed anchor, or ``None`` if the heading reduces to an empty
        string after processing.
    """
    text = unicodedata.normalize("NFC", heading)
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s", "-", text)
    text = text.strip("-")
    return text or None


def strip_fenced_code(content: str) -> str:
    """Drop lines inside fenced code blocks so embedded ``##`` lines are not parsed as headings."""
    out: list[str] = []
    in_block = False
    for line in content.split("\n"):
        if line.lstrip().startswith("```"):
            in_block = not in_block
            continue
        if not in_block:
            out.append(line)
    return "\n".join(out)


def parse_anchors(md_content: str) -> list[str]:
    """Parse all ATX headings into a deduplicated list of anchor fragments.

    Empty headings are skipped. Duplicate anchors get ``-1``, ``-2``, … suffixes
    in document order, matching GitHub's behavior.
    """
    seen: dict[str, int] = {}
    anchors: list[str] = []
    stripped = strip_fenced_code(md_content)
    for match in HEADING_RE.finditer(stripped):
        heading = match.group(2).strip()
        anchor = github_anchor(heading)
        if anchor is None:
            continue
        if anchor in seen:
            count = seen[anchor]
            seen[anchor] = count + 1
            anchors.append(f"{anchor}-{count}")
        else:
            seen[anchor] = 1
            anchors.append(anchor)
    return anchors


@dataclass(frozen=True)
class Finding:
    """One audit finding (error or warning)."""

    severity: str  # "error" | "warning"
    kind: str
    message: str


def audit(
    map_dir: Path,
    repo_root: Path,
    *,
    strict: bool,
    strict_skip: bool,
    today: date,
) -> list[Finding]:
    """Return the list of findings for all map files under ``map_dir``."""
    findings: list[Finding] = []
    if not map_dir.exists():
        return findings

    for map_path in sorted(map_dir.glob("*.json")):
        rel_map = map_path.relative_to(repo_root).as_posix()
        try:
            data = json.loads(map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(Finding("error", "invalid-json", f"{rel_map}: invalid JSON ({exc})"))
            continue

        # Shape validation runs first and unconditionally — a missing or
        # broken design field must not mask other shape problems in the
        # same file (otherwise each PR can only surface one shape error
        # at a time).
        sections = data.get("sections", {})
        if not isinstance(sections, dict):
            findings.append(Finding("error", "invalid-sections", f"{rel_map}: 'sections' must be an object"))
            sections = {}

        design_rel = data.get("design")
        design_present = isinstance(design_rel, str) and bool(design_rel)
        if not design_present:
            findings.append(Finding("error", "missing-design", f"{rel_map}: missing 'design' key"))
            doc_anchors: set[str] = set()
        else:
            design_abs = repo_root / design_rel
            if not design_abs.exists():
                findings.append(
                    Finding(
                        "error",
                        "missing-design-file",
                        f"{rel_map}: design doc {design_rel} does not exist",
                    )
                )
                doc_anchors = set()
            else:
                doc_anchors = set(parse_anchors(design_abs.read_text(encoding="utf-8")))

        if design_present and doc_anchors:
            for anchor in sections:
                if anchor not in doc_anchors:
                    findings.append(
                        Finding(
                            "error",
                            "stale-reference",
                            f"{rel_map}: anchor '#{anchor}' not found in {design_rel}",
                        )
                    )

        skip_anchors: set[str] = set()
        skip_list = data.get("skip_audit", [])
        # Validate the top-level shape before iterating: ``"skip_audit": null``
        # or any non-list value would otherwise raise ``TypeError`` below and
        # surface as a stack trace rather than an actionable finding.
        if not isinstance(skip_list, list):
            findings.append(
                Finding(
                    "error",
                    "invalid-skip-audit-shape",
                    f"{rel_map}: 'skip_audit' must be a list, got {type(skip_list).__name__}",
                )
            )
            skip_list = []
        for entry in skip_list:
            if not isinstance(entry, dict):
                findings.append(
                    Finding("error", "invalid-skip-audit", f"{rel_map}: skip_audit entry must be an object")
                )
                continue
            anchor = entry.get("anchor")
            if not isinstance(anchor, str) or not anchor:
                # A non-string / empty anchor cannot be matched against
                # doc_anchors below, so the corresponding section would
                # surface as 'orphan-section' — misleading. Emit a
                # dedicated finding so the real shape problem is fixed.
                findings.append(
                    Finding(
                        "error",
                        "invalid-skip-anchor",
                        f"{rel_map}: skip_audit entry has missing or non-string anchor: {entry!r}",
                    )
                )
            else:
                skip_anchors.add(anchor)
            anchor_label = anchor if isinstance(anchor, str) and anchor else "<missing>"
            # Per DESIGN §3.3.2, every skip_audit entry must declare a
            # category so future maintainers can tell "section will
            # never carry a contract" from "we're planning to add one".
            category = entry.get("category")
            if category not in ("documentation_only", "deferred_promotion"):
                findings.append(
                    Finding(
                        "error",
                        "invalid-skip-category",
                        (
                            f"{rel_map}: skip_audit '#{anchor_label}' has missing or unknown 'category' "
                            f"({category!r}); must be 'documentation_only' or 'deferred_promotion'"
                        ),
                    )
                )
            expires = entry.get("expires")
            if not isinstance(expires, str) or not expires:
                findings.append(
                    Finding(
                        "error",
                        "missing-expires",
                        f"{rel_map}: skip_audit '#{anchor_label}' is missing required 'expires' field",
                    )
                )
                continue
            try:
                exp = date.fromisoformat(expires)
            except ValueError:
                findings.append(
                    Finding(
                        "error",
                        "invalid-expires",
                        f"{rel_map}: skip_audit '#{anchor_label}' has invalid expires '{expires}'",
                    )
                )
                continue
            if exp < today:
                severity = "error" if strict_skip else "warning"
                findings.append(
                    Finding(
                        severity,
                        "expired-skip",
                        f"{rel_map}: skip_audit '#{anchor_label}' expired {expires}",
                    )
                )

        for anchor in sorted(doc_anchors):
            if anchor in skip_anchors:
                continue
            section = sections.get(anchor)
            if isinstance(section, dict) and section.get("tests"):
                continue
            severity = "error" if strict else "warning"
            findings.append(
                Finding(
                    severity,
                    "orphan-section",
                    f"{design_rel}: section '#{anchor}' has no tests",
                )
            )
    return findings


def report(findings: Iterable[Finding]) -> int:
    """Pretty-print findings and return the count of errors."""
    error_count = 0
    for finding in findings:
        prefix = "error" if finding.severity == "error" else "warn"
        stream = sys.stderr if finding.severity == "error" else sys.stdout
        print(f"{prefix}: [{finding.kind}] {finding.message}", file=stream)
        if finding.severity == "error":
            error_count += 1
    return error_count


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. See module docstring for modes."""
    # Module docstring's first line is the CLI description — guard against
    # the docstring being stripped (python -OO) so help still renders.
    description = (__doc__ or "").splitlines()[0] if __doc__ else None
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Treat orphan sections as errors. CI's design-gaps job runs "
            "with --strict so a regression here breaks the build."
        ),
    )
    parser.add_argument(
        "--strict-skip",
        action="store_true",
        help="Treat expired skip_audit entries as errors.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Override repo root (used by tests).",
    )
    parser.add_argument(
        "--today",
        help="ISO date used as today's date (testing override).",
    )
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    map_dir = repo_root / "tests" / "feature_map"
    today = date.fromisoformat(args.today) if args.today else date.today()

    findings = audit(
        map_dir,
        repo_root,
        strict=args.strict,
        strict_skip=args.strict_skip,
        today=today,
    )
    errors = report(findings)
    if errors == 0:
        print(f"audit: {len(findings)} finding(s), 0 error(s).")
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
