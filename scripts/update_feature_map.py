#!/usr/bin/env python3
"""Scan tests/ for Design: markers and write tests/feature_map/<codename>.json.

Markers are extracted from function/method docstrings via ``ast.get_docstring``
(``FunctionDef`` and ``AsyncFunctionDef`` only — module/class docstrings are
ignored). Tests with a ``Design:`` line but no matching ``Contract:`` line in
the same docstring are skipped with a warning. Multiple ``Design:`` lines per
docstring are allowed (cross-cutting tests).

Per-feature map files preserve ``skip_audit`` entries on regeneration so
hand-curated audit waivers survive across runs.

Modes:
  default  — write/update map files in-place; exit 0.
  --check  — compare expected output against committed files; exit 1 on drift.

Exit codes:
  0 — success / no drift.
  1 — drift detected, codename collision, or write error.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

# Allow ``import _codename_overrides`` whether the script is invoked directly,
# imported from tests with pythonpath = ["scripts"], or executed from any cwd.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# noqa: E402 — sys.path is mutated above to make this import resolvable
# regardless of how the script is invoked, so the import must follow.
from _codename_overrides import resolve_codename  # noqa: E402

REPO_ROOT = _SCRIPTS_DIR.parent

DESIGN_RE = re.compile(r"^\s*Design:\s*(\S+?)#(\S+?)\s*$", re.MULTILINE)
CONTRACT_RE = re.compile(r"^\s*Contract:\s*\S", re.MULTILINE)


@dataclass(frozen=True)
class MarkerEntry:
    """Single ``Design:`` marker hit located in a test function."""

    design_path: str
    anchor: str
    test_id: str


def iter_test_functions(
    path: Path,
    repo_root: Path,
    parse_errors: list[str] | None = None,
) -> Iterator[tuple[str, str | None]]:
    """Yield ``(test_id, docstring)`` pairs for every function/method in ``path``.

    Args:
        path: Absolute path to a Python source file.
        repo_root: Repo root used to derive a stable relative test id.
        parse_errors: Optional list to which parse-failure relpaths get
            appended. Lets ``--check`` callers fail loudly when a test
            file we can't parse may have stale Design: markers.

    Yields:
        ``(test_id, docstring)`` where ``test_id`` follows the
        ``tests/<...>.py::[Class::]function`` convention used by pytest.
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        # A test file we can't parse may carry Design: markers that
        # silently disappear from the feature map. Surface the warning
        # so a broken test file does not regress coverage tracking,
        # and let --check callers escalate the exit code.
        rel = path.relative_to(repo_root).as_posix() if path.is_relative_to(repo_root) else str(path)
        print(
            f"warn: {rel}: skipped while collecting markers ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        if parse_errors is not None:
            parse_errors.append(rel)
        return

    rel = path.relative_to(repo_root).as_posix()

    def visit(node: ast.AST, prefix: str) -> Iterator[tuple[str, str | None]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                doc = ast.get_docstring(child, clean=True)
                test_id = f"{rel}::{prefix}{child.name}" if prefix else f"{rel}::{child.name}"
                yield test_id, doc
            elif isinstance(child, ast.ClassDef):
                yield from visit(child, f"{prefix}{child.name}::")

    yield from visit(tree, "")


def collect_markers(
    tests_dir: Path,
    repo_root: Path,
) -> tuple[list[MarkerEntry], list[str], list[str]]:
    """Walk ``tests_dir`` and extract Design markers.

    Args:
        tests_dir: Root directory to recurse into (typically ``<repo>/tests``).
        repo_root: Repo root used for relative test ids.

    Returns:
        ``(entries, warnings, parse_errors)``: ``warnings`` lists test ids
        that have a ``Design:`` line but no matching ``Contract:`` line in the
        same docstring; ``parse_errors`` lists relative paths of test files
        that could not be parsed (their markers, if any, are missing from
        the map and ``--check`` must fail).
    """
    entries: list[MarkerEntry] = []
    warnings: list[str] = []
    parse_errors: list[str] = []
    feature_map_dir = tests_dir / "feature_map"

    for path in sorted(tests_dir.rglob("*.py")):
        if feature_map_dir in path.parents:
            continue
        for test_id, doc in iter_test_functions(path, repo_root, parse_errors=parse_errors):
            if not doc:
                continue
            design_hits = DESIGN_RE.findall(doc)
            if not design_hits:
                continue
            if not CONTRACT_RE.search(doc):
                warnings.append(test_id)
                continue
            for design_path, anchor in design_hits:
                entries.append(MarkerEntry(design_path=design_path, anchor=anchor, test_id=test_id))
    return entries, warnings, parse_errors


def build_maps(
    entries: Iterable[MarkerEntry],
) -> tuple[dict[str, dict[str, object]], list[tuple[str, str, str]]]:
    """Group markers by codename and detect codename collisions.

    Args:
        entries: Marker entries from :func:`collect_markers`.

    Returns:
        ``(maps, collisions)`` where ``maps`` is keyed by codename with the
        canonical map structure (``feature``, ``design``, ``sections``), and
        ``collisions`` lists ``(codename, first_design_path, conflicting_path)``
        tuples for unmappable conflicts.
    """
    maps: dict[str, dict[str, object]] = {}
    collisions: list[tuple[str, str, str]] = []

    for entry in entries:
        codename = resolve_codename(entry.design_path)
        existing = maps.get(codename)
        if existing is None:
            maps[codename] = {
                "feature": codename,
                "design": entry.design_path,
                "sections": {entry.anchor: {"tests": [entry.test_id]}},
            }
            continue
        if existing["design"] != entry.design_path:
            collisions.append((codename, str(existing["design"]), entry.design_path))
            continue
        sections = existing["sections"]
        assert isinstance(sections, dict)
        section = sections.setdefault(entry.anchor, {"tests": []})
        tests_list = section["tests"]
        assert isinstance(tests_list, list)
        if entry.test_id not in tests_list:
            tests_list.append(entry.test_id)

    for payload in maps.values():
        sections = payload["sections"]
        assert isinstance(sections, dict)
        for section in sections.values():
            section["tests"] = sorted(section["tests"])
        payload["sections"] = dict(sorted(sections.items()))
    return maps, collisions


def render_payload(payload: dict[str, object], existing_skip_audit: list[object]) -> str:
    """Render a map payload to canonical JSON, preserving skip_audit.

    Args:
        payload: Generated payload (without skip_audit).
        existing_skip_audit: Skip-audit list read from the committed file.

    Returns:
        JSON text with trailing newline, indent=2, UTF-8.
    """
    final = dict(payload)
    final["skip_audit"] = existing_skip_audit
    return json.dumps(final, indent=2, ensure_ascii=False) + "\n"


class SkipAuditCorrupt(RuntimeError):
    """Raised when an existing map file's skip_audit cannot be re-read.

    Re-generating the map silently in this case would clobber hand-curated
    audit waivers with an empty list — a destructive silent failure on a
    long-lived artifact. The CLI converts this to an error exit so a
    human resolves the corruption explicitly.
    """


def read_existing_skip_audit(path: Path) -> list[object]:
    """Return the ``skip_audit`` list from an existing map file.

    Returns ``[]`` if the file does not exist (fresh codename). Raises
    :class:`SkipAuditCorrupt` if the file exists but is unreadable or has
    a non-list ``skip_audit`` field — never silently overwrites curated
    waivers with an empty list.
    """
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SkipAuditCorrupt(f"{path}: invalid JSON ({exc})") from exc
    skip = data.get("skip_audit", [])
    if not isinstance(skip, list):
        raise SkipAuditCorrupt(f"{path}: 'skip_audit' must be a list, got {type(skip).__name__}")
    return skip


def diff_maps(maps: dict[str, dict[str, object]], map_dir: Path) -> list[Path]:
    """Return the list of map files that would change vs the committed state."""
    drifts: list[Path] = []
    expected: set[str] = set()
    for codename, payload in maps.items():
        path = map_dir / f"{codename}.json"
        expected.add(path.name)
        rendered = render_payload(payload, read_existing_skip_audit(path))
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if rendered != current:
            drifts.append(path)

    if map_dir.exists():
        for path in sorted(map_dir.glob("*.json")):
            if path.name not in expected:
                drifts.append(path)
    return drifts


def write_maps(maps: dict[str, dict[str, object]], map_dir: Path) -> list[Path]:
    """Write/update map files in-place. Returns the list of paths actually changed."""
    map_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    expected: set[str] = set()
    for codename, payload in maps.items():
        path = map_dir / f"{codename}.json"
        expected.add(path.name)
        rendered = render_payload(payload, read_existing_skip_audit(path))
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if rendered != current:
            path.write_text(rendered, encoding="utf-8")
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point. See module docstring for modes."""
    # Module docstring's first line is the CLI description — guard against
    # the docstring being stripped (python -OO) so help still renders.
    description = (__doc__ or "").splitlines()[0] if __doc__ else None
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed map files are up-to-date; exit 1 on drift.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Override repo root (used by tests).",
    )
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    tests_dir = repo_root / "tests"
    map_dir = tests_dir / "feature_map"

    entries, warnings, parse_errors = collect_markers(tests_dir, repo_root)
    maps, collisions = build_maps(entries)

    if collisions:
        print("error: codename collisions detected:", file=sys.stderr)
        for codename, first, second in collisions:
            print(f"  {codename!r}: {first} ↔ {second}", file=sys.stderr)
        return 1

    for tid in warnings:
        print(f"warn: {tid}: Design: marker without matching Contract: — skipped", file=sys.stderr)

    if parse_errors:
        # A test file we couldn't parse may carry Design: markers that are
        # now silently absent from the map. Refuse to drop them: --check
        # fails loudly; the regen mode also fails to avoid persisting an
        # incomplete map that erases waivers via the diff path.
        print(
            f"error: {len(parse_errors)} test file(s) failed to parse — markers may be missing from the map.",
            file=sys.stderr,
        )
        return 1

    try:
        if args.check:
            drifts = diff_maps(maps, map_dir)
            if drifts:
                print(
                    "error: tests/feature_map/ is stale. Run `python3 scripts/update_feature_map.py`.",
                    file=sys.stderr,
                )
                for path in drifts:
                    print(f"  drift: {path.relative_to(repo_root)}", file=sys.stderr)
                return 1
            return 0

        written = write_maps(maps, map_dir)
    except SkipAuditCorrupt as exc:
        # Refuse to overwrite a curated skip_audit list with an empty one
        # — a corrupt or hand-edited map must be repaired by a human.
        print(f"error: {exc}", file=sys.stderr)
        print(
            "       Repair the map file (or revert to the last good revision) before re-running.",
            file=sys.stderr,
        )
        return 1

    for path in written:
        print(f"updated: {path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
