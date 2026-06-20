# bridge — Config GUI (helm PR 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local single-operator React/shadcn web app — served as static files by the existing `kanban config serve` FastAPI app — that visually authors, validates and saves the pipeline config, with a rich prompt editor and an explicit "Sync board" action.

**Architecture:** A new repo-root `web/` Vite+React+shadcn SPA (dev/build only) builds into `src/kanbanmate/webui/`, mounted by the existing FastAPI app at `/`. The SPA talks to the 7 shipped PR-1 endpoints plus two new ones: `GET /api/placeholders` (the engine's canonical `{{placeholder}}` set) and `POST /api/board/provision` (dry-run diff + apply via `Seeder.ensure_columns`). Two new pure/app modules back the latter: `core/columns_diff.py` and `app/board_provision.py`. No Node at runtime; FastAPI/uvicorn/SPA stay behind the `[ui]` extra.

**Tech Stack:** Python 3.12, FastAPI (`[ui]` extra), pytest. Frontend: Vite, React 18, the in-repo `kanbanmate-design` system (shadcn/oklch tokens, Geist), no router lib (single-page, tab state).

## Global Constraints

- Python `>=3.12`; `mypy --strict` and `ruff` (line-length 100, target py312) must pass — `make lint` zero errors.
- `core/` imports nothing with I/O (functional core); `app/` implements/uses ports; `http/` is a top entrypoint that may import `app`/`core`/`cli.init` but NOT `daemon`/`bin` (`tests/test_layering.py`). `web/` is outside the Python import graph.
- FastAPI/uvicorn import only under the `[ui]` extra; the bare `kanban` CLI must import without them (lazy-import guard in `cli/config.py` — never import `http.config_api` at module top of any base module).
- Google-style docstrings (`Args:`/`Returns:`/`Raises:`) on every new module/class/function. Inline comments explain the _why_, in English.
- Module size: soft warning ~800 LOC, hard ceiling 1000 LOC.
- Merge = human-only. `board_provision` mutates Status **options only** — never cards, never PRs, never merges. Removals are surfaced, never applied.
- Conventional Commits, scope `bridge` (e.g. `feat(bridge): …`). No version prefixes, no AI attribution.
- Every `rg`/`grep` uses a type/glob filter. Every network command uses `--connect-timeout`/`--max-time` (use `gh api` / `git pull`, not `git fetch`).
- Live exercise NEVER touches the live kanban-mate clone (`/Users/izno/dev/KanbanMate/.claude/kanban/`) — always a copied config + a throwaway/mirrored registry root.

---

## File Structure

**New Python files:**

- `src/kanbanmate/core/columns_diff.py` — pure: `diff_columns(current, desired) -> ColumnDiff`. ADD/RENAME/REORDER/REMOVE classification.
- `src/kanbanmate/app/board_provision.py` — imperative shell: resolve registry entry → build seeder → dry-run diff or apply via `ensure_columns`.
- `tests/core/test_columns_diff.py`, `tests/app/test_board_provision.py`, additions to `tests/http/test_config_api.py` (or a new `tests/http/test_board_provision_api.py` + `tests/http/test_static_mount.py`).

**Modified Python files:**

- `src/kanbanmate/core/placeholders.py` — add `KNOWN_PLACEHOLDERS: dict[str, str]` + `unknown_placeholders(template) -> list[str]`.
- `src/kanbanmate/http/config_api.py` — add `GET /api/placeholders`, `POST /api/board/provision`, and the guarded static SPA mount.
- `pyproject.toml` — package-data `webui/**` under `[tool.setuptools.package-data]`; (CI build step in `.github/workflows/pr.yml`).
- `tests/test_layering.py` — only if a new import edge needs whitelisting (it should not).

**New frontend files (repo-root `web/`):**

- `web/package.json`, `web/vite.config.js`, `web/index.html`, `web/src/main.jsx`, `web/src/api.js`, `web/src/App.jsx`, `web/src/panels/*.jsx`, `web/src/components/RichPromptEditor.jsx`, `web/src/components/SyncBoardDialog.jsx`, plus the design-system assets copied/imported under `web/src/ds/`.
- Build output: `src/kanbanmate/webui/` (Vite `outDir`), git-ignored in source-tree but produced by CI and shipped in the wheel. (Decision §11.2 of the spec: build-in-CI-and-package; commit only as fallback.)

**Reference (read, do not modify):**

- `.claude/skills/kanbanmate-design/ui_kits/config/` — the approved layout (AppShell, ColumnsPanel, TransitionsPanel, SidePanels, data.js) and `new-pieces.html` (RichPromptEditor + SyncBoardDialog mockups). Port these into `web/src`.
- `src/kanbanmate/app/launch_context.py:86-113` — the canonical placeholder context keys.
- `src/kanbanmate/adapters/github/client.py:668` (`ensure_columns`) and `:941` (`status_options`).
- `src/kanbanmate/cli/seed.py:353-470` (registry → seeder build pattern) and `:284-318` (`status_options` optional-probe pattern).

---

## Task 1: `core/columns_diff` — pure column-set diff

**Files:**

- Create: `src/kanbanmate/core/columns_diff.py`
- Test: `tests/core/test_columns_diff.py`

**Interfaces:**

- Consumes: nothing (pure stdlib).
- Produces:
  - `@dataclass(frozen=True) ColumnChange` with fields `kind: str` (`"add"|"rename"|"reorder"|"remove"`), `column: str`, `to: str | None = None` (new name for `rename`), `from_pos: int | None = None`, `to_pos: int | None = None` (for `reorder`).
  - `@dataclass(frozen=True) ColumnDiff` with fields `changes: list[ColumnChange]`, `removals: list[ColumnChange]`, `is_noop: bool`.
  - `def diff_columns(current: list[str], desired: list[str]) -> ColumnDiff`.

> **Scope note (matches `ensure_columns` semantics, `client.py:668`):** `ensure_columns` preserves options **by id** and never drops a residual that still holds cards. Since the diff has no card-count knowledge, RENAME detection by id is not possible from names alone. Therefore `diff_columns` is a **name-set + order** diff: a name in `desired` but not `current` is ADD; a name in `current` but not `desired` is REMOVE (surfaced, never applied); a name in both whose index differs is REORDER. RENAME is **operator-asserted**, not inferred — see §6.3 below and Task 5: the API accepts an optional `renames: {old: new}` map the UI builds when the operator edits a column's name in place, and `diff_columns` consumes it to reclassify an ADD+REMOVE pair as a RENAME.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_columns_diff.py
"""Tests for the pure column-set diff backing the Sync-board preview."""

from kanbanmate.core.columns_diff import ColumnChange, diff_columns


def test_identical_sets_is_noop() -> None:
    d = diff_columns(["Backlog", "Spec", "Done"], ["Backlog", "Spec", "Done"])
    assert d.is_noop is True
    assert d.changes == []
    assert d.removals == []


def test_added_column_is_add() -> None:
    d = diff_columns(["Backlog", "Done"], ["Backlog", "Spec", "Done"])
    assert d.is_noop is False
    assert ColumnChange(kind="add", column="Spec") in d.changes
    assert d.removals == []


def test_removed_column_is_surfaced_not_in_changes() -> None:
    d = diff_columns(["Backlog", "Old", "Done"], ["Backlog", "Done"])
    assert d.removals == [ColumnChange(kind="remove", column="Old")]
    # removals never appear in the applied change list
    assert all(c.kind != "remove" for c in d.changes)


def test_reorder_detected_by_index() -> None:
    d = diff_columns(["Backlog", "Review", "Merge"], ["Backlog", "Merge", "Review"])
    kinds = {(c.kind, c.column) for c in d.changes}
    assert ("reorder", "Review") in kinds or ("reorder", "Merge") in kinds


def test_rename_map_reclassifies_add_remove() -> None:
    # "PR Ready" removed + "PR/CI" added, but the operator asserts it's a rename.
    d = diff_columns(
        ["Backlog", "PR Ready", "Done"],
        ["Backlog", "PR/CI", "Done"],
        renames={"PR Ready": "PR/CI"},
    )
    assert ColumnChange(kind="rename", column="PR Ready", to="PR/CI") in d.changes
    assert d.removals == []  # the remove was reclassified
    assert all(c.kind != "add" or c.column != "PR/CI" for c in d.changes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/core/test_columns_diff.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kanbanmate.core.columns_diff'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/kanbanmate/core/columns_diff.py
"""Pure column-set diff for the bridge "Sync board" preview (helm PR 2).

Computes the change set between the board's CURRENT Status options and the
DESIRED ``columns.yml`` order, classifying each difference as add / rename /
reorder / remove. Removals are surfaced separately and NEVER applied (a removal
would null every card still in that column — the operator removes via GitHub if
intended). RENAME is operator-asserted via the ``renames`` map (a name-only diff
cannot infer it), mirroring how the GUI edits a column name in place.

Pure functional core: stdlib only, no I/O (DESIGN §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnChange:
    """One classified difference between current and desired columns.

    Args:
        kind: One of ``"add"`` / ``"rename"`` / ``"reorder"`` / ``"remove"``.
        column: The current (or, for ``add``, the new) column name the change concerns.
        to: For ``rename``, the new name; otherwise ``None``.
        from_pos: For ``reorder``, the 0-based index in ``current``; otherwise ``None``.
        to_pos: For ``reorder``, the 0-based index in ``desired``; otherwise ``None``.
    """

    kind: str
    column: str
    to: str | None = None
    from_pos: int | None = None
    to_pos: int | None = None


@dataclass(frozen=True)
class ColumnDiff:
    """The full classified diff returned by :func:`diff_columns`.

    Args:
        changes: Applicable changes (add / rename / reorder), in a stable order.
        removals: Columns present on the board but not desired — surfaced, never applied.
        is_noop: ``True`` when ``changes`` and ``removals`` are both empty.
    """

    changes: list[ColumnChange] = field(default_factory=list)
    removals: list[ColumnChange] = field(default_factory=list)
    is_noop: bool = True


def diff_columns(
    current: list[str],
    desired: list[str],
    *,
    renames: dict[str, str] | None = None,
) -> ColumnDiff:
    """Classify the difference between current and desired column sets.

    Args:
        current: The board's current Status option names, in board order.
        desired: The desired column names, in board order (the ``columns.yml`` set).
        renames: Optional operator-asserted ``{old_name: new_name}`` map. Each entry
            reclassifies the (remove old, add new) pair as a single ``rename``.

    Returns:
        A :class:`ColumnDiff`. ``changes`` carries add/rename/reorder; ``removals``
        carries every current column absent from ``desired`` (minus any renamed away).
    """
    renames = dict(renames or {})
    renamed_from = set(renames)
    renamed_to = set(renames.values())

    changes: list[ColumnChange] = []
    # Renames first, in board order of the OLD name.
    for old in current:
        if old in renames:
            changes.append(ColumnChange(kind="rename", column=old, to=renames[old]))

    # Adds: desired names neither present in current nor produced by a rename.
    current_set = set(current)
    for name in desired:
        if name not in current_set and name not in renamed_to:
            changes.append(ColumnChange(kind="add", column=name))

    # Removals: current names neither desired nor renamed away.
    desired_set = set(desired)
    removals = [
        ColumnChange(kind="remove", column=name)
        for name in current
        if name not in desired_set and name not in renamed_from
    ]

    # Reorder: compare the post-rename projection of current against desired,
    # restricted to names common to both, by index.
    projected = [renames.get(name, name) for name in current]
    common_current = [n for n in projected if n in desired_set]
    common_desired = [n for n in desired if n in set(projected)]
    if common_current != common_desired:
        for to_pos, name in enumerate(common_desired):
            from_pos = common_current.index(name)
            if from_pos != to_pos:
                changes.append(
                    ColumnChange(kind="reorder", column=name, from_pos=from_pos, to_pos=to_pos)
                )

    is_noop = not changes and not removals
    return ColumnDiff(changes=changes, removals=removals, is_noop=is_noop)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/core/test_columns_diff.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/core/columns_diff.py tests/core/test_columns_diff.py
git commit -m "feat(bridge): pure column-set diff for sync-board preview"
```

---

## Task 2: `core/placeholders` — known set + unknown finder

**Files:**

- Modify: `src/kanbanmate/core/placeholders.py`
- Test: `tests/core/test_placeholders.py` (add to existing if present, else create)

**Interfaces:**

- Consumes: the existing `_TOKEN` regex in `placeholders.py`.
- Produces:
  - `KNOWN_PLACEHOLDERS: dict[str, str]` — `{name: one-line description}`, the canonical set the dispatch context supplies (`app/launch_context.py:86-113`).
  - `def unknown_placeholders(template: str) -> list[str]` — distinct top-level placeholder names in `template` whose first dotted segment is not in `KNOWN_PLACEHOLDERS`, in first-seen order.

> **Grounding (`app/launch_context.py:92-113`):** the context keys are `code, title, branch, ticket_body, script_output, issue_body, comments, codename, design_path, plan_paths, base_clone, dev_repo_path`. Mirror exactly. A drift-guard test (Step 1) pins this list.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_placeholders.py  (append; keep existing imports/tests)
from kanbanmate.core.placeholders import KNOWN_PLACEHOLDERS, unknown_placeholders


def test_known_placeholders_match_launch_context_keys() -> None:
    # Drift guard: the exposed set must equal the dispatch context keys.
    # Update BOTH this literal and KNOWN_PLACEHOLDERS if launch_context changes.
    expected = {
        "code", "title", "branch", "ticket_body", "script_output",
        "issue_body", "comments", "codename", "design_path", "plan_paths",
        "base_clone", "dev_repo_path",
    }
    assert set(KNOWN_PLACEHOLDERS) == expected
    assert all(isinstance(v, str) and v for v in KNOWN_PLACEHOLDERS.values())


def test_unknown_placeholders_flags_typos() -> None:
    tmpl = "Implement {{code}} ({{codename}}); base {{baze}} and {{also_bad}}."
    assert unknown_placeholders(tmpl) == ["baze", "also_bad"]


def test_unknown_placeholders_empty_when_all_known() -> None:
    assert unknown_placeholders("ticket {{code}} — {{title}}") == []


def test_unknown_placeholders_handles_dotted_paths() -> None:
    # Only the first segment is matched against the known set.
    assert unknown_placeholders("{{ticket.title}}") == ["ticket"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/core/test_placeholders.py -v -k "known or unknown"`
Expected: FAIL with `ImportError: cannot import name 'KNOWN_PLACEHOLDERS'`.

- [ ] **Step 3: Write minimal implementation** (append to `src/kanbanmate/core/placeholders.py`, after `fill`)

```python
# The canonical placeholder set the dispatch context supplies (app/launch_context.py:92-113).
# Single source of truth for bridge's rich prompt editor (GET /api/placeholders). DRIFT GUARD:
# tests/core/test_placeholders.py pins these names to the launch context — change both together.
KNOWN_PLACEHOLDERS: dict[str, str] = {
    "code": "The ticket's issue number (bare int, e.g. 9).",
    "title": "The ticket title.",
    "branch": "The per-ticket WIP / worktree branch name.",
    "ticket_body": "The issue body markdown.",
    "script_output": "The last failing check's output (CI gate / fix-CI stages).",
    "issue_body": "The first cross-referenced linked-issue body.",
    "comments": "The joined ticket comment history.",
    "codename": "The feature codename parsed from the ticket body.",
    "design_path": "Path to the feature DESIGN.md (set after design).",
    "plan_paths": "Path(s) to the implementation plan file(s).",
    "base_clone": "The base clone path (reserved; empty unless set).",
    "dev_repo_path": "The operator's dev-clone path (reserved; empty unless set).",
}


def unknown_placeholders(template: str) -> list[str]:
    """Return the distinct unknown placeholder names referenced by *template*.

    A placeholder is "unknown" when the FIRST dotted segment of its key is not in
    :data:`KNOWN_PLACEHOLDERS`. Names are returned in first-seen order (deduplicated),
    backing the editor's "N unknown placeholders" finding.

    Args:
        template: A prompt template containing zero or more ``{{key}}`` tokens.

    Returns:
        The unknown top-level placeholder names, in first-seen order.
    """
    seen: list[str] = []
    for match in _TOKEN.finditer(template):
        head = match.group(1).split(".", 1)[0]
        if head not in KNOWN_PLACEHOLDERS and head not in seen:
            seen.append(head)
    return seen
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/core/test_placeholders.py -v`
Expected: PASS (existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/core/placeholders.py tests/core/test_placeholders.py
git commit -m "feat(bridge): expose canonical placeholder set + unknown-placeholder finder"
```

---

## Task 3: `app/board_provision` — dry-run diff + apply

**Files:**

- Create: `src/kanbanmate/app/board_provision.py`
- Test: `tests/app/test_board_provision.py`

**Interfaces:**

- Consumes: `core.columns_diff.diff_columns` / `ColumnDiff`; the `Seeder` port (`ensure_columns`, optional `status_options`); the registry (`cli.init._load_registry`, `_projects_path`, `ProjectEntry`); `adapters.github.client.GithubClient` + `adapters.github.token.load_token` (production seeder build, mirrors `cli/seed.py:413`).
- Produces:
  - `@dataclass(frozen=True) ProvisionResult` with `applied: bool`, `diff: ColumnDiff`, `option_map: dict[str, str]` (empty on dry-run).
  - `def provision_board(root: Path, *, desired_columns: list[str], renames: dict[str, str] | None = None, dry_run: bool, seeder: Seeder | None = None) -> ProvisionResult`.

> **Grounding:** resolve the FIRST registry entry exactly as `http/config_api.py:_get_service` does (PR-1 single-project assumption). Build the production seeder as `cli/seed.py:413` does. Read current options via the optional `status_options(project_id)` probe (`cli/seed.py:313` pattern); when absent, fall back to `entry.option_map`.

- [ ] **Step 1: Write the failing test**

```python
# tests/app/test_board_provision.py
"""Tests for the bridge board-provision shell (dry-run diff + apply)."""

import json
from pathlib import Path

import pytest

from kanbanmate.app.board_provision import ProvisionResult, provision_board


class _FakeSeeder:
    """A Seeder exposing status_options + ensure_columns, recording calls."""

    def __init__(self, options: dict[str, str]) -> None:
        self._options = dict(options)
        self.ensure_calls: list[list[str]] = []

    def status_options(self, project_id: str) -> dict[str, str]:
        return dict(self._options)

    def ensure_columns(self, project_id: str, columns: list[str]) -> dict[str, str]:
        self.ensure_calls.append(list(columns))
        # Simulate GitHub returning the requested columns mapped to ids.
        return {c: self._options.get(c, f"OPT_{c}") for c in columns}


def _registry_root(tmp_path: Path) -> Path:
    """Write a minimal projects.json with one entry and return the root."""
    root = tmp_path / "root"
    (root).mkdir()
    projects = {
        "PVT_x": {
            "repo": "Org/repo",
            "clone": str(tmp_path / "clone"),
            "project_id": "PVT_x",
            "status_field_node_id": "FLD",
        }
    }
    (root / "projects.json").write_text(json.dumps(projects), encoding="utf-8")
    return root


def test_dry_run_computes_diff_without_mutating(tmp_path: Path) -> None:
    root = _registry_root(tmp_path)
    seeder = _FakeSeeder({"Backlog": "o1", "Done": "o2"})
    result = provision_board(
        root, desired_columns=["Backlog", "Spec", "Done"], dry_run=True, seeder=seeder
    )
    assert isinstance(result, ProvisionResult)
    assert result.applied is False
    assert any(c.kind == "add" and c.column == "Spec" for c in result.diff.changes)
    assert seeder.ensure_calls == []  # NO mutation on dry-run
    assert result.option_map == {}


def test_apply_calls_ensure_columns_in_desired_order(tmp_path: Path) -> None:
    root = _registry_root(tmp_path)
    seeder = _FakeSeeder({"Backlog": "o1", "Done": "o2"})
    result = provision_board(
        root, desired_columns=["Backlog", "Spec", "Done"], dry_run=False, seeder=seeder
    )
    assert result.applied is True
    assert seeder.ensure_calls == [["Backlog", "Spec", "Done"]]
    assert result.option_map == {"Backlog": "o1", "Spec": "OPT_Spec", "Done": "o2"}


def test_no_registry_entry_raises(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    (root / "projects.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="No project registered"):
        provision_board(root, desired_columns=["Backlog"], dry_run=True, seeder=_FakeSeeder({}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/app/test_board_provision.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kanbanmate.app.board_provision'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/kanbanmate/app/board_provision.py
"""Board provisioning shell for bridge's "Sync board" action (helm PR 2).

Resolves the runtime registry's project entry, reads the board's current Status
options, diffs them against the desired ``columns.yml`` set, and — on apply —
re-provisions the options via the shipped :meth:`Seeder.ensure_columns` (which
preserves option ids so cards are never orphaned). This is the ONLY board-mutating
path bridge adds; it writes Status options only — never cards, never PRs, never
merges (CLAUDE.md autonomy floor).

Layering: ``app`` is the imperative shell — it may import ``core`` and the ports,
and (like ``http``) the registry helpers via ``cli.init``. ``core`` stays pure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kanbanmate.cli.init import ProjectEntry, _load_registry, _projects_path
from kanbanmate.core.columns_diff import ColumnDiff, diff_columns
from kanbanmate.ports.board import Seeder


@dataclass(frozen=True)
class ProvisionResult:
    """Outcome of a :func:`provision_board` call.

    Args:
        applied: ``True`` when the board was mutated (apply); ``False`` for a dry-run.
        diff: The classified column diff (always populated).
        option_map: The ``{column: option_id}`` map after apply; empty on dry-run.
    """

    applied: bool
    diff: ColumnDiff
    option_map: dict[str, str] = field(default_factory=dict)


def _first_entry(root: Path) -> ProjectEntry:
    """Return the registry's first (PR-1 single) project entry.

    Args:
        root: The kanban runtime root holding ``projects.json``.

    Returns:
        The first :class:`~kanbanmate.cli.init.ProjectEntry`.

    Raises:
        ValueError: When no project is registered under ``root``.
    """
    registry = _load_registry(_projects_path(root))
    if not registry:
        raise ValueError("No project registered in the kanban root")
    return next(iter(registry.values()))


def _build_seeder(entry: ProjectEntry) -> Seeder:
    """Build the production GitHub seeder for ``entry`` (mirrors cli/seed.py:413).

    Args:
        entry: The resolved registry entry.

    Returns:
        A :class:`~kanbanmate.adapters.github.client.GithubClient` bound to the project.
    """
    # Imported lazily so this module stays importable without a live token in tests
    # that inject a fake seeder.
    from kanbanmate.adapters.github.client import GithubClient  # noqa: PLC0415
    from kanbanmate.adapters.github.token import load_token  # noqa: PLC0415

    return GithubClient(load_token(), project_id=entry.project_id)


def _current_options(seeder: Seeder, project_id: str, entry: ProjectEntry) -> list[str]:
    """Read the board's current Status option names, in board order.

    Uses the optional ``status_options`` probe (cli/seed.py:313 pattern); falls back
    to the registry entry's recorded ``option_map`` keys when the seeder lacks it.

    Args:
        seeder: The Seeder driving provisioning.
        project_id: The Project v2 node id.
        entry: The resolved registry entry (for the fallback option map).

    Returns:
        The current option names, board order (empty list when neither source knows).
    """
    probe = getattr(seeder, "status_options", None)
    if callable(probe):
        return list(probe(project_id).keys())
    return list(entry.option_map.keys())


def provision_board(
    root: Path,
    *,
    desired_columns: list[str],
    renames: dict[str, str] | None = None,
    dry_run: bool,
    seeder: Seeder | None = None,
) -> ProvisionResult:
    """Diff (and optionally apply) the board's Status options against the desired columns.

    Args:
        root: The kanban runtime root (resolves the registry's project entry).
        desired_columns: The desired column names, board order (the ``columns.yml`` set).
        renames: Optional operator-asserted ``{old: new}`` map (see :func:`diff_columns`).
        dry_run: When ``True``, compute + return the diff WITHOUT mutating the board.
        seeder: Injected Seeder (tests). Defaults to the production GitHub client.

    Returns:
        A :class:`ProvisionResult`.

    Raises:
        ValueError: When no project is registered under ``root``.
    """
    entry = _first_entry(root)
    active = seeder if seeder is not None else _build_seeder(entry)
    current = _current_options(active, entry.project_id, entry)
    diff = diff_columns(current, desired_columns, renames=renames)

    if dry_run:
        return ProvisionResult(applied=False, diff=diff)

    option_map = active.ensure_columns(entry.project_id, desired_columns)
    return ProvisionResult(applied=True, diff=diff, option_map=option_map)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/app/test_board_provision.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/app/board_provision.py tests/app/test_board_provision.py
git commit -m "feat(bridge): board-provision shell (dry-run diff + apply via ensure_columns)"
```

---

## Task 4: `GET /api/placeholders` endpoint

**Files:**

- Modify: `src/kanbanmate/http/config_api.py`
- Test: `tests/http/test_config_api.py` (append)

**Interfaces:**

- Consumes: `core.placeholders.KNOWN_PLACEHOLDERS`.
- Produces: `GET /api/placeholders` → `{"placeholders": [{"name": str, "description": str}, ...]}` (sorted by name for stable output).

- [ ] **Step 1: Write the failing test**

```python
# tests/http/test_config_api.py  (append; reuse the module's existing TestClient fixture)
def test_get_placeholders_returns_known_set(client) -> None:
    resp = client.get("/api/placeholders")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()["placeholders"]}
    assert {"code", "codename", "script_output"} <= names
    assert all(p["description"] for p in resp.json()["placeholders"])
```

> If `tests/http/test_config_api.py` has no shared `client` fixture, add one mirroring the existing tests' `TestClient(app)` construction (read the top of that file first).

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/http/test_config_api.py -v -k placeholders`
Expected: FAIL with 404 (route not defined).

- [ ] **Step 3: Write minimal implementation** (add near `get_schema`, after the `GET /api/schema` route in `config_api.py`)

```python
@app.get("/api/placeholders")
def get_placeholders() -> JSONResponse:
    """Return the engine's canonical prompt-placeholder set.

    The rich prompt editor (bridge PR 2) highlights + validates ``{{placeholder}}``
    tokens against this set, sourced from the single engine definition
    (:data:`kanbanmate.core.placeholders.KNOWN_PLACEHOLDERS`) so the UI can never
    drift from the dispatch context.

    Returns:
        ``{"placeholders": [{"name", "description"}, ...]}`` sorted by name.
    """
    from kanbanmate.core.placeholders import KNOWN_PLACEHOLDERS  # noqa: PLC0415

    items = [{"name": k, "description": v} for k, v in sorted(KNOWN_PLACEHOLDERS.items())]
    return JSONResponse(content={"placeholders": items})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/http/test_config_api.py -v -k placeholders`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/http/config_api.py tests/http/test_config_api.py
git commit -m "feat(bridge): GET /api/placeholders exposes the canonical placeholder set"
```

---

## Task 5: `POST /api/board/provision` endpoint

**Files:**

- Modify: `src/kanbanmate/http/config_api.py`
- Test: `tests/http/test_board_provision_api.py` (create)

**Interfaces:**

- Consumes: `app.board_provision.provision_board` / `ProvisionResult`; the bounded `_read_json_object` helper; `app.state.kanban_root`.
- Produces: `POST /api/board/provision` with body `{"dry_run": bool, "renames": {old: new}?}` →
  `{"applied": bool, "is_noop": bool, "changes": [{"kind","column","to","from_pos","to_pos"}], "removals": [...], "option_map": {...}}`.
- The endpoint derives `desired_columns` from the **saved** config (loads via `_get_service().load()`), NOT from a posted draft (spec §8: Sync operates on saved config; the dialog is disabled while dirty). Inject the seeder via `app.state.seeder` when present (tests), else `provision_board` builds the production one.

- [ ] **Step 1: Write the failing test**

```python
# tests/http/test_board_provision_api.py
"""HTTP tests for POST /api/board/provision (bridge sync-board)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from kanbanmate.http.config_api import app


class _FakeSeeder:
    def __init__(self, options):
        self._options = dict(options)
        self.ensure_calls = []

    def status_options(self, project_id):
        return dict(self._options)

    def ensure_columns(self, project_id, columns):
        self.ensure_calls.append(list(columns))
        return {c: self._options.get(c, f"OPT_{c}") for c in columns}


def _setup(tmp_path: Path) -> Path:
    """Write a registry + a clone config whose columns are Backlog/Spec/Done."""
    root = tmp_path / "root"
    clone = tmp_path / "clone" / ".claude" / "kanban"
    clone.mkdir(parents=True)
    root.mkdir()
    (clone / "columns.yml").write_text(
        "columns:\n  - {key: Backlog, name: Backlog, class: inert}\n"
        "  - {key: Spec, name: Spec, class: inert}\n"
        "  - {key: Done, name: Done, class: inert}\n",
        encoding="utf-8",
    )
    (clone / "transitions.yml").write_text("transitions: []\n", encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps({"PVT_x": {"repo": "Org/repo", "clone": str(tmp_path / "clone"),
                              "project_id": "PVT_x", "status_field_node_id": "FLD"}}),
        encoding="utf-8",
    )
    return root


def test_provision_dry_run(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    seeder = _FakeSeeder({"Backlog": "o1", "Done": "o2"})
    app.state.kanban_root = root
    app.state.seeder = seeder
    with TestClient(app) as client:
        resp = client.post("/api/board/provision", json={"dry_run": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False
    assert any(c["kind"] == "add" and c["column"] == "Spec" for c in body["changes"])
    assert seeder.ensure_calls == []


def test_provision_apply(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    seeder = _FakeSeeder({"Backlog": "o1", "Done": "o2"})
    app.state.kanban_root = root
    app.state.seeder = seeder
    with TestClient(app) as client:
        resp = client.post("/api/board/provision", json={"dry_run": False})
    assert resp.status_code == 200
    assert resp.json()["applied"] is True
    assert seeder.ensure_calls == [["Backlog", "Spec", "Done"]]
```

> The `columns.yml` shape above must match what `core/columns.load_columns` accepts — read `assets/columns.yml.tmpl` and `core/columns.py:48-96` first and copy the exact accepted YAML form into the fixture.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/http/test_board_provision_api.py -v`
Expected: FAIL with 404.

- [ ] **Step 3: Write minimal implementation** (add to `config_api.py`)

```python
@app.post("/api/board/provision")
async def provision(request: fastapi.Request) -> JSONResponse:
    """Diff (and optionally apply) the GitHub Status options against the saved columns.

    Body: ``{"dry_run": bool, "renames": {old: new}?}``. The desired column set is
    read from the SAVED config (not a posted draft) — bridge disables Sync while the
    editor is dirty (DESIGN §8). On apply, re-provisions via
    :func:`kanbanmate.app.board_provision.provision_board` (Status options only;
    never cards/PRs/merges).

    Returns:
        ``{"applied", "is_noop", "changes", "removals", "option_map"}``.

    Raises:
        HTTPException: 411/413/422 (bad body); 503 (no registered project).
    """
    from dataclasses import asdict  # noqa: PLC0415 — already imported at top; safe local alias
    from kanbanmate.app.board_provision import provision_board  # noqa: PLC0415

    body = await _read_json_object(request)
    dry_run = bool(body.get("dry_run", True))
    renames = body.get("renames") or {}
    if not isinstance(renames, dict):
        raise HTTPException(status_code=422, detail="'renames' must be an object")

    service = _get_service()  # 503 if no project registered
    draft = service.load()
    desired = [c.name for c in draft.definition.columns]

    kanban_root = getattr(app.state, "kanban_root", None) or _DEFAULT_ROOT
    injected = getattr(app.state, "seeder", None)
    try:
        result = provision_board(
            kanban_root,
            desired_columns=desired,
            renames={str(k): str(v) for k, v in renames.items()},
            dry_run=dry_run,
            seeder=injected,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return JSONResponse(
        content={
            "applied": result.applied,
            "is_noop": result.diff.is_noop,
            "changes": [asdict(c) for c in result.diff.changes],
            "removals": [asdict(c) for c in result.diff.removals],
            "option_map": result.option_map,
        }
    )
```

> Remove the local `asdict` import if the module-level `from dataclasses import asdict` (config_api.py:23) is in scope — it is; drop the local line to avoid a redefinition lint. Use the top-level import.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/http/test_board_provision_api.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/kanbanmate/http/config_api.py tests/http/test_board_provision_api.py
git commit -m "feat(bridge): POST /api/board/provision (sync-board diff + apply)"
```

---

## Task 6: Guarded static SPA mount

**Files:**

- Modify: `src/kanbanmate/http/config_api.py`
- Test: `tests/http/test_static_mount.py` (create)

**Interfaces:**

- Consumes: `fastapi.staticfiles.StaticFiles`; the built SPA dir `Path(__file__).parent.parent / "webui"`.
- Produces: `GET /` serves the SPA `index.html` when built; a friendly JSON message (200) when `webui/` is absent. `/api/*` always works. Mounting is LAST so it never shadows `/api/*`.

- [ ] **Step 1: Write the failing test**

```python
# tests/http/test_static_mount.py
"""The static SPA mount degrades gracefully when no build is present."""

from fastapi.testclient import TestClient

from kanbanmate.http.config_api import app


def test_root_without_build_is_friendly_not_500() -> None:
    # In a source checkout with no `webui/` build, `/` must not 500.
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "build" in resp.text.lower() or "npm" in resp.text.lower()


def test_api_health_still_works_with_mount() -> None:
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/http/test_static_mount.py -v`
Expected: FAIL — `GET /` currently 404s (no route), so `test_root_without_build_is_friendly_not_500` fails.

- [ ] **Step 3: Write minimal implementation** (add at the END of `config_api.py`, after all `/api/*` routes)

```python
# --- Static SPA mount (bridge PR 2) -------------------------------------------------
# The built React/shadcn SPA lives in the package at ``webui/`` (Vite outDir, shipped
# under the [ui] extra). Mounted LAST so it never shadows the /api/* routes. When the
# build is absent (a source checkout without `npm run build`), `/` returns a friendly
# hint instead of a 500, and the API keeps working (DESIGN §7/§9).
_WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"

if (_WEBUI_DIR / "index.html").is_file():
    from fastapi.staticfiles import StaticFiles  # noqa: PLC0415

    # html=True → serve index.html at `/` and fall back to it for client-side routes.
    app.mount("/", StaticFiles(directory=str(_WEBUI_DIR), html=True), name="webui")
else:

    @app.get("/")
    def _no_build() -> JSONResponse:
        """Friendly placeholder when the SPA build is absent (DESIGN §9)."""
        return JSONResponse(
            content={
                "message": (
                    "Config UI not built. Run `npm --prefix web run build` (or install "
                    "the [ui] extra from a release wheel). The /api/* endpoints work regardless."
                )
            }
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/http/test_static_mount.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full backend gate + commit**

Run: `make lint && PYTHONPATH=src python -m pytest tests/core/test_columns_diff.py tests/core/test_placeholders.py tests/app/test_board_provision.py tests/http -v`
Expected: all PASS, zero lint errors.

```bash
git add src/kanbanmate/http/config_api.py tests/http/test_static_mount.py
git commit -m "feat(bridge): guarded static SPA mount on the config API"
```

---

## Task 7: Frontend scaffold — Vite + React + design system + API client

**Files:**

- Create: `web/package.json`, `web/vite.config.js`, `web/index.html`, `web/src/main.jsx`, `web/src/api.js`, `web/.gitignore`
- Copy: design-system assets from `.claude/skills/kanbanmate-design/` into `web/src/ds/` (the `_ds_bundle.js`, `styles.css`, `tokens/`).

**Interfaces:**

- Produces: `web/src/api.js` exporting `getConfig()`, `validate(draft)`, `saveConfig(draft)`, `renderConfig()`, `getPlaceholders()`, `provisionBoard({dryRun, renames})`, each a `fetch` wrapper returning parsed JSON and throwing on non-2xx.
- Vite `build.outDir` = `../src/kanbanmate/webui` (emptyOutDir true) so `npm run build` populates the packaged dir.

- [ ] **Step 1: Scaffold config files**

```json
// web/package.json
{
  "name": "kanbanmate-bridge",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.0"
  }
}
```

```js
// web/vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build into the Python package so the wheel ships the SPA (DESIGN §7).
// Dev server proxies /api to the running `kanban config serve` (default :8766).
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../src/kanbanmate/webui", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8766" } },
});
```

```
// web/.gitignore
node_modules/
```

```html
<!-- web/index.html -->
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>KanbanMate — Configuration</title>
    <link rel="stylesheet" href="./src/ds/styles.css" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Write the API client**

```js
// web/src/api.js
// Thin fetch wrappers over the kanban config API (helm PR 1 + bridge PR 2).
// Every call throws an Error on a non-2xx response so callers surface it in a Banner.

async function call(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = data && data.detail ? data.detail : resp.statusText;
    throw new Error(`${resp.status}: ${detail}`);
  }
  return data;
}

export const getConfig = () => call("GET", "/api/config");
export const validate = (draft) => call("POST", "/api/config/validate", draft);
export const saveConfig = (draft) => call("POST", "/api/config", draft);
export const renderConfig = () => call("GET", "/api/config/render");
export const getPlaceholders = () => call("GET", "/api/placeholders");
export const provisionBoard = ({ dryRun, renames }) =>
  call("POST", "/api/board/provision", {
    dry_run: dryRun,
    renames: renames || {},
  });
```

- [ ] **Step 3: Copy design-system assets + write the entry point**

```bash
mkdir -p web/src/ds
cp .claude/skills/kanbanmate-design/styles.css web/src/ds/styles.css
cp -r .claude/skills/kanbanmate-design/tokens web/src/ds/tokens
cp .claude/skills/kanbanmate-design/_ds_bundle.js web/src/ds/_ds_bundle.js
```

> Read `web/src/ds/styles.css` after copying — its `@import` paths must resolve relative to `web/src/ds/`. Fix any path that pointed at the skill layout.

```jsx
// web/src/main.jsx
import React from "react";
import { createRoot } from "react-dom/client";
import "./ds/_ds_bundle.js"; // exposes window.KanbanMateDesignSystem_2463ad
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(<App />);
```

> If `_ds_bundle.js` is an IIFE that only attaches to `window` (it is — `window.KanbanMateDesignSystem_2463ad`), importing it for side effects is correct. If Vite complains it has no default export, keep the bare `import "./ds/_ds_bundle.js";` form (side-effect import) as written.

- [ ] **Step 4: Verify it builds (App.jsx stub for now)**

```jsx
// web/src/App.jsx  (temporary stub — replaced in Task 8)
export default function App() {
  return <div style={{ padding: 24 }}>bridge — loading…</div>;
}
```

Run: `cd web && npm install && npm run build`
Expected: build succeeds; `src/kanbanmate/webui/index.html` exists.

Re-run the static-mount test to confirm the built dir is now served:
Run: `PYTHONPATH=src python -m pytest tests/http/test_static_mount.py::test_api_health_still_works_with_mount -v`
Expected: PASS (mount active; `/api/health` still works).

- [ ] **Step 5: Commit**

```bash
git add web/ src/kanbanmate/webui/.gitkeep 2>/dev/null; git add web/
git commit -m "feat(bridge): vite+react scaffold, api client, design-system assets"
```

> Do NOT commit `src/kanbanmate/webui/` build output here (CI builds it — Task 11). Ensure `src/kanbanmate/webui/` is git-ignored except a `.gitkeep`; add the ignore rule in this commit.

---

## Task 8: Live config editor — AppShell + panels wired to the API

**Files:**

- Create: `web/src/App.jsx` (replace stub), `web/src/panels/ColumnsPanel.jsx`, `web/src/panels/TransitionsPanel.jsx`, `web/src/panels/SidePanels.jsx` (Defaults/Validation/Yaml), `web/src/components/AppShell.jsx`.

**Interfaces:**

- Consumes: `api.getConfig/validate/saveConfig/renderConfig`; the DS components on `window.KanbanMateDesignSystem_2463ad`.
- Produces: a working editor whose single source of truth is one `draft` state (`{definition:{columns,transitions,defaults}, binding}`), with `dirty`, `findings`, and a Save gated on zero error-severity findings.

> Port the approved layout verbatim from `.claude/skills/kanbanmate-design/ui_kits/config/` (AppShell.jsx, ColumnsPanel.jsx, TransitionsPanel.jsx, SidePanels.jsx, index.html's `App`). The ONLY substantive change: replace the static `window.KMConfigData` with live API data and wire mutation + validate + save. Read each kit file and adapt it.

- [ ] **Step 1: Port `App.jsx` with live data + save/validate wiring**

```jsx
// web/src/App.jsx
import React from "react";
import * as api from "./api.js";
import AppShell from "./components/AppShell.jsx";
import ColumnsPanel from "./panels/ColumnsPanel.jsx";
import TransitionsPanel from "./panels/TransitionsPanel.jsx";
import {
  DefaultsPanel,
  ValidationPanel,
  YamlPanel,
} from "./panels/SidePanels.jsx";

const { Banner } = window.KanbanMateDesignSystem_2463ad;

export default function App() {
  const [draft, setDraft] = React.useState(null);
  const [findings, setFindings] = React.useState([]);
  const [dirty, setDirty] = React.useState(false);
  const [active, setActive] = React.useState("transitions");
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    api
      .getConfig()
      .then(setDraft)
      .catch((e) => setError(e.message));
  }, []);

  const errorCount = findings.filter((f) => f.severity === "error").length;

  // Mutate the draft locally; mark dirty. Panels call this with a producer fn.
  const update = (mut) => {
    setDraft((d) => mut(structuredClone(d)));
    setDirty(true);
  };

  const onValidate = async () => {
    try {
      const res = await api.validate(draft);
      setFindings(res.findings || []);
    } catch (e) {
      setError(e.message);
    }
  };

  const onSave = async () => {
    try {
      await api.saveConfig(draft); // server re-validates; 4xx → throw
      setDirty(false);
      const res = await api.validate(draft);
      setFindings(res.findings || []);
    } catch (e) {
      // Server rejected (error findings) — surface them and keep dirty.
      setError(e.message);
      try {
        const res = await api.validate(draft);
        setFindings(res.findings || []);
      } catch (_) {
        /* validate also failed — error banner already set */
      }
    }
  };

  const onGoto = (field) => {
    if (field.startsWith("transitions")) setActive("transitions");
    else if (field.startsWith("defaults")) setActive("defaults");
    else if (field.startsWith("columns")) setActive("columns");
  };

  if (error && !draft) {
    return (
      <div style={{ padding: 24 }}>
        <Banner tone="error" title="Cannot reach the config API">
          {error}. Start it with <code>kanban config serve</code>.
        </Banner>
      </div>
    );
  }
  if (!draft) return <div style={{ padding: 24 }}>Loading…</div>;

  const panels = {
    columns: <ColumnsPanel draft={draft} update={update} dirty={dirty} />,
    transitions: (
      <TransitionsPanel draft={draft} update={update} findings={findings} />
    ),
    defaults: <DefaultsPanel draft={draft} update={update} />,
    validation: <ValidationPanel findings={findings} onGoto={onGoto} />,
    yaml: <YamlPanel />,
  };

  return (
    <AppShell
      active={active}
      onNav={setActive}
      errorCount={errorCount}
      dirty={dirty}
      onSave={onSave}
      onValidate={onValidate}
    >
      {error && (
        <Banner tone="error" title="Action failed">
          {error}
        </Banner>
      )}
      {panels[active]}
    </AppShell>
  );
}
```

- [ ] **Step 2: Port AppShell + the four panels from the kit**

Adapt `.claude/skills/kanbanmate-design/ui_kits/config/AppShell.jsx`, `ColumnsPanel.jsx`, `TransitionsPanel.jsx`, `SidePanels.jsx` into `web/src/components` / `web/src/panels`. Convert each from the kit's global-attach form (`Object.assign(window, {…})`, `window.ColumnsPanel`) to ES-module `export default` / named exports, and:

- `AppShell`: accept an `onValidate` prop and render a "Validate" button beside "Save" (the kit header has Save + dirty + errorCount; add Validate).
- `ColumnsPanel`: read `draft.definition.columns`; wire add/rename/reorder/mark-inert to `update(d => …)`; render the **Sync board** button (its dialog comes in Task 10) — disabled when `dirty`, with title "Save before syncing".
- `TransitionsPanel`: read `draft.definition.transitions`; keep the Dialog editor; the prompt field becomes `<RichPromptEditor>` (Task 9) — for THIS task keep the kit's `<Textarea>` and swap it in Task 9.
- `DefaultsPanel`: bind `concurrency_cap` / `move_rate_limit_per_hour` to `draft.definition.defaults` via `update`.
- `ValidationPanel`: render `findings` with severity + `field` locus + click-to-`onGoto`.
- `YamlPanel`: `React.useEffect(() => api.renderConfig().then(setText))`; render read-only `transitions` + `columns` text.

> Each panel file: read the kit original, then write the module form. This is mechanical porting — no new design. Keep all DS component usage identical.

- [ ] **Step 3: Build + manual smoke**

Run: `cd web && npm run build`
Expected: build succeeds.

Manual smoke (isolated, never the live clone):

```bash
# Copy a config + registry into a throwaway root, then serve it.
TMP=$(mktemp -d)
cp -r /Users/izno/dev/KanbanMate/.claude/kanban "$TMP/clone-config"   # READ source; serve a COPY
# Build a one-entry projects.json pointing clone -> the copy (edit by hand or a small python -c).
PYTHONPATH=src python -m kanbanmate.cli.app config serve --root "$TMP/root" --port 8799 &
# Open http://127.0.0.1:8799/ : the editor loads the config, edits mark dirty, Validate shows findings.
```

Expected: editor loads, panels switch, edit → dirty, Validate populates findings, Save clears dirty.

- [ ] **Step 4: Commit**

```bash
git add web/src
git commit -m "feat(bridge): live config editor (shell + columns/transitions/defaults/validation/yaml panels)"
```

---

## Task 9: Rich prompt editor component

**Files:**

- Create: `web/src/components/RichPromptEditor.jsx`
- Modify: `web/src/panels/TransitionsPanel.jsx` (use it in the Dialog)

**Interfaces:**

- Consumes: `api.getPlaceholders()`; DS `KeyChip`, `Banner`.
- Produces: `<RichPromptEditor value onChange />` — known-placeholder chips (click to insert), `{{ }}` highlight (`.ph` known / `.ph.bad` unknown), an unknown-placeholder Banner with a did-you-mean, a sample-filled preview line.

> Mirror `.claude/skills/kanbanmate-design/ui_kits/config/new-pieces.html` `RichPromptEditor`. The mock used a static styled `<div>`; here it is a controlled editor. Use a `<textarea>` for editing layered under a highlighted overlay (caret-stable), OR — simpler and acceptable — a `<textarea>` plus a separate live-highlighted read-only preview block below it. Pick the textarea+preview form to avoid contentEditable caret bugs (spec §11.4 leaned this way for cost).

- [ ] **Step 1: Implement the component**

```jsx
// web/src/components/RichPromptEditor.jsx
import React from "react";
import * as api from "../api.js";

const { KeyChip, Banner } = window.KanbanMateDesignSystem_2463ad;
const TOKEN = /\{\{\s*([\w.]+)\s*\}\}/g;

// Levenshtein for did-you-mean (small strings; trivial cost).
function near(name, known) {
  const dist = (a, b) => {
    const m = [...Array(a.length + 1)].map((_, i) => [
      i,
      ...Array(b.length).fill(0),
    ]);
    for (let j = 0; j <= b.length; j++) m[0][j] = j;
    for (let i = 1; i <= a.length; i++)
      for (let j = 1; j <= b.length; j++)
        m[i][j] = Math.min(
          m[i - 1][j] + 1,
          m[i][j - 1] + 1,
          m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
        );
    return m[a.length][b.length];
  };
  let best = null,
    bd = 99;
  for (const k of known) {
    const d = dist(name, k);
    if (d < bd) {
      bd = d;
      best = k;
    }
  }
  return bd <= 3 ? best : null;
}

export default function RichPromptEditor({ value, onChange }) {
  const [known, setKnown] = React.useState({}); // {name: description}
  React.useEffect(() => {
    api.getPlaceholders().then((r) => {
      const map = {};
      r.placeholders.forEach((p) => (map[p.name] = p.description));
      setKnown(map);
    });
  }, []);

  const text = value || "";
  const knownNames = Object.keys(known);
  const unknowns = [];
  let m;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(text))) {
    const head = m[1].split(".")[0];
    if (knownNames.length && !known[head] && !unknowns.includes(head))
      unknowns.push(head);
  }

  // Build the highlighted preview (escape, then wrap tokens).
  const esc = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const html = esc(text).replace(TOKEN, (full, key) => {
    const head = key.split(".")[0];
    const bad = knownNames.length && !known[head];
    return `<span class="ph${bad ? " bad" : ""}">${esc(full)}</span>`;
  });

  const insert = (chip) => onChange(text + chip);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {knownNames.map((n) => (
          <span
            key={n}
            title={known[n]}
            onClick={() => insert(`{{${n}}}`)}
            style={{ cursor: "pointer" }}
          >
            <KeyChip>{`{{${n}}}`}</KeyChip>
          </span>
        ))}
      </div>
      <textarea
        value={text}
        onChange={(e) => onChange(e.target.value)}
        rows={6}
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12.5,
          lineHeight: 1.6,
          padding: 12,
          background: "var(--background)",
          border: "1px solid var(--input)",
          borderRadius: "var(--radius-md)",
          color: "var(--foreground)",
        }}
      />
      <div
        className="editor"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12.5,
          lineHeight: 1.6,
          padding: 12,
          background: "var(--muted)",
          borderRadius: "var(--radius-md)",
          whiteSpace: "pre-wrap",
        }}
        dangerouslySetInnerHTML={{
          __html: html || "<span style='opacity:.5'>preview</span>",
        }}
      />
      {unknowns.length > 0 && (
        <Banner
          tone="error"
          title={`${unknowns.length} unknown placeholder${unknowns.length > 1 ? "s" : ""}`}
        >
          {unknowns.map((u) => {
            const dym = near(u, knownNames);
            return (
              <div key={u}>
                <code>{`{{${u}}}`}</code>
                {dym
                  ? ` — did you mean {{${dym}}}?`
                  : " is not a known placeholder."}
              </div>
            );
          })}
        </Banner>
      )}
    </div>
  );
}
```

> The `.ph` / `.ph.bad` CSS classes already exist in the design system's editor styling (used in `new-pieces.html`). If they live only in that demo's inline `<style>` and not in `tokens/`, add the two rules to `web/src/ds/styles.css` (copy them verbatim from `new-pieces.html:20-21`). Verify after copying.

- [ ] **Step 2: Wire it into the transition Dialog**

In `web/src/panels/TransitionsPanel.jsx`, replace the prompt `<Textarea>` with:

```jsx
<RichPromptEditor
  value={edit.prompt || ""}
  onChange={(v) =>
    update((d) => {
      d.definition.transitions[editIdx].prompt = v;
      return d;
    })
  }
/>
```

(import `RichPromptEditor` at the top).

- [ ] **Step 3: Build + manual verify**

Run: `cd web && npm run build`
Expected: build succeeds. In the served UI, open a transition's prompt → chips appear, `{{code}}` highlights green, typing `{{baze}}` underlines red + Banner shows "did you mean {{base}}?".

- [ ] **Step 4: Commit**

```bash
git add web/src/components/RichPromptEditor.jsx web/src/panels/TransitionsPanel.jsx web/src/ds/styles.css
git commit -m "feat(bridge): rich prompt editor with placeholder highlight + validation"
```

---

## Task 10: Sync board dialog component

**Files:**

- Create: `web/src/components/SyncBoardDialog.jsx`
- Modify: `web/src/panels/ColumnsPanel.jsx` (open it from the Sync button)

**Interfaces:**

- Consumes: `api.provisionBoard({dryRun, renames})`; DS `Dialog`, `Banner`, `Button`, `KeyChip`.
- Produces: `<SyncBoardDialog open onClose />` — on open, fetch the dry-run diff; render ADD/RENAME/REORDER rows + removals warning; "Apply to board" runs the non-dry-run call then closes + triggers a config refresh.

> Mirror `.claude/skills/kanbanmate-design/ui_kits/config/new-pieces.html` `SyncBoardDialog`. Render the live `changes`/`removals` from the API instead of the mock's static rows.

- [ ] **Step 1: Implement the component**

```jsx
// web/src/components/SyncBoardDialog.jsx
import React from "react";
import * as api from "../api.js";

const { Dialog, Banner, Button, KeyChip } =
  window.KanbanMateDesignSystem_2463ad;

const TAG = { add: "ADD", rename: "RENAME", reorder: "REORDER" };

export default function SyncBoardDialog({ open, onClose, onApplied }) {
  const [diff, setDiff] = React.useState(null);
  const [err, setErr] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (!open) return;
    setDiff(null);
    setErr(null);
    api
      .provisionBoard({ dryRun: true })
      .then(setDiff)
      .catch((e) => setErr(e.message));
  }, [open]);

  const apply = async () => {
    setBusy(true);
    try {
      await api.provisionBoard({ dryRun: false });
      onApplied && onApplied();
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const changes = diff ? diff.changes : [];
  const removals = diff ? diff.removals : [];

  return (
    <Dialog
      open={open}
      onClose={onClose}
      width={560}
      title="Sync board"
      description="Provision GitHub Projects v2 Status options to match columns.yml"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={busy || !diff || diff.is_noop}
            onClick={apply}
          >
            {busy ? "Applying…" : "Apply to board"}
          </Button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Banner tone="neutral" title="This mutates the GitHub board">
          Re-provisions the Status options to match <code>columns.yml</code>{" "}
          (via the seeder). Tickets and card positions are untouched. Merge
          stays human-only.
        </Banner>
        {err && (
          <Banner tone="error" title="Sync failed">
            {err}
          </Banner>
        )}
        {!diff && !err && <div>Computing diff…</div>}
        {diff && diff.is_noop && (
          <div>
            Board already matches <code>columns.yml</code>. Nothing to apply.
          </div>
        )}
        {changes.map((c, i) => (
          <div
            key={i}
            className="diff-row"
            style={{ display: "flex", gap: 8, alignItems: "center" }}
          >
            <span
              className={`tag ${c.kind === "rename" || c.kind === "reorder" ? "ren" : "add"}`}
            >
              {TAG[c.kind]}
            </span>
            <KeyChip>{c.column}</KeyChip>
            {c.kind === "rename" && (
              <>
                <span>→</span>
                <KeyChip>{c.to}</KeyChip>
              </>
            )}
            {c.kind === "reorder" && (
              <span style={{ color: "var(--muted-foreground)" }}>
                pos {c.from_pos} → {c.to_pos}
              </span>
            )}
          </div>
        ))}
        {removals.length > 0 && (
          <Banner
            tone="warning"
            title={`${removals.length} column(s) on the board not in columns.yml`}
          >
            Not removed automatically (would orphan cards):{" "}
            {removals.map((r) => r.column).join(", ")}. Remove them in GitHub if
            intended.
          </Banner>
        )}
      </div>
    </Dialog>
  );
}
```

> The `.diff-row` / `.tag` / `.add` / `.ren` CSS classes come from `new-pieces.html:23-26`. Copy those rules into `web/src/ds/styles.css` if not already present. If the DS has no `tone="warning"` Banner, use `tone="neutral"` (check the DS bundle's Banner tones).

- [ ] **Step 2: Wire the Sync button in ColumnsPanel**

In `web/src/panels/ColumnsPanel.jsx`: add `const [sync, setSync] = React.useState(false)`, make the Sync button `onClick={() => setSync(true)}` and `disabled={dirty}` (title "Save before syncing"), and render `<SyncBoardDialog open={sync} onClose={() => setSync(false)} onApplied={() => window.location.reload()} />`.

- [ ] **Step 3: Build + manual verify (throwaway project only)**

Run: `cd web && npm run build`
Expected: build succeeds. Sync dialog opens, shows the dry-run diff. **Do not click Apply against a real board** unless it is a throwaway project; the dry-run diff is safe to view.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/SyncBoardDialog.jsx web/src/panels/ColumnsPanel.jsx web/src/ds/styles.css
git commit -m "feat(bridge): sync-board dialog (dry-run diff preview + apply)"
```

---

## Task 11: Packaging — ship the SPA under `[ui]` + CI build

**Files:**

- Modify: `pyproject.toml`, `.github/workflows/pr.yml`, `.gitignore`

**Interfaces:**

- Produces: the wheel includes `kanbanmate/webui/**`; CI builds the SPA before packaging/tests that need it; the source tree ignores the build output.

- [ ] **Step 1: Package-data + gitignore**

In `pyproject.toml` `[tool.setuptools.package-data]`, extend the `kanbanmate` list to include the build output:

```toml
[tool.setuptools.package-data]
kanbanmate = ["py.typed", "assets/*.tmpl", "assets/*.yml", "bin/check-*.sh", "webui/**/*"]
```

Add to `.gitignore`:

```
src/kanbanmate/webui/
web/node_modules/
```

Keep a tracked placeholder so the dir exists in a source checkout:

```bash
mkdir -p src/kanbanmate/webui && touch src/kanbanmate/webui/.gitkeep
git add -f src/kanbanmate/webui/.gitkeep
```

- [ ] **Step 2: CI build step**

Read `.github/workflows/pr.yml`. Before the step that runs `pip install -e ".[dev,ui,mcp]"`/tests, add a Node setup + SPA build so `webui/` is populated for the static-mount test and packaging:

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: "22"
- name: Build config UI
  run: npm --prefix web ci && npm --prefix web run build
```

> Match the existing workflow's step style/indentation — read it first. Place the Node steps after checkout, before the Python install/test job that imports the mount. If the workflow has multiple jobs, add to the one that runs `tests/http`.

- [ ] **Step 3: Verify the gate locally**

Run:

```bash
cd web && npm run build && cd ..
make lint && PYTHONPATH=src python -m pytest tests/http/test_static_mount.py -v
```

Expected: build OK; with `webui/index.html` present the mount path is exercised; lint clean.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .gitignore .github/workflows/pr.yml src/kanbanmate/webui/.gitkeep
git commit -m "build(bridge): package the config SPA under [ui] + CI build step"
```

---

## Final gate (run before opening the PR)

- [ ] `make check` (lint + test + module-size guards) — zero errors.
- [ ] `cd web && npm run build` — succeeds; `src/kanbanmate/webui/index.html` present.
- [ ] Residual-import grep: `grep -rn "columns_diff\|board_provision\|KNOWN_PLACEHOLDERS" src/ tests/ --include="*.py"` — every hit resolves.
- [ ] `python -c "import kanbanmate"` smoke test (bare import, no `[ui]`).
- [ ] Live exercise on a **copied** config + throwaway root (never the live clone): load editor, edit a prompt with a bad placeholder (squiggle + finding), fix, Save (YAML re-renders in the YAML tab), open Sync-board dry-run.

---

## Self-Review

**1. Spec coverage:**

- §2.1 local editor load/edit/validate/save → Task 8. ✓
- §2.2 rich prompt editor → Task 9. ✓
- §2.3 columns first-class (add/rename/reorder/inert) → Task 8 (ColumnsPanel) + Task 1 (diff backing rename). ✓
- §2.4 Sync board (diff, never silent removals, ensure_columns) → Tasks 1, 3, 5, 10. ✓
- §2.5 findings panel + field locus + click-to-locate → Task 8 (ValidationPanel/onGoto). ✓
- §2.6 served by config serve, no Node at runtime, [ui] extra → Tasks 6, 7, 11. ✓
- §3 React+shadcn reusing design system → Tasks 7–10. ✓
- §6.2 placeholder exposure → Tasks 2, 4. ✓
- §6.3 provision endpoint dry-run/apply → Task 5. ✓
- §7 serving/packaging/guarded mount → Tasks 6, 11. ✓
- §8 state/save-gate/sync-on-saved-config → Task 8 (save gate), Task 5 (desired from saved config). ✓
- §9 error handling (unreachable, save rejected, sync failure, missing build) → Tasks 6, 8, 10. ✓
- §10 testing layers → Tasks 1–6 (backend), manual for SPA. ✓
- §11 open decisions: placeholder endpoint = dedicated `GET /api/placeholders` (decided, Task 4); packaging = CI-build (decided, Task 11); editor = textarea+preview (decided, Task 9); ticket/branch = `feat/bridge` (header). ✓

**2. Placeholder scan:** No "TBD"/"implement later"; every code step shows code; tests are concrete. The "read the kit and adapt" instructions in Tasks 8–10 point at exact existing files with the exact transformation (global-attach → ES module) and the exact data swap (`window.KMConfigData` → API) — mechanical, not vague.

**3. Type consistency:** `ColumnChange`/`ColumnDiff`/`diff_columns(renames=…)` (Task 1) match their use in `board_provision` (Task 3) and the endpoint's `asdict` serialization (Task 5). `provision_board(root, *, desired_columns, renames, dry_run, seeder)` signature is identical in Tasks 3 and 5. `KNOWN_PLACEHOLDERS` dict shape (Task 2) matches `get_placeholders` consumption (Task 4) and the API client `getPlaceholders` shape used in `RichPromptEditor` (Task 9). API client method names (`api.js`, Task 7) match every call site (Tasks 8–10). ✓
