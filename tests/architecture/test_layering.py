"""AST-based layering guard: core/ and conf/ must not import upward (arch-cleanup-2 Phase 2).

Enforces the architecture invariant from docs/production/architecture.md:
core/ and conf/ are the lowest layers and must not import from api/, scraper/,
pipeline/, dispatch/, verify/, library/, indexer/, or trailers/.

Allow-listed exceptions (documented boundaries):
- personalscraper.logger — leaf utility, allow-listed in core/ and conf/
- core/app_context.py importing personalscraper.api.metadata.registry
  under TYPE_CHECKING — the AppContext boundary, already tested separately
- Per-line ``# layering: allow`` markers — a single import line may opt out of
  the guard when the upward dependency is a documented, intentional boundary
  (see the marker in conf/loader.py). This is
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


# ---------------------------------------------------------------------------
# conf/ ↛ api/ (the cycle's guard)
#
# api/ imports conf/ (provider clients read their config models), so conf/ is
# the lower layer. The generic guard above lets a ``# layering: allow`` marker
# hide an upward import; that escape hatch is how the conf ↔ api cycle lived on.
# This guard has no marker exemption: conf/ never imports api/ at runtime.
# ---------------------------------------------------------------------------


def _runtime_api_imports(source: str) -> list[int]:
    """Return the line numbers of runtime ``personalscraper.api`` imports in ``source``.

    Args:
        source: Python source code to analyse.

    Returns:
        Line numbers of imports of ``personalscraper.api`` (or a submodule) not
        nested in an ``if TYPE_CHECKING:`` block. A ``# layering: allow`` marker
        does NOT exempt them.
    """
    tree = ast.parse(source)
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        elif isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        else:
            continue
        if any(m == "personalscraper.api" or m.startswith("personalscraper.api.") for m in modules):
            if not _is_type_checking_block(node, tree):
                lines.append(node.lineno)
    return lines


def test_conf_never_imports_api_even_with_marker() -> None:
    """conf/ must not import api/ at runtime, ``# layering: allow`` or not."""
    violations: list[str] = []
    for py_file in sorted((_PACKAGE_ROOT / "conf").rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        violations.extend(f"{rel}:{n}" for n in _runtime_api_imports(py_file.read_text(encoding="utf-8")))
    assert not violations, "conf/ imports api/ (the conf <-> api cycle; move the shared piece to core/):\n" + "\n".join(
        violations
    )


def test_marked_api_import_is_still_flagged_by_cycle_guard() -> None:
    """POSITIVE control: a marker-exempted api import IS flagged by the cycle guard."""
    source = "from personalscraper.api.torrent import X  # layering: allow because\n"
    assert _runtime_api_imports(source) == [1]


def test_type_checking_api_import_is_not_flagged_by_cycle_guard() -> None:
    """NEGATIVE control: an api import under TYPE_CHECKING is not a runtime edge."""
    source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from personalscraper.api import x\n"
    assert _runtime_api_imports(source) == []


# ---------------------------------------------------------------------------
# app/ (the application layer) is freed of HTTP: it imports neither fastapi nor
# starlette (backend-brief § 5 Q11).  ``test_engine_does_not_import_web`` already
# covers ``personalscraper.web``; this one covers the HTTP frameworks.  A
# TYPE_CHECKING import is exempt, as everywhere in this file.
# ---------------------------------------------------------------------------

_APP_HTTP_FORBIDDEN_PREFIXES = ("fastapi", "starlette")
_APP_PACKAGE_DIR = _PACKAGE_ROOT / "app"
_APP_SYNTHETIC_REL = "personalscraper/app/_synthetic_probe.py"


def test_app_does_not_import_http() -> None:
    """No module under ``personalscraper/app/`` imports ``fastapi`` or ``starlette`` at runtime."""
    assert _APP_PACKAGE_DIR.is_dir(), "personalscraper/app/ is missing (the guard would scan nothing)"
    violations: list[str] = []
    for py_file in sorted(_APP_PACKAGE_DIR.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        source = py_file.read_text(encoding="utf-8")
        violations.extend(_collect_violations_from_source(source, rel, _APP_HTTP_FORBIDDEN_PREFIXES))
    assert not violations, "app/ must not import an HTTP framework (the application layer is HTTP-free):\n" + "\n".join(
        violations
    )


def test_app_http_import_is_flagged() -> None:
    """POSITIVE control: a synthetic app/ file importing fastapi IS flagged (non-vacuous anchor)."""
    source = "from fastapi import HTTPException\n"
    violations = _collect_violations_from_source(source, _APP_SYNTHETIC_REL, _APP_HTTP_FORBIDDEN_PREFIXES)
    assert violations, "app HTTP guard failed to flag a fastapi import (vacuous guard!)"
    assert "fastapi" in violations[0]


# ---------------------------------------------------------------------------
# The v1 interface (``http_v1/``) and the application layer, one direction:
# http_v1 → app → engine. ``app/`` never imports ``http_v1`` (the services
# know no HTTP interface); ``http_v1/`` never imports the engine (a route
# reaches it only through a service); and no ``http_v1/`` route carries a
# ``Depends(require…)`` of its own (the perimeter is the ONE dependency).
# ``test_engine_does_not_import_web`` already keeps ``http_v1/`` off v0.
# ---------------------------------------------------------------------------

_HTTP_V1_PACKAGE_DIR = _PACKAGE_ROOT / "http_v1"
_HTTP_V1_SYNTHETIC_REL = "personalscraper/http_v1/_synthetic_probe.py"
_APP_HTTP_V1_FORBIDDEN_PREFIXES = ("personalscraper.http_v1",)

# What http_v1/ may import from the package: the application layer, the config,
# the core, the logger. Every other top-level package or module is the engine.
_HTTP_V1_ALLOWED_TOP_LEVEL = frozenset({"app", "conf", "core", "logger", "config", "http_v1"})
_HTTP_V1_ENGINE_PREFIXES: tuple[str, ...] = tuple(
    sorted(
        f"personalscraper.{entry.stem if entry.is_file() else entry.name}"
        for entry in _PACKAGE_ROOT.iterdir()
        if not entry.name.startswith("__")
        and not entry.name.startswith(".")
        and (entry.is_dir() or entry.suffix == ".py")
        and (entry.stem if entry.is_file() else entry.name) not in _HTTP_V1_ALLOWED_TOP_LEVEL
    )
)

_REQUIRE_DEPENDENCY = "Depends(require"


def test_app_does_not_import_http_v1() -> None:
    """No module under ``personalscraper/app/`` imports ``personalscraper.http_v1`` at runtime."""
    violations: list[str] = []
    for py_file in sorted(_APP_PACKAGE_DIR.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        source = py_file.read_text(encoding="utf-8")
        violations.extend(_collect_violations_from_source(source, rel, _APP_HTTP_V1_FORBIDDEN_PREFIXES))
    assert not violations, "app/ must not import the v1 interface (http_v1 -> app, never back):\n" + "\n".join(
        violations
    )


def test_app_http_v1_import_is_flagged() -> None:
    """POSITIVE control: a synthetic app/ file importing http_v1 IS flagged (non-vacuous anchor)."""
    source = "from personalscraper.http_v1.app import V1_PREFIX\n"
    violations = _collect_violations_from_source(source, _APP_SYNTHETIC_REL, _APP_HTTP_V1_FORBIDDEN_PREFIXES)
    assert violations, "app -> http_v1 guard failed to flag an http_v1 import (vacuous guard!)"
    assert "personalscraper.http_v1" in violations[0]


def test_http_v1_does_not_import_the_engine() -> None:
    """No module under ``personalscraper/http_v1/`` imports the engine: a route reaches it through a service."""
    assert _HTTP_V1_PACKAGE_DIR.is_dir(), "personalscraper/http_v1/ is missing (the guard would scan nothing)"
    assert "personalscraper.api" in _HTTP_V1_ENGINE_PREFIXES, "the engine list is empty or wrong"
    violations: list[str] = []
    for py_file in sorted(_HTTP_V1_PACKAGE_DIR.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        source = py_file.read_text(encoding="utf-8")
        violations.extend(_collect_violations_from_source(source, rel, _HTTP_V1_ENGINE_PREFIXES))
    assert not violations, "http_v1/ must not import the engine (go through an app/ service):\n" + "\n".join(violations)


def test_http_v1_engine_import_is_flagged() -> None:
    """POSITIVE control: a synthetic http_v1/ file importing the engine IS flagged (non-vacuous anchor)."""
    source = "from personalscraper.indexer.db import apply_migrations\n"
    violations = _collect_violations_from_source(source, _HTTP_V1_SYNTHETIC_REL, _HTTP_V1_ENGINE_PREFIXES)
    assert violations, "http_v1 -> engine guard failed to flag an indexer import (vacuous guard!)"
    assert "personalscraper.indexer" in violations[0]


def test_http_v1_app_import_is_not_flagged() -> None:
    """NEGATIVE control: an app/ import from http_v1/ is the allowed direction."""
    source = (
        "from personalscraper.app.errors import AppRefusal\nfrom personalscraper.conf.models.config import Config\n"
    )
    violations = _collect_violations_from_source(source, _HTTP_V1_SYNTHETIC_REL, _HTTP_V1_ENGINE_PREFIXES)
    assert violations == [], f"http_v1 -> app/conf imports wrongly flagged: {violations}"


def _require_dependency_lines(source: str) -> list[int]:
    """Return the line numbers of a ``Depends(require…)`` in ``source`` (a text scan).

    Args:
        source: Python source code.

    Returns:
        The 1-based line numbers carrying the pattern.
    """
    return [number for number, line in enumerate(source.splitlines(), start=1) if _REQUIRE_DEPENDENCY in line]


def test_http_v1_routes_carry_no_guard_of_their_own() -> None:
    """No ``Depends(require…)`` anywhere in ``http_v1/``: the perimeter is the single guard."""
    violations: list[str] = []
    for py_file in sorted(_HTTP_V1_PACKAGE_DIR.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        violations.extend(f"{rel}:{n}" for n in _require_dependency_lines(py_file.read_text(encoding="utf-8")))
    assert not violations, "http_v1/ routes carry their own guard (the perimeter is the only one):\n" + "\n".join(
        violations
    )


def test_planted_require_dependency_is_flagged() -> None:
    """POSITIVE control: a planted per-route guard IS flagged (non-vacuous anchor)."""
    source = "def route(_: Annotated[None, Depends(require_session)]) -> None: ...\n"
    assert _require_dependency_lines(source) == [1]


# ---------------------------------------------------------------------------
# i18n/ layering guard — the translation layer is a leaf
#
# Every surface (CLI, Telegram, app, web) imports ``personalscraper.i18n``; if it
# imported any of them back, the layer would close a cycle. It may import the
# logger only.
# ---------------------------------------------------------------------------


def _personalscraper_imports(source: str) -> set[str]:
    """Absolute ``personalscraper`` modules a source imports (relative imports excluded)."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name.split(".")[0] == "personalscraper")
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] == "personalscraper":
                modules.add(node.module)
    return modules


def test_i18n_imports_only_the_logger() -> None:
    """``personalscraper.i18n`` imports nothing from ``personalscraper`` but ``personalscraper.logger``."""
    i18n_root = _PACKAGE_ROOT / "i18n"
    assert i18n_root.exists(), "personalscraper/i18n does not exist"
    leaks: list[str] = []
    for py_file in sorted(i18n_root.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        for module in sorted(_personalscraper_imports(py_file.read_text(encoding="utf-8"))):
            if module not in {"personalscraper.logger", "personalscraper.i18n"} and not module.startswith(
                "personalscraper.i18n."
            ):
                leaks.append(f"{rel}: imports {module!r}")
    assert not leaks, "i18n/ must import only personalscraper.logger:\n" + "\n".join(leaks)


def test_i18n_import_scan_flags_an_upward_import() -> None:
    """POSITIVE control: the scanner reports a ``personalscraper`` import (non-vacuous anchor)."""
    assert _personalscraper_imports("from personalscraper.app import x\nimport os\n") == {"personalscraper.app"}


# ---------------------------------------------------------------------------
# Import leaks closed by guards: three directions with NO exemption. The
# ``# layering: allow`` marker is NOT honoured by these guards, and an import
# under ``TYPE_CHECKING`` is exempt (it is not a runtime edge).
# ---------------------------------------------------------------------------

_PACKAGE_NAME = "personalscraper"
_EVENTS_PACKAGE_DIR = _PACKAGE_ROOT / "events"
_EVENTS_SYNTHETIC_REL = "personalscraper/events/_synthetic_probe.py"


def _in_type_checking_body(node: ast.AST, tree: ast.Module) -> bool:
    """Return True if ``node`` sits in the BODY of an ``if TYPE_CHECKING:`` (its ``else:`` runs at runtime)."""
    for top in ast.walk(tree):
        if not isinstance(top, ast.If):
            continue
        test = top.test
        if (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        ):
            if any(child is node for statement in top.body for child in ast.walk(statement)):
                return True
    return False


def _runtime_import_targets(source: str, rel: str) -> list[tuple[int, str, tuple[str, ...]]]:
    """Return the runtime ``personalscraper`` imports of ``source``, relative imports resolved.

    Args:
        source: Python source code.
        rel: Repo-relative POSIX path of the file, used to resolve relative imports.

    Returns:
        One ``(line, module, names)`` triple per import statement that is not under ``TYPE_CHECKING``:
        ``module`` is the absolute dotted module, ``names`` the names imported from it (empty for a
        plain ``import x.y``).
    """
    tree = ast.parse(source, filename=rel)
    package_parts = rel.removesuffix(".py").split("/")[:-1]
    targets: list[tuple[int, str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found = [(alias.name, ()) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - (node.level - 1)]
                module = ".".join([*base, *([node.module] if node.module else [])])
            else:
                module = node.module or ""
            found = [(module, tuple(alias.name for alias in node.names))]
        else:
            continue
        if _in_type_checking_body(node, tree):
            continue
        targets.extend(
            (node.lineno, module, names)
            for module, names in found
            if module == _PACKAGE_NAME or module.startswith(f"{_PACKAGE_NAME}.")
        )
    return targets


def _engine_top_levels() -> frozenset[str]:
    """Return the names of the engine: every top-level package or module of ``personalscraper`` but ``app``."""
    return frozenset(
        entry.stem if entry.is_file() else entry.name
        for entry in _PACKAGE_ROOT.iterdir()
        if not entry.name.startswith(".")
        and entry.name != "__pycache__"
        and (entry.is_dir() or entry.suffix == ".py")
        and entry.name not in {"app", "__init__.py", "__main__.py"}
    )


def _private_engine_imports(source: str, rel: str, engine: frozenset[str]) -> list[str]:
    """Return the runtime imports of an engine module through a ``_`` segment or a ``_`` name.

    Args:
        source: Python source code.
        rel: Repo-relative POSIX path of the file.
        engine: The engine's top-level names.

    Returns:
        One human-readable violation per offending import (empty if none).
    """
    violations: list[str] = []
    for line, module, names in _runtime_import_targets(source, rel):
        segments = module.split(".")[1:]
        if module == _PACKAGE_NAME:
            # ``from personalscraper import _fs_utils`` reaches an engine module through a name.
            violations.extend(
                f"{rel}:{line}: imports the private engine module {_PACKAGE_NAME}.{name}"
                for name in names
                if name.startswith("_") and not name.startswith("__") and name in engine
            )
            continue
        if not segments or segments[0] not in engine:
            continue
        if any(segment.startswith("_") for segment in segments):
            violations.append(f"{rel}:{line}: imports the private engine module {module}")
        violations.extend(
            f"{rel}:{line}: imports the private name {name} from {module}" for name in names if name.startswith("_")
        )
    return violations


def test_app_imports_only_public_engine_apis() -> None:
    """No ``app/`` module imports, at runtime, a private engine module or a private name of one.

    The engine is every top-level package or module of ``personalscraper`` but ``app``; "private" is a
    dotted segment after ``personalscraper`` (or an imported name) starting with ``_``.
    """
    engine = _engine_top_levels()
    assert {"api", "core", "conf", "acquire", "events"} <= engine, f"the engine list is wrong: {sorted(engine)}"
    violations: list[str] = []
    for py_file in sorted(_APP_PACKAGE_DIR.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        violations.extend(_private_engine_imports(py_file.read_text(encoding="utf-8"), rel, engine))
    assert not violations, "app/ reaches into the engine's private modules (import the public path):\n" + "\n".join(
        violations
    )


def test_app_private_engine_module_import_is_flagged() -> None:
    """POSITIVE control: a synthetic app/ file importing a ``_`` engine module IS flagged."""
    source = "from personalscraper.core.sqlite._pragmas import apply_pragmas\n"
    violations = _private_engine_imports(source, _APP_SYNTHETIC_REL, _engine_top_levels())
    assert len(violations) == 1, "app private-module guard failed to flag a private engine module (vacuous guard!)"
    assert "personalscraper.core.sqlite._pragmas" in violations[0]


def test_app_private_engine_name_import_is_flagged() -> None:
    """POSITIVE control: a synthetic app/ file importing a ``_`` name from an engine module IS flagged."""
    source = "from personalscraper.conf.loader import _load_json5_file\n"
    violations = _private_engine_imports(source, _APP_SYNTHETIC_REL, _engine_top_levels())
    assert len(violations) == 1, "app private-name guard failed to flag a private engine name (vacuous guard!)"
    assert "_load_json5_file" in violations[0]


def test_app_private_engine_import_exemptions() -> None:
    """NEGATIVE control: a TYPE_CHECKING import, an ``app`` private module and a public import are not flagged."""
    source = (
        "from typing import TYPE_CHECKING\n"
        "from personalscraper.app._runner_engine import reserve_run_row\n"
        "from personalscraper.core.sqlite import apply_pragmas\n"
        "if TYPE_CHECKING:\n"
        "    from personalscraper.api.transport._policy import CircuitPolicy\n"
    )
    assert _private_engine_imports(source, _APP_SYNTHETIC_REL, _engine_top_levels()) == []


def test_app_private_engine_import_in_type_checking_else_is_flagged() -> None:
    """POSITIVE control: the ``else:`` branch of ``if TYPE_CHECKING:`` runs at runtime, so it IS flagged."""
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    pass\n"
        "else:\n"
        "    from personalscraper.core.sqlite._pragmas import apply_pragmas\n"
    )
    violations = _private_engine_imports(source, _APP_SYNTHETIC_REL, _engine_top_levels())
    assert len(violations) == 1, "the TYPE_CHECKING else-branch exemption is back (vacuous guard!)"


def test_app_private_engine_module_imported_as_a_name_is_flagged() -> None:
    """POSITIVE control: an engine module imported as a ``_`` name from the package root IS flagged."""
    engine = _engine_top_levels()
    absolute = _private_engine_imports("from personalscraper import _fs_utils\n", _APP_SYNTHETIC_REL, engine)
    assert len(absolute) == 1, "guard failed to flag 'from personalscraper import _fs_utils' (vacuous guard!)"
    relative = _private_engine_imports("from . import _fs_utils\n", "personalscraper/_synthetic_probe.py", engine)
    assert len(relative) == 1, "guard failed to flag the relative form of a private engine module"
    dunder = _private_engine_imports("from personalscraper import __version__\n", _APP_SYNTHETIC_REL, engine)
    assert dunder == [], "a dunder name of the package root must not be flagged"


def test_app_private_engine_import_ignores_the_layering_marker() -> None:
    """NEGATIVE control of the exemption: ``# layering: allow`` is NOT honoured, the import is still flagged."""
    source = "from personalscraper.core.sqlite._pragmas import apply_pragmas  # layering: allow because reasons\n"
    violations = _private_engine_imports(source, _APP_SYNTHETIC_REL, _engine_top_levels())
    assert len(violations) == 1, "guard 1 honours the '# layering: allow' marker"


def _persistence_imports(source: str, rel: str) -> list[str]:
    """Return the runtime imports of ``app.store`` or of an ``app`` module named ``*repository``.

    Args:
        source: Python source code.
        rel: Repo-relative POSIX path of the file.

    Returns:
        One human-readable violation per offending import (empty if none).
    """
    violations: list[str] = []
    for line, module, names in _runtime_import_targets(source, rel):
        # ``from personalscraper.app import store`` reaches the module through a name.
        candidates = [module, *(f"{module}.{name}" for name in names)]
        for candidate in candidates:
            if (
                candidate == "personalscraper.app.store"
                or candidate.startswith("personalscraper.app.store.")
                or candidate.rsplit(".", 1)[-1].endswith("repository")
            ):
                violations.append(f"{rel}:{line}: imports the persistence module {candidate}")
                break
    return violations


def test_http_v1_does_not_import_app_persistence() -> None:
    """``http_v1/`` imports neither ``personalscraper.app.store`` nor a ``*repository`` module.

    The rule: no module under ``personalscraper/http_v1/`` imports ``personalscraper.app.store`` or a
    module whose last segment ends with ``repository``.
    """
    assert _HTTP_V1_PACKAGE_DIR.is_dir(), "personalscraper/http_v1/ is missing (the guard would scan nothing)"
    violations: list[str] = []
    for py_file in sorted(_HTTP_V1_PACKAGE_DIR.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        violations.extend(_persistence_imports(py_file.read_text(encoding="utf-8"), rel))
    assert not violations, "http_v1/ reaches the persistence (go through a service or a view):\n" + "\n".join(
        violations
    )


def test_http_v1_store_import_is_flagged() -> None:
    """POSITIVE control: a synthetic http_v1/ file importing ``app.store`` IS flagged."""
    source = "from personalscraper.app.store import AppStore\n"
    violations = _persistence_imports(source, _HTTP_V1_SYNTHETIC_REL)
    assert len(violations) == 1, "http_v1 -> app.store guard failed to flag an import (vacuous guard!)"


def test_http_v1_repository_import_is_flagged() -> None:
    """POSITIVE control: a synthetic http_v1/ file importing an ``app`` repository module IS flagged."""
    source = "from personalscraper.app.accounts.repository import StartKind\n"
    violations = _persistence_imports(source, _HTTP_V1_SYNTHETIC_REL)
    assert len(violations) == 1, "http_v1 -> repository guard failed to flag an import (vacuous guard!)"
    assert "personalscraper.app.accounts.repository" in violations[0]


def test_http_v1_repository_import_outside_app_is_flagged() -> None:
    """POSITIVE control: a ``*repository`` module outside ``app`` (the indexer's) IS flagged."""
    source = "from personalscraper.indexer.repository import X\n"
    violations = _persistence_imports(source, _HTTP_V1_SYNTHETIC_REL)
    assert len(violations) == 1, "the repository arm is still limited to personalscraper.app (vacuous guard!)"


def test_http_v1_persistence_import_exemptions() -> None:
    """NEGATIVE control: a TYPE_CHECKING import and a service import are not flagged."""
    source = (
        "from typing import TYPE_CHECKING\n"
        "from personalscraper.app.accounts.service import AccountService\n"
        "if TYPE_CHECKING:\n"
        "    from personalscraper.app.store import AppStore\n"
    )
    assert _persistence_imports(source, _HTTP_V1_SYNTHETIC_REL) == []


def _app_imports(source: str, rel: str) -> list[str]:
    """Return the runtime imports of ``personalscraper.app`` (or a module under it) in ``source``.

    Args:
        source: Python source code.
        rel: Repo-relative POSIX path of the file.

    Returns:
        One human-readable violation per offending import (empty if none).
    """
    violations: list[str] = []
    for line, module, names in _runtime_import_targets(source, rel):
        if module == "personalscraper.app" or module.startswith("personalscraper.app."):
            violations.append(f"{rel}:{line}: imports {module}")
        elif module == _PACKAGE_NAME and "app" in names:
            violations.append(f"{rel}:{line}: imports personalscraper.app")
    return violations


def test_event_catalog_does_not_import_app() -> None:
    """No ``events/`` module imports ``personalscraper.app``: the catalog sits below the application layer."""
    assert _EVENTS_PACKAGE_DIR.is_dir(), "personalscraper/events/ is missing (the guard would scan nothing)"
    violations: list[str] = []
    for py_file in sorted(_EVENTS_PACKAGE_DIR.rglob("*.py")):
        rel = py_file.relative_to(_REPO_ROOT).as_posix()
        violations.extend(_app_imports(py_file.read_text(encoding="utf-8"), rel))
    assert not violations, (
        "events/ imports the application layer (register the event in its own module):\n" + "\n".join(violations)
    )


def test_event_catalog_app_import_is_flagged() -> None:
    """POSITIVE control: a synthetic events/ file importing ``app`` IS flagged, whatever the form."""
    for source in (
        "from personalscraper.app.accounts import events\n",
        "from personalscraper.app.accounts.events import AccountRightsChanged\n",
        "import personalscraper.app.accounts.events\n",
        "from personalscraper import app\n",
    ):
        assert _app_imports(source, _EVENTS_SYNTHETIC_REL), f"events -> app guard missed {source!r} (vacuous guard!)"


def test_event_catalog_app_import_exemptions() -> None:
    """NEGATIVE control: a TYPE_CHECKING app import and an engine import are not flagged."""
    source = (
        "from typing import TYPE_CHECKING\n"
        "from personalscraper.core import ApiError\n"
        "if TYPE_CHECKING:\n"
        "    from personalscraper.app.accounts.events import AccountRightsChanged\n"
    )
    assert _app_imports(source, _EVENTS_SYNTHETIC_REL) == []
