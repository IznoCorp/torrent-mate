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

        design_rel = data.get("design")
        if not isinstance(design_rel, str) or not design_rel:
            findings.append(Finding("error", "missing-design", f"{rel_map}: missing 'design' key"))
            continue

        design_abs = repo_root / design_rel
        if not design_abs.exists():
            findings.append(
                Finding(
                    "error",
                    "missing-design-file",
                    f"{rel_map}: design doc {design_rel} does not exist",
                )
            )
            continue

        doc_anchors = set(parse_anchors(design_abs.read_text(encoding="utf-8")))
        sections = data.get("sections", {})
        if not isinstance(sections, dict):
            findings.append(Finding("error", "invalid-sections", f"{rel_map}: 'sections' must be an object"))
            sections = {}

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
        for entry in data.get("skip_audit", []):
            if not isinstance(entry, dict):
                findings.append(
                    Finding("error", "invalid-skip-audit", f"{rel_map}: skip_audit entry must be an object")
                )
                continue
            anchor = entry.get("anchor")
            if isinstance(anchor, str):
                skip_anchors.add(anchor)
            expires = entry.get("expires")
            if isinstance(expires, str):
                try:
                    exp = date.fromisoformat(expires)
                except ValueError:
                    findings.append(
                        Finding(
                            "error",
                            "invalid-expires",
                            f"{rel_map}: skip_audit '#{anchor}' has invalid expires '{expires}'",
                        )
                    )
                    continue
                if exp < today:
                    severity = "error" if strict_skip else "warning"
                    findings.append(
                        Finding(
                            severity,
                            "expired-skip",
                            f"{rel_map}: skip_audit '#{anchor}' expired {expires}",
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
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat orphan sections as errors (used post-cycle-4).",
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
