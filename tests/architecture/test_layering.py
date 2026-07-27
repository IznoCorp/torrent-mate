"""AST-based layering guard: core/ and conf/ must not import upward (arch-cleanup-2 Phase 2).

Enforces the architecture invariant from docs/reference/architecture.md:
core/ and conf/ are the lowest layers and must not import from api/, scraper/,
pipeline/, dispatch/, verify/, library/, indexer/, or trailers/.

Allow-listed exceptions (documented boundaries):
- personalscraper.logger — leaf utility, allow-listed in core/ and conf/
- core/app_context.py importing personalscraper.api.metadata.registry
  under TYPE_CHECKING — the AppContext boundary, already tested separately
- Per-line ``# layering: allow`` markers — a single import line may opt out of
  the guard when the upward dependency is a documented, intentional boundary
  (see the two markers in conf/models/_ranking.py and conf/loader.py). This is
  finer-grained than whole-module allow-listing so the rest of the file stays
  guarded. Each marked line MUST carry a justification comment.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "personalscraper"

# Upward targets that core/ and conf/ must never import at runtime.
_FORBIDDEN_PREFIXES = (
    "personalscraper.api",
    "personalscraper.scraper",
    "personalscraper.pipeline",
    "personalscraper.dispatch",
    "personalscraper.verify",
    "personalscraper.indexer",
    "personalscraper.trailers",
)

# Modules that are structural exceptions — checked independently elsewhere.
_ALLOWED_MODULES = {
    "personalscraper/core/app_context.py",  # TYPE_CHECKING registry import — AppContext boundary
}


def _is_type_checking_block(node: ast.AST, tree: ast.Module) -> bool:
    """Return True if ``node`` is nested inside an ``if TYPE_CHECKING:`` block."""
    for top in ast.walk(tree):
        if isinstance(top, ast.If):
            test = top.test
            is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            )
            if is_tc:
                # Walk body and orelse — if node is in this subtree it's guarded.
                for child in ast.walk(top):
                    if child is node:
                        return True
    return False


# Inline marker that exempts a single import line from the layering guard.
# Use sparingly, only for documented, intentional upward boundaries, and always
# alongside a justification comment. The justification may be trailing text on
# the marker line itself (``# layering: allow <why>``) OR an immediately
# preceding comment line. A bare ``# layering: allow`` with neither is rejected.
_ALLOW_MARKER = "# layering: allow"


def _marker_has_justification(source_lines: list[str], line_idx: int) -> bool:
    """Return True if the ``# layering: allow`` marker at ``line_idx`` is justified.

    A justification is REQUIRED (see this module's docstring). It is considered
    present when either:

    - there is non-empty text trailing the marker on the same line
      (``... import x  # layering: allow because <reason>``), OR
    - the immediately preceding source line is a non-empty comment
      (``# <reason>`` then the marked import on the next line).

    A bare ``# layering: allow`` with neither — no trailing text and no
    preceding comment — is unjustified and must still be treated as a violation.
    The two real markers (``conf/models/_ranking.py`` and ``conf/loader.py``)
    place their justification in a preceding comment, so both remain accepted.

    Args:
        source_lines: The file's source split into lines (no trailing newlines).
        line_idx: Zero-based index of the line carrying the marker.

    Returns:
        ``True`` if a justification accompanies the marker, ``False`` otherwise.
    """
    line = source_lines[line_idx]
    marker_pos = line.find(_ALLOW_MARKER)
    if marker_pos == -1:
        return False
    # (a) Trailing justification text after the marker on the same line.
    trailing = line[marker_pos + len(_ALLOW_MARKER) :].strip()
    if trailing:
        return True
    # (b) Immediately preceding non-empty comment line.
    if line_idx > 0:
        prev = source_lines[line_idx - 1].strip()
        if prev.startswith("#") and prev.lstrip("#").strip():
            return True
    return False


def _collect_violations_from_source(
    source: str, rel: str, prefixes: tuple[str, ...] = _FORBIDDEN_PREFIXES
) -> list[str]:
    """Return layering violations for ``source`` attributed to relative path ``rel``.

    Pure function: parses the given source text and applies the upward-import
    guard (TYPE_CHECKING exemption + justified ``# layering: allow`` exemption).
    Decoupled from the filesystem so the guard can be self-pinned with synthetic
    sources (positive/negative control tests) without writing probe files into
    the package tree.

    Args:
        source: Python source code to analyse.
        rel: Repo-relative POSIX path used both for the allow-list lookup and in
            the returned violation strings (e.g. ``"personalscraper/core/x.py"``).
        prefixes: Forbidden import prefixes to check against. Defaults to
            ``_FORBIDDEN_PREFIXES`` (the core/conf upward-import guard set).

    Returns:
        List of human-readable violation strings (empty if none).
    """
    if rel in _ALLOWED_MODULES:
        return []
    source_lines = source.splitlines()
    tree = ast.parse(source, filename=rel)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # Determine the full module name being imported.
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                # Reconstruct absolute path from relative imports.
                if node.level and node.level > 0:
                    # Relative import — resolve against the file's package.
                    pkg_parts = rel.replace(".py", "").replace("/", ".").split(".")
                    base = pkg_parts[: -(node.level)]
                    module = ".".join(base) + ("." + module if module else "")
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            else:
                continue
            # Check against forbidden prefixes.
            for prefix in prefixes:
                if module == prefix or module.startswith(prefix + "."):
                    # Allow if guarded by TYPE_CHECKING.
                    if _is_type_checking_block(node, tree):
                        break
                    # Allow if the import line carries an inline opt-out marker
                    # AND that marker is accompanied by a justification (trailing
                    # text or a preceding comment line). A bare, unjustified
                    # marker is still a violation — the marker docstring requires
                    # a justification for every opt-out.
                    line_idx = node.lineno - 1
                    if 0 <= line_idx < len(source_lines) and _ALLOW_MARKER in source_lines[line_idx]:
                        if _marker_has_justification(source_lines, line_idx):
                            break
                        violations.append(
                            f"{rel}:{node.lineno}: imports {module!r} with a bare "
                            f"'# layering: allow' marker and no justification"
                        )
                        break
                    violations.append(f"{rel}:{node.lineno}: imports {module!r}")
                    break
    return violations


def _collect_violations(py_file: Path) -> list[str]:
    """Return list of violation strings for ``py_file`` (filesystem wrapper)."""
    rel = py_file.relative_to(_REPO_ROOT).as_posix()
    return _collect_violations_from_source(py_file.read_text(encoding="utf-8"), rel)


def test_core_does_not_import_upward() -> None:
    """No module under core/ imports api/, scraper/, or any upper layer at runtime."""
    core_root = _PACKAGE_ROOT / "core"
    violations: list[str] = []
    for py_file in sorted(core_root.rglob("*.py")):
        violations.extend(_collect_violations(py_file))
    assert not violations, "core/ has upward import leaks (fix by importing from core._contracts):\n" + "\n".join(
        violations
    )


def test_conf_does_not_import_upward() -> None:
    """No module under conf/ imports api/, scraper/, or any upper layer at runtime."""
    conf_root = _PACKAGE_ROOT / "conf"
    violations: list[str] = []
    for py_file in sorted(conf_root.rglob("*.py")):
        violations.extend(_collect_violations(py_file))
    assert not violations, (
        "conf/ has upward import leaks (fix by importing from core._contracts "
        "or conf/models/_ranking.py):\n" + "\n".join(violations)
    )


def test_core_contracts_has_no_upward_deps() -> None:
    """core/_contracts.py imports nothing from personalscraper (only stdlib/enum)."""
    contracts_file = _PACKAGE_ROOT / "core" / "_contracts.py"
    assert contracts_file.exists(), "core/_contracts.py does not exist"
    source = contracts_file.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            else:
                continue
            assert not module.startswith("personalscraper."), (
                f"core/_contracts.py:{node.lineno}: must not import "
                f"from personalscraper — found {module!r}. "
                "Only stdlib and enum are allowed."
            )


# ---------------------------------------------------------------------------
# Self-pin control tests
#
# The three real-tree tests above pass *vacuously* today: the real core/ and
# conf/ trees carry zero unmarked upward imports, so an empty result is also
# what a broken (always-empty) guard would return. The synthetic-source control
# tests below feed known-bad and known-good inputs through
# ``_collect_violations_from_source`` so the guard is proven non-vacuous: it
# must flag the bad cases and exempt the good ones. If ``_collect_violations``
# ever rots into a no-op, ``test_unmarked_upward_import_is_flagged`` fails.
# ---------------------------------------------------------------------------

# Synthetic relative path used by the control tests — pretends to live under
# core/ so it is subject to the guard, but is never written to disk.
_SYNTHETIC_REL = "personalscraper/core/_synthetic_probe.py"


def test_unmarked_upward_import_is_flagged() -> None:
    """POSITIVE control: a bare upward import (no marker, no guard) IS a violation.

    This is the non-vacuous anchor — it feeds a known-bad source and asserts the
    guard reports it. If ``_collect_violations_from_source`` were broken into an
    always-empty stub, this assertion would fail.
    """
    source = "from personalscraper.api import x\n"
    violations = _collect_violations_from_source(source, _SYNTHETIC_REL)
    assert violations, "guard failed to flag an unmarked upward import (vacuous guard!)"
    assert "personalscraper.api" in violations[0]


def test_marked_upward_import_is_not_flagged() -> None:
    """NEGATIVE control: a justified ``# layering: allow`` import is exempt."""
    source = "from personalscraper.api import x  # layering: allow — documented boundary\n"
    violations = _collect_violations_from_source(source, _SYNTHETIC_REL)
    assert violations == [], f"justified marker should be exempt, got: {violations}"


def test_type_checking_guarded_upward_import_is_not_flagged() -> None:
    """NEGATIVE control: an import under ``if TYPE_CHECKING:`` is exempt."""
    source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from personalscraper.api import x\n"
    violations = _collect_violations_from_source(source, _SYNTHETIC_REL)
    assert violations == [], f"TYPE_CHECKING-guarded import should be exempt, got: {violations}"


def test_bare_marker_without_justification_is_flagged() -> None:
    """A ``# layering: allow`` with no justification at all is STILL a violation.

    No trailing text after the marker and no preceding comment line means the
    marker is unjustified, and the guard requires a justification for every
    opt-out — so the import remains a violation.
    """
    source = "from personalscraper.api import x  # layering: allow\n"
    violations = _collect_violations_from_source(source, _SYNTHETIC_REL)
    assert violations, "bare unjustified '# layering: allow' should still be a violation"
    assert "no justification" in violations[0]


def test_marker_justified_by_preceding_comment_is_not_flagged() -> None:
    """A marker justified by a preceding comment line is exempt.

    This mirrors the form used by the two real markers
    (``conf/models/_ranking.py`` and ``conf/loader.py``), whose justification
    lives in a comment on the line above the marked import.
    """
    source = (
        "# documented, intentional upward boundary — see arch-cleanup-2 Phase 2\n"
        "from personalscraper.api import x  # layering: allow\n"
    )
    violations = _collect_violations_from_source(source, _SYNTHETIC_REL)
    assert violations == [], f"marker justified by preceding comment should be exempt, got: {violations}"


def test_real_layering_markers_carry_justifications() -> None:
    """The two real ``# layering: allow`` markers in the tree are justified.

    Locates every real marker under ``personalscraper/`` and asserts each is
    justified (so the stricter enforcement does not regress them). Guards
    against someone adding a bare marker to the real tree.
    """
    marked: list[tuple[str, int]] = []
    for py_file in sorted(_PACKAGE_ROOT.rglob("*.py")):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            if _ALLOW_MARKER in line:
                rel = py_file.relative_to(_REPO_ROOT).as_posix()
                assert _marker_has_justification(lines, idx), (
                    f"{rel}:{idx + 1}: '# layering: allow' marker lacks a justification "
                    "(add trailing text or a preceding comment line)"
                )
                marked.append((rel, idx + 1))
    # Sanity: the two documented markers exist — keeps the test honest if the
    # tree ever loses them (would otherwise pass vacuously with zero markers).
    assert len(marked) >= 2, f"expected at least the 2 documented markers, found: {marked}"


# ---------------------------------------------------------------------------
# acquire/ layering guard — RP5c (D3)
#
# ``acquire/`` is the acquisition lobe. It must import downward only:
# ``api/``, ``core/``, ``conf/``, ``events/``. It must NEVER import the
# triage packages in ``_TRIAGE_PREFIXES``. The two control tests pin the guard
# non-vacuously: a synthetic triage import attributed under ``acquire/`` MUST be
# flagged (positive anchor); a downward ``api/`` import MUST NOT be (negative).
# ---------------------------------------------------------------------------

_TRIAGE_PREFIXES = (
    "personalscraper.ingest",
    "personalscraper.sort",
    "personalscraper.sorter",
    "personalscraper.process",
    "personalscraper.scraper",
    "personalscraper.dispatch",
    "personalscraper.indexer",
    "personalscraper.enforce",
    "personalscraper.verify",
    "personalscraper.insights",
    "personalscraper.maintenance",
    "personalscraper.reports",
    "personalscraper.trailers",
    "personalscraper.pipeline",
    "personalscraper.pipeline_steps",
    "personalscraper.commands",
)

_ACQUIRE_SYNTHETIC_REL = "personalscraper/acquire/_synthetic_probe.py"


def test_acquire_does_not_import_triage() -> None:
    """No module under acquire/ imports any triage package at runtime."""
    acquire_root = _PACKAGE_ROOT / "acquire"
    if not acquire_root.exists():
        return  # package not yet created — skip gracefully before Phase 01
    violations: list[str] = []
    for py_file in sorted(acquire_root.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        violations.extend(_collect_violations_from_source(py_file.read_text(encoding="utf-8"), rel, _TRIAGE_PREFIXES))
    assert not violations, "acquire/ has forbidden triage imports (it must only import downward):\n" + "\n".join(
        violations
    )


def test_acquire_triage_import_is_flagged() -> None:
    """POSITIVE control: a triage import attributed to acquire/ IS a violation (non-vacuous anchor)."""
    source = "from personalscraper.dispatch import something\n"
    violations = _collect_violations_from_source(source, _ACQUIRE_SYNTHETIC_REL, _TRIAGE_PREFIXES)
    assert violations, "acquire/ triage guard failed to flag a dispatch import (vacuous guard!)"
    assert "personalscraper.dispatch" in violations[0]


def test_acquire_downward_import_is_not_flagged() -> None:
    """NEGATIVE control: a downward import (api/) attributed to acquire/ is NOT a violation."""
    source = "from personalscraper.api import something\n"
    violations = _collect_violations_from_source(source, _ACQUIRE_SYNTHETIC_REL, _TRIAGE_PREFIXES)
    assert violations == [], f"downward api/ import should not be flagged, got: {violations}"


# ---------------------------------------------------------------------------
# Deleter ⇏ acquire/ guard — RP3 (D3 extended)
#
# ``maintenance/`` and ``dispatch/`` are the two deletion sites.  They must
# import ONLY ``core.delete_permit`` port types, never the concrete ``acquire/``
# implementation.  The concrete authority is injected at the composition root
# ($7.4 of DESIGN.md).  The three tests below share ONE scanner
# (``_scan_deleters_for_acquire_import`` → ``_collect_violations_from_source``)
# so the positive control is non-vacuous: if the scanner rots into a no-op the
# anchor test fails.
# ---------------------------------------------------------------------------

_DELETER_FORBIDDEN_ACQUIRE = ("personalscraper.acquire",)

_DELETER_MODULES: list[Path] = [
    _PACKAGE_ROOT / "maintenance",
    _PACKAGE_ROOT / "dispatch",
]


def _scan_deleters_for_acquire_import(module_dirs: list[Path]) -> list[str]:
    """Return violation strings for any ``personalscraper.acquire.*`` import.

    Walks every ``*.py`` under *module_dirs* and delegates to
    ``_collect_violations_from_source`` — the same scanner engine used by the
    core/conf and acquire/ guards.  Decoupled from the forbidden-prefix list
    so the positive/negative controls exercise the identical code path.

    Args:
        module_dirs: Package directories to scan recursively.

    Returns:
        List of human-readable violation strings (empty if none).
    """
    violations: list[str] = []
    for module_dir in module_dirs:
        if not module_dir.is_dir():
            continue
        for py_file in sorted(module_dir.rglob("*.py")):
            rel = py_file.relative_to(_REPO_ROOT).as_posix()
            try:
                source = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            violations.extend(_collect_violations_from_source(source, rel, _DELETER_FORBIDDEN_ACQUIRE))
    return violations


def test_deleters_do_not_import_acquire() -> None:
    """No module under dispatch/ or maintenance/ imports acquire/ at runtime."""
    violations = _scan_deleters_for_acquire_import(_DELETER_MODULES)
    assert not violations, (
        "dispatch/ or maintenance/ has forbidden acquire/ imports "
        "(deleters must only use core.delete_permit port types):\n" + "\n".join(violations)
    )


def test_deleter_acquire_import_is_flagged() -> None:
    """POSITIVE control: a synthetic dispatch/ file importing acquire/ IS flagged.

    Creates a temporary probe file on disk inside ``personalscraper/dispatch/``,
    runs the REAL scanner ``_scan_deleters_for_acquire_import`` over the dispatch/
    directory, and asserts the forbidden import is detected.  The probe is
    cleaned up in a ``finally`` block so it never persists in the tree.

    This is the non-vacuous anchor — if ``_collect_violations_from_source``
    were broken into an always-empty stub, this assertion would fail.
    """
    probe_path = _PACKAGE_ROOT / "dispatch" / "_synthetic_acquire_probe.py"
    assert not probe_path.exists(), (
        f"Probe file {probe_path} already exists — "
        "a previous test run may have leaked it. Delete it manually and re-run."
    )
    try:
        probe_path.write_text(
            "from personalscraper.acquire.store import ConcreteAcquireStore\n",
            encoding="utf-8",
        )
        violations = _scan_deleters_for_acquire_import([_PACKAGE_ROOT / "dispatch"])
        assert violations, (
            "deleter acquire guard failed to flag a synthetic acquire import "
            "(vacuous guard — the scanner did not detect the forbidden import)"
        )
        assert any("personalscraper.acquire" in v for v in violations), (
            f"expected 'personalscraper.acquire' in violation message, got: {violations}"
        )
    finally:
        if probe_path.exists():
            probe_path.unlink()


def test_deleter_core_import_is_not_flagged() -> None:
    """NEGATIVE control: a synthetic dispatch/ file importing ``core.delete_permit`` is NOT flagged.

    Same tmp-file discipline as the positive control.  ``core/`` is the neutral
    leaf — deleters are allowed (and expected) to depend on the port types.
    """
    probe_path = _PACKAGE_ROOT / "dispatch" / "_synthetic_core_probe.py"
    assert not probe_path.exists(), (
        f"Probe file {probe_path} already exists — "
        "a previous test run may have leaked it. Delete it manually and re-run."
    )
    try:
        probe_path.write_text(
            "from personalscraper.core.delete_permit import AllowAllPermit\n",
            encoding="utf-8",
        )
        violations = _scan_deleters_for_acquire_import([_PACKAGE_ROOT / "dispatch"])
        assert violations == [], f"core.delete_permit import was wrongly flagged as an acquire/ violation: {violations}"
    finally:
        if probe_path.exists():
            probe_path.unlink()


# ---------------------------------------------------------------------------
# Web layering guard — DESIGN §9 (D5)
#
# Engine packages must NEVER import ``personalscraper.web`` — the dependency
# is one-way: web may import engine packages, but engine packages must never
# import web.  This prevents async/sync mixing bugs and keeps the web boundary
# clean (DESIGN §9 mitigation: "architecture test asserts no
# personalscraper.web import from engine packages").
#
# The guard scans every package directory under ``personalscraper/`` except
# ``web/`` itself (and hidden / dunder dirs).  Two synthetic-source control
# tests pin the guard non-vacuously: a web import attributed to a core/ path
# MUST be flagged (positive anchor); a downward core/ import MUST NOT be
# flagged (negative anchor).
# ---------------------------------------------------------------------------

_WEB_FORBIDDEN_PREFIXES = ("personalscraper.web",)

# Every package directory under personalscraper/ EXCEPT web/ itself,
# hidden/dunder dirs (``__pycache__``), and the CLI composition root
# (``commands/`` — expected to wire web).  ``static/`` is served build
# output, never Python source.
_ENGINE_PACKAGE_DIRS: list[Path] = sorted(
    p
    for p in _PACKAGE_ROOT.iterdir()
    if p.is_dir()
    and not p.name.startswith("_")
    and not p.name.startswith(".")
    and p.name not in ("commands", "web", "static")
)


def test_engine_does_not_import_web() -> None:
    """No engine package or top-level module imports ``personalscraper.web`` (one-way dependency, DESIGN §9)."""
    violations: list[str] = []
    # Scan package directories (excluding web/, commands/, static/).
    for pkg_dir in _ENGINE_PACKAGE_DIRS:
        for py_file in sorted(pkg_dir.rglob("*.py")):
            rel = py_file.relative_to(_REPO_ROOT).as_posix()
            try:
                source = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            violations.extend(_collect_violations_from_source(source, rel, _WEB_FORBIDDEN_PREFIXES))
    # Also scan top-level .py modules under personalscraper/ (e.g. pipeline_steps.py,
    # pipeline.py, models.py).  The package-dir scan above misses them because they
    # are files, not directories.  Exclude dunder modules (__init__.py, __main__.py)
    # which are the package bootstrap — they are checked separately if needed.
    for py_file in sorted(_PACKAGE_ROOT.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        try:
            source = py_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        violations.extend(_collect_violations_from_source(source, rel, _WEB_FORBIDDEN_PREFIXES))
    assert not violations, (
        "Engine packages/modules must not import personalscraper.web (one-way dependency, DESIGN §9):\n"
        + "\n".join(violations)
    )


def test_engine_web_import_is_flagged() -> None:
    """POSITIVE control: a synthetic core/ file importing web IS flagged (non-vacuous anchor)."""
    source = "from personalscraper.web.app import create_app\n"
    violations = _collect_violations_from_source(source, _SYNTHETIC_REL, _WEB_FORBIDDEN_PREFIXES)
    assert violations, "web layering guard failed to flag a web import from engine (vacuous guard!)"
    assert "personalscraper.web" in violations[0]


def test_engine_core_import_is_not_flagged_by_web_guard() -> None:
    """NEGATIVE control: a downward import (core/) is NOT flagged by the web guard."""
    source = "from personalscraper.core.event_bus import Event\n"
    violations = _collect_violations_from_source(source, _SYNTHETIC_REL, _WEB_FORBIDDEN_PREFIXES)
    assert violations == [], f"downward core/ import should not be flagged by web guard, got: {violations}"
