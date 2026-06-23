# Fast-track lanes (skiff) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route small-and-safe tickets through shorter lifecycle lanes (lite / express) decided by a cheap triage agent, while leaving the full lane and every safety invariant untouched.

**Architecture:** A new `Triage` stage launches first and classifies each ticket. It writes a durable `**track**` body field and an explicit _route_ breadcrumb, then the engine's session-end backstop moves the card to the chosen lane's entry column (`Brainstorming` for full, the new `Scope` for lite, `PrepareFeature` for express). Routing is by **topology** — the engine only ever moves along a whitelisted `Triage → X` edge — so `core/decide.py` stays free of conditional logic. The shared build/PR/review tail self-adapts to the artifacts each lane leaves on the per-ticket WIP branch, and `pr-review` scales its strictness by reading `**track**`.

**Tech Stack:** Python 3.11, dataclasses, PyYAML, pytest, mypy (strict), ruff. Hexagonal layering (core/ pure · adapters/ I/O · bin/ leaf entrypoints · app/daemon). GitHub Projects v2 via the urllib client.

## Global Constraints

- **Merge = human-only.** No lane auto-merges. `gh pr merge`, force-push, rebase, history-rewrite stay banned in every profile (the new `triage` profile inherits the full `_DENY`). Verbatim: `merge = human only` (CLAUDE.md).
- **No conditional logic in `core/decide.py`.** Routing is a topological engine move via the session-end backstop, validated against the transitions whitelist.
- **Conservative-by-construction.** Triage routes to `full` on any uncertainty, on any sensitive-path/keyword/label match, and on any of its own failures.
- **Fail-soft leaf entrypoints.** `bin/` helpers + session-end never crash the calling agent shell: usage error → exit 2; store/wiring error → reported to stderr, exit 1 (helpers) / exit 0 (session-end, the always-run leaf). All board ops wrapped.
- **Breadcrumb-keying invariant.** Every breadcrumb is keyed by the **issue number** (never a node id); the writer and all readers share the identical key.
- **Module size:** soft warning 800 LOC, hard ceiling 1000 LOC per `src/**/*.py` (`make size`).
- **Docstrings:** Google-style (`Args:`/`Returns:`/`Raises:`) on every module/class/function. Inline comments explain the _why_, in English.
- **Search safety:** every `rg`/`grep` carries a type/glob filter. **Commits:** Conventional Commits, scope `skiff` for milestone commits; never AI attribution / version prefixes.
- **Lane vocabulary is closed:** exactly `{"full", "lite", "express"}`.
- **`docs/` is globally gitignored** — `git add -f` for any file under `docs/`.

**Lane → entry column map (single source of truth, referenced throughout):**

| lane    | entry column (key) | entry column (name) | head stage fired on arrival        |
| ------- | ------------------ | ------------------- | ---------------------------------- |
| full    | `Brainstorming`    | `Brainstorming`     | interactive brainstorm (unchanged) |
| lite    | `Scope` (NEW)      | `Scope`             | compressed mini-design + mini-plan |
| express | `PrepareFeature`   | `Prepare feature`   | create-branch → build (no design)  |

---

### Task 1: Route breadcrumb in the store

**Files:**

- Modify: `src/kanbanmate/adapters/store/fs_breadcrumbs.py` (add the route breadcrumb to `AgentBreadcrumbsMixin`)
- Modify: `src/kanbanmate/ports/store.py` (add the three protocol methods)
- Modify: `src/kanbanmate/adapters/store/fs_store.py:296` region (purge_ticket clears `route/<issue>`; ensure the `route/` dir is created in `__init__` alongside `advances/`/`done/`)
- Test: `tests/adapters/test_fs_breadcrumbs.py` (or the existing breadcrumb test module — match the repo's location)

**Interfaces:**

- Produces: `record_agent_route(issue_number: int, lane: str, *, now: float) -> None`; `recent_agent_route(issue_number: int, *, now: float) -> str` (returns the lane, or `""` when absent/expired/corrupt); `clear_agent_route(issue_number: int) -> None`. TTL = the same `_DONE_TTL` (1800 s) horizon as the done breadcrumb (the route + done breadcrumbs are written together by triage).
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_fs_breadcrumbs.py
import time

from kanbanmate.adapters.store.fs_store import FsStateStore


def test_route_breadcrumb_roundtrips_the_lane(tmp_path) -> None:
    """record_agent_route writes the lane; recent_agent_route reads it back within TTL."""
    store = FsStateStore(tmp_path)
    now = time.time()
    assert store.recent_agent_route(7, now=now) == ""  # absent → empty
    store.record_agent_route(7, "express", now=now)
    assert store.recent_agent_route(7, now=now) == "express"


def test_route_breadcrumb_expires_after_ttl(tmp_path) -> None:
    """An aged route breadcrumb reads as empty (mirrors the done TTL horizon)."""
    store = FsStateStore(tmp_path)
    store.record_agent_route(7, "lite", now=1000.0)
    assert store.recent_agent_route(7, now=1000.0 + 1801.0) == ""


def test_clear_agent_route_is_idempotent(tmp_path) -> None:
    """clear_agent_route removes the marker and never raises when absent."""
    store = FsStateStore(tmp_path)
    store.record_agent_route(7, "full", now=500.0)
    store.clear_agent_route(7)
    store.clear_agent_route(7)  # no-op, no raise
    assert store.recent_agent_route(7, now=500.0) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adapters/test_fs_breadcrumbs.py -k route -v`
Expected: FAIL with `AttributeError: 'FsStateStore' object has no attribute 'record_agent_route'`

- [ ] **Step 3: Add the route breadcrumb to the mixin**

In `src/kanbanmate/adapters/store/fs_breadcrumbs.py`, after the agent-done block (after `clear_agent_done`, ~line 206), add:

```python
    # ------------------------------------------------------------------
    # Agent-route breadcrumb (the lane the triage stage chose, skiff)
    # ------------------------------------------------------------------

    def _route_path(self, issue_number: int) -> Path:
        """Return the filesystem path for ``issue_number``'s route breadcrumb (issue-keyed)."""
        return self.root / "route" / f"{issue_number}"

    def record_agent_route(self, issue_number: int, lane: str, *, now: float) -> None:
        """Drop the triage stage's chosen LANE breadcrumb (skiff fast-track routing).

        Writes ``<root>/route/<issue>`` = ``{"ts": now, "lane": lane}``. Written SYNCHRONOUSLY by
        ``bin/kanban_route.py`` when the triage stage has classified the ticket, BEFORE it runs
        ``kanban-done``. The session-end backstop reads it (:meth:`recent_agent_route`) to move the
        card to the lane's entry column. Unlike the boolean done/advance breadcrumbs this carries a
        PAYLOAD (the lane), because the engine move target depends on it. Keyed by the issue number.

        Args:
            issue_number: The ticket whose lane to record (the breadcrumb key).
            lane: The chosen lane (one of ``"full"`` / ``"lite"`` / ``"express"``).
            now: The wall-clock timestamp written into the breadcrumb.
        """
        self._route_path(issue_number).write_text(json.dumps({"ts": now, "lane": lane}))

    def recent_agent_route(self, issue_number: int, *, now: float) -> str:
        """Return the recent route lane for ``issue_number``, or ``""`` when absent/expired/corrupt.

        The lane is "recent" within :data:`_DONE_TTL` (1800 s — the same horizon as the done
        breadcrumb, which triage writes in the same breath). Degrades to ``""`` on a missing or
        unreadable marker (no raise — a poison file must never wedge the session-end leaf).

        Args:
            issue_number: The ticket whose lane to read (the key).
            now: The wall-clock timestamp the TTL is measured against.

        Returns:
            The recorded lane string, or ``""`` when no fresh, well-formed breadcrumb exists.
        """
        path = self._route_path(issue_number)
        if not path.exists():
            return ""
        try:
            data = json.loads(path.read_text())
            ts = float(data.get("ts", 0.0))
            lane = str(data.get("lane", ""))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return ""
        return lane if (now - ts) <= _DONE_TTL else ""

    def clear_agent_route(self, issue_number: int) -> None:
        """Remove ``issue_number``'s route breadcrumb (no-op when absent).

        Unlinks ``<root>/route/<issue>``; normally consumed by ``purge_ticket`` at teardown.

        Args:
            issue_number: The ticket whose route breadcrumb to clear (the key).
        """
        self._unlink(self._route_path(issue_number))
```

- [ ] **Step 4: Create the `route/` dir in the store `__init__` and purge it in `purge_ticket`**

In `src/kanbanmate/adapters/store/fs_store.py`, find where `__init__` creates the breadcrumb dirs (near the `advances/` and `done/` mkdir, ~line 120-122) and add the `route/` dir the same way:

```python
        # The agent-route breadcrumb directory (skiff fast-track); one marker per issue.
        (self.root / "route").mkdir(parents=True, exist_ok=True)
```

In `purge_ticket` (the block that already clears `clear_agent_advance` + `clear_agent_done`, ~line 355-360), add:

```python
        # Purge the route breadcrumb too (idempotent / no-raise): a torn-down ticket must leave no
        # stale lane marker that a later session-end could misread.
        self.clear_agent_route(issue_number)
```

- [ ] **Step 5: Add the protocol methods**

In `src/kanbanmate/ports/store.py`, after `recent_agent_done` (~line 508) / its `clear` sibling, add the three abstract methods mirroring the done-breadcrumb signatures (`record_agent_route(self, issue_number: int, lane: str, *, now: float) -> None`, `recent_agent_route(self, issue_number: int, *, now: float) -> str`, `clear_agent_route(self, issue_number: int) -> None`) with full Google-style docstrings.

- [ ] **Step 6: Run tests + lint**

Run: `pytest tests/adapters/test_fs_breadcrumbs.py -k route -v && mypy src/kanbanmate/adapters/store src/kanbanmate/ports`
Expected: PASS, no mypy errors.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(skiff): route breadcrumb in the state store"
```

---

### Task 2: Lane→entry resolution (pure)

**Files:**

- Modify: `src/kanbanmate/core/transitions_defaults.py` (add the `TRACK_ENTRY` constant + `TRACK_VALUES`)
- Modify: `src/kanbanmate/bin/_clone_config.py` (add `route_entry_column(lane)` pure resolver)
- Test: `tests/bin/test_clone_config.py`

**Interfaces:**

- Produces: `TRACK_ENTRY: dict[str, str]` (`{"full": "Brainstorming", "lite": "Scope", "express": "PrepareFeature"}`); `TRACK_VALUES: tuple[str, ...]` (`("full", "lite", "express")`); `route_entry_column(lane: str) -> str | None` (the entry column KEY, or `None` for an unknown lane).
- Consumes: nothing.

- [ ] **Step 1: Write the failing test**

```python
# tests/bin/test_clone_config.py
from kanbanmate.bin._clone_config import route_entry_column


def test_route_entry_column_maps_known_lanes() -> None:
    assert route_entry_column("full") == "Brainstorming"
    assert route_entry_column("lite") == "Scope"
    assert route_entry_column("express") == "PrepareFeature"


def test_route_entry_column_unknown_lane_is_none() -> None:
    assert route_entry_column("") is None
    assert route_entry_column("turbo") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bin/test_clone_config.py -k route_entry -v`
Expected: FAIL with `ImportError: cannot import name 'route_entry_column'`

- [ ] **Step 3: Add the constants in `transitions_defaults.py`**

Near `DEFAULT_MOVE_RATE_LIMIT_PER_HOUR` (~line 781), add:

```python
# skiff fast-track: the lane vocabulary + each lane's entry column KEY. The triage stage routes a
# ticket onto a lane by having the ENGINE move the card to this column (a whitelisted Triage→entry
# edge), so the launch on that edge fires the lane's head stage. Pairs with the columns shipped in
# columns.yml.tmpl + the Triage→{entry} transitions below; a custom board that renames these columns
# must update this map too.
TRACK_VALUES: tuple[str, ...] = ("full", "lite", "express")
TRACK_ENTRY: dict[str, str] = {
    "full": "Brainstorming",
    "lite": "Scope",
    "express": "PrepareFeature",
}
```

- [ ] **Step 4: Add the resolver in `_clone_config.py`**

After `auto_advance_target` (~line 189), add:

```python
def route_entry_column(lane: str) -> str | None:
    """Return the entry column KEY for a triage-chosen ``lane``, else ``None`` (skiff).

    The triage stage records a lane (``full`` / ``lite`` / ``express``) via ``kanban-route``; the
    session-end backstop maps it here to the column the engine moves the card into (the head edge
    that fires the lane's first stage). An unknown lane → ``None`` → the backstop fails soft to
    ``full`` (the conservative default) without moving into an unwhitelisted column.

    Args:
        lane: The recorded lane string.

    Returns:
        The entry column key for a known lane, else ``None``.
    """
    return TRACK_ENTRY.get(lane)
```

Add the import at the top of `_clone_config.py` (it already imports from `transitions_defaults` — extend it):

```python
from kanbanmate.core.transitions_defaults import TRACK_ENTRY  # plus existing names
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/bin/test_clone_config.py -k route_entry -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(skiff): lane→entry column resolver"
```

---

### Task 3: The `kanban-route` helper

**Files:**

- Create: `src/kanbanmate/bin/kanban_route.py`
- Modify: `pyproject.toml:36-45` (register the console script)
- Test: `tests/bin/test_kanban_route.py`

**Interfaces:**

- Consumes: `route_entry_column` / `TRACK_VALUES` (Task 2); `FsStateStore.record_agent_route` (Task 1); `check_pin`, `helper_store_root`, `parse_issue_arg` from `bin/_pin` (existing, used by `kanban_done.py`).
- Produces: console script `kanban-route` → `kanbanmate.bin.kanban_route:main`. Usage: `kanban-route <issue> <lane>`.

- [ ] **Step 1: Write the failing test**

```python
# tests/bin/test_kanban_route.py
from unittest.mock import MagicMock

import pytest

from kanbanmate.bin import kanban_route
from kanbanmate.bin.kanban_route import main


def _patch_store(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    store = MagicMock()
    monkeypatch.setattr(kanban_route, "FsStateStore", lambda *a, **k: store)
    monkeypatch.setattr(kanban_route, "helper_store_root", lambda: ("/root", None))
    monkeypatch.setattr(kanban_route, "check_pin", lambda issue: None)
    return store


def test_records_the_chosen_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid <issue> <lane> records the route breadcrumb and exits 0."""
    store = _patch_store(monkeypatch)
    assert main(["7", "express"]) == 0
    store.record_agent_route.assert_called_once()
    assert store.record_agent_route.call_args.args[0] == 7
    assert store.record_agent_route.call_args.args[1] == "express"


def test_unknown_lane_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown lane is a usage error (exit 2); the store is never touched."""
    store = _patch_store(monkeypatch)
    assert main(["7", "turbo"]) == 2
    store.record_agent_route.assert_not_called()


def test_missing_args_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _patch_store(monkeypatch)
    assert main(["7"]) == 2
    store.record_agent_route.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/bin/test_kanban_route.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'kanbanmate.bin.kanban_route'`

- [ ] **Step 3: Write the helper (mirror `kanban_done.py`)**

```python
# src/kanbanmate/bin/kanban_route.py
"""Agent helper: the triage stage's lane decision — ``kanban-route <issue> <lane>`` (skiff).

The triage stage classifies a ticket (size + sensitivity) and routes it onto a fast-track lane by
recording the chosen lane as a persisted breadcrumb. The session-end backstop reads it and moves the
card to the lane's entry column (``full``→Brainstorming, ``lite``→Scope, ``express``→PrepareFeature),
so the launch on that whitelisted ``Triage→entry`` edge fires the lane's head stage. The agent runs
this BEFORE ``kanban-done`` (which ends the session).

A leaf entrypoint (DESIGN §3.2): a pure local store write, no GitHub network. PIN-aware (R1, §29.1)
and FAIL-SOFT: a bad argument exits non-zero with clear stderr and never crashes the calling agent
shell. The lane vocabulary is closed — an unknown lane is a usage error (exit 2), never a silent
mis-route.
"""

from __future__ import annotations

import sys
import time

from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.bin._pin import check_pin, helper_store_root, parse_issue_arg
from kanbanmate.core.transitions_defaults import TRACK_VALUES

_PROG = "kanban-route"


def main(argv: list[str] | None = None) -> int:
    """Record the triage stage's chosen LANE for ``<issue>`` (skiff fast-track routing).

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``. Expects exactly ``<issue> <lane>``.

    Returns:
        ``0`` on success, ``2`` on a usage error, ``1`` on any other failure.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    if len(raw_argv) != 2:
        print(f"usage: {_PROG} <issue> <lane>  (lane: {'|'.join(TRACK_VALUES)})", file=sys.stderr)
        return 2
    try:
        issue = parse_issue_arg(raw_argv[0])
    except ValueError:
        print(f"{_PROG}: issue must be an integer, got {raw_argv[0]!r}", file=sys.stderr)
        return 2
    lane = raw_argv[1].strip()
    if lane not in TRACK_VALUES:
        print(
            f"{_PROG}: unknown lane {lane!r}; allowed: {', '.join(TRACK_VALUES)}",
            file=sys.stderr,
        )
        return 2

    # Pin enforcement (R1, §29.1): refuse a mismatched issue when the worktree is pinned.
    pin_error = check_pin(issue)
    if pin_error is not None:
        print(f"{_PROG}: {pin_error}", file=sys.stderr)
        return 1

    try:
        _store_root, _nudge_root = helper_store_root()
        store = (
            FsStateStore(_store_root)
            if _nudge_root is None
            else FsStateStore(_store_root, nudge_root=_nudge_root)
        )
        store.record_agent_route(issue, lane, now=time.time())
    except Exception as exc:  # noqa: BLE001 — never crash the caller; report + exit non-zero.
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 1

    print(f"route #{issue}: lane {lane!r} recorded; the engine will move the card to its lane entry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Register the console script**

In `pyproject.toml`, in `[project.scripts]` (alphabetical, after `kanban-progress`):

```toml
kanban-route = "kanbanmate.bin.kanban_route:main"
```

Then re-install so the script resolves: `pip install -e ".[dev]"`

- [ ] **Step 5: Run tests**

Run: `pytest tests/bin/test_kanban_route.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(skiff): kanban-route helper records the triage lane decision"
```

---

### Task 4: Routed-advance backstop in session-end

**Files:**

- Modify: `src/kanbanmate/bin/kanban_session_end.py` (add `_routed_advance`; read the route breadcrumb before purge; branch the done path on `state.advance == "route"`)
- Test: `tests/bin/test_kanban_session_end.py`

**Interfaces:**

- Consumes: `route_entry_column` (Task 2); `recent_agent_route` (Task 1); existing `resolve_column`, `load_clone_columns`, `load_clone_transitions`, `cfg.get`, `cfg.move_rate_limit_per_hour`, `client.move_card`, `store.move_count_for_item_last_hour`, `store.record_move_for_item`, `store.record_pending_launch`, `store.nudge_daemon`.
- Produces: a `RoutedAdvanceResult = Literal["routed", "stopped", "parked_blocked"]` mirroring `AutoAdvanceResult`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/bin/test_kanban_session_end.py  (add to the existing module)
def test_route_directive_moves_card_to_lane_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean-done triage stage (advance='route') moves the card to the lane's entry column."""
    store = MagicMock()
    store.load.return_value = _state(stage="Triage", advance="route")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    store.recent_agent_route.return_value = "express"  # triage chose express
    store.move_count_for_item_last_hour.return_value = 0
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    # express → PrepareFeature (key) → its display name "Prepare feature".
    client.move_card.assert_called_once_with("PVTI_node", "Prepare feature")
    store.record_move_for_item.assert_called_once()


def test_route_directive_unknown_lane_fails_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty/unknown recorded lane → no move, session-end still exits 0 (card stays in Triage)."""
    store = MagicMock()
    store.load.return_value = _state(stage="Triage", advance="route")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    store.recent_agent_route.return_value = ""  # triage crashed before routing
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    _patch_backstop_config(monkeypatch)

    assert main(["7"]) == 0
    client.move_card.assert_not_called()


def test_route_rate_limited_parks_in_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """At/over the per-issue rate limit the routed move parks in Blocked (anti-loop bound)."""
    store = MagicMock()
    store.load.return_value = _state(stage="Triage", advance="route")
    store.recent_agent_advance.return_value = False
    store.recent_agent_done.return_value = True
    store.recent_agent_route.return_value = "lite"
    store.move_count_for_item_last_hour.return_value = 10  # >= cap
    monkeypatch.setattr(kanban_session_end, "FsStateStore", lambda *a, **k: store)
    client = _patch_github_capture_client(monkeypatch)
    upsert = MagicMock()
    monkeypatch.setattr(kanban_session_end, "upsert_stage_comment", upsert)
    monkeypatch.setattr(kanban_session_end, "update_body_status", MagicMock())
    _patch_backstop_config(monkeypatch, rate_limit=10)

    assert main(["7"]) == 0
    client.move_card.assert_called_once_with("PVTI_node", "Blocked")
    assert upsert.call_args.kwargs["header"].status == "blocked"
```

> Note: the existing `_patch_backstop_config` helper must make `cfg.get("Triage", "Brainstorming"|"Scope"|"PrepareFeature")` resolve to a launch transition (non-None) and `resolve_column` resolve those keys. If the helper builds a minimal `TransitionConfig`/columns, extend it to include the Triage edges + the new columns. Read the helper before writing the tests and adjust its fixtures.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/bin/test_kanban_session_end.py -k route -v`
Expected: FAIL (no `recent_agent_route` handling; card not moved).

- [ ] **Step 3: Add `_routed_advance` (mirror `_auto_advance`)**

In `src/kanbanmate/bin/kanban_session_end.py`, add the result type beside `AutoAdvanceResult` (~line 75):

```python
# The outcome of :func:`_routed_advance` (skiff): ``routed`` (moved to the lane entry), ``stopped``
# (unknown/empty lane / no item id / unwhitelisted entry → no move), or ``parked_blocked`` (the
# rate-limit backstop parked the card). The done-branch caller finalizes the sticky to match.
RoutedAdvanceResult = Literal["routed", "stopped", "parked_blocked"]
```

Add the function next to `_auto_advance`:

```python
def _routed_advance(
    state: TicketState,
    issue: int,
    lane: str,
    client: GithubClient,
    entry: ProjectEntry,
    store: FsStateStore,
    *,
    now: float,
) -> RoutedAdvanceResult:
    """Move a clean-done TRIAGE stage's card to its chosen lane's entry column (skiff backstop).

    The triage transition carries ``advance: route``; the agent recorded a lane via ``kanban-route``
    and ran ``kanban-done``. This resolves the lane → entry column (:func:`route_entry_column`),
    VALIDATES that ``Triage → entry`` is a whitelisted launch transition (the engine only ever moves
    along a real, prompt-bearing edge it would have launched anyway — the routing safety guard), then
    moves the card there so the daemon's next diff fires the lane's head stage. Mirrors
    :func:`_auto_advance`: same rate-limit backstop, same direct ``client.move_card`` (never
    ``kanban_move.main``), same ``record_move_for_item`` + ``record_pending_launch`` + reflex
    ``nudge_daemon``, same fail-soft discipline (every board op wrapped; a failure logs + returns a
    degraded result, session-end still exits 0).

    Conservative fallback: an unknown/empty lane resolves to ``None`` → no move (the card stays in
    Triage, visible for an operator re-drag) rather than guessing a target.

    Args:
        state: The loaded ticket state (carries ``stage`` == "Triage" and ``item_id``).
        issue: The ticket's issue number (rate-limit + comment key).
        lane: The recorded lane (``full`` / ``lite`` / ``express``).
        client: The fail-soft GitHub client wired by the caller.
        entry: The resolved project registry entry (for the clone config loaders).
        store: The runtime state store (rate-limit ledger + breadcrumbs).
        now: Current wall-clock time (rate-limit window + recorded move timestamp).
    """
    entry_key = route_entry_column(lane)
    if entry_key is None:
        # Unknown/empty lane → no move (triage failure / pre-route crash). Fail-soft: the card stays
        # in Triage; an operator re-drag (Backlog→Triage) re-runs triage.
        print(
            f"{_PROG}: warning: ticket #{issue} route lane {lane!r} is not a known lane; "
            "skipping the engine move (card stays in Triage)",
            file=sys.stderr,
        )
        return "stopped"
    if not state.item_id:
        return "stopped"
    try:
        columns = load_clone_columns(entry)
        cfg = load_clone_transitions(entry)
    except Exception as exc:  # noqa: BLE001 — fail-soft: a config-read failure never breaks session-end.
        print(f"{_PROG}: warning: could not load clone config for #{issue} route: {exc}", file=sys.stderr)
        return "stopped"

    target_col = resolve_column(columns, entry_key)
    if target_col is None:
        print(
            f"{_PROG}: warning: route entry {entry_key!r} for #{issue} is not a known column; skipping",
            file=sys.stderr,
        )
        return "stopped"

    # ROUTING SAFETY GUARD: the engine only moves along a whitelisted Triage→entry launch edge. An
    # entry that is not a real transition (mis-config / tampered breadcrumb) → no move.
    edge = cfg.get(state.stage, target_col.key)
    if edge is None or not getattr(edge, "prompt", None):
        print(
            f"{_PROG}: warning: {state.stage}->{target_col.key} for #{issue} is not a whitelisted "
            "launch transition; refusing the route move",
            file=sys.stderr,
        )
        return "stopped"

    # OUTER per-issue rate-limit backstop (identical to _auto_advance).
    if store.move_count_for_item_last_hour(issue, now=now) >= cfg.move_rate_limit_per_hour:
        blocked_col = resolve_column(columns, _BLOCKED_KEY)
        blocked_name = blocked_col.name if blocked_col is not None else _BLOCKED_KEY
        try:
            client.move_card(state.item_id, blocked_name)
            client.comment(issue, "KanbanMate: triage route rate limit exceeded — parked in Blocked.")
        except Exception as exc:  # noqa: BLE001 — fail-soft.
            print(f"{_PROG}: warning: could not park #{issue} in Blocked (route rate limit): {exc}", file=sys.stderr)
        store.record_move_for_item(issue, now=now)
        return "parked_blocked"

    try:
        client.move_card(state.item_id, target_col.name)
        store.record_move_for_item(issue, now=now)
        # The lane entry is ALWAYS a launch edge (validated above) → record the pending_launch
        # breadcrumb so a daemon restart / stale baseline between this move and the launch-detect
        # tick never drops the head stage (#55/#27 pattern).
        store.record_pending_launch(state.item_id, from_col=state.stage, to_col=target_col.key, now=now)
        store.nudge_daemon()  # reflex wake
        print(f"{_PROG}: ticket #{issue} routed -> {target_col.name} (lane {lane!r}).")
        return "routed"
    except Exception as exc:  # noqa: BLE001 — fail-soft: a route move never breaks session-end.
        print(f"{_PROG}: warning: could not route #{issue} to {target_col.name!r}: {exc}", file=sys.stderr)
        return "stopped"
```

Add the imports at the top (extend the existing `_clone_config` import):

```python
from kanbanmate.bin._clone_config import route_entry_column  # plus existing imports
```

- [ ] **Step 4: Read the route breadcrumb before purge + branch the done path**

In `main()`, in the breadcrumb-read block (after `done = store.recent_agent_done(...)`, ~line 370, BEFORE `purge_ticket`), add:

```python
        # skiff: read the triage route lane BEFORE purge_ticket clears it (same load-bearing
        # ordering as advance/done). Empty when the stage is not a triage route.
        routed_lane = store.recent_agent_route(issue, now=now)
```

In the done branch (4c), replace the single `advance_result = _auto_advance(...)` call with a route-vs-auto split, and treat `"routed"` like `"advanced"` for the sticky (✅):

```python
            if state.advance == "route":
                # skiff: the triage stage routes to a lane entry instead of a fixed auto target.
                route_result = _routed_advance(state, issue, routed_lane, client, entry, store, now=now)
                advance_result = "parked_blocked" if route_result == "parked_blocked" else (
                    "advanced" if route_result == "routed" else "stopped"
                )
            else:
                advance_result = _auto_advance(state, issue, client, entry, store, now=now)
```

(The existing sticky logic — `if advance_result == "parked_blocked": blocked else: done` — then finalizes ✅ for a successful route and ⛔ for a rate-limited park, unchanged.)

- [ ] **Step 5: Run tests + lint + size**

Run: `pytest tests/bin/test_kanban_session_end.py -v && mypy src/kanbanmate/bin/kanban_session_end.py && make size`
Expected: PASS; `kanban_session_end.py` stays under the 1000-LOC ceiling (if it crosses, extract `_routed_advance` + `_auto_advance` into a `bin/_backstop.py` sibling and re-import — note this in the commit).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(skiff): routed-advance backstop moves triage cards to their lane entry"
```

---

### Task 5: The `triage` permission profile

**Files:**

- Modify: `src/kanbanmate/core/profiles.py:16` (add `"triage"`)
- Modify: `src/kanbanmate/adapters/perms.py` (`_PROFILE_ALLOW` + `_PINNED_MODE`)
- Test: `tests/adapters/test_perms.py`

**Interfaces:**

- Consumes: nothing new. `config_validate._check_v4_profile` already validates against `PROFILES` — no change.
- Produces: a read-only profile that allows reading, code search, `kanban-route`, `kanban-update-body` (the track field), `kanban-comment`, `kanban-done`; inherits the full `_DENY` (no merge, no push, no edit).

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_perms.py
from kanbanmate.adapters.perms import allow_list, deny_list, pinned_mode
from kanbanmate.core.profiles import PROFILES


def test_triage_is_a_known_profile() -> None:
    assert "triage" in PROFILES


def test_triage_allows_route_and_read_only_shell_but_no_edit() -> None:
    allow = allow_list("triage")
    assert "Read" in allow
    assert "Bash(kanban-route*)" in allow
    assert "Bash(kanban-update-body*)" in allow
    assert "Edit" not in allow  # read-only: no source mutation
    assert "Bash" not in allow  # no broad shell


def test_triage_inherits_the_full_deny_set() -> None:
    deny = deny_list("triage")
    assert "Bash(gh pr merge*)" in deny  # merge still banned
    assert any("--force" in d for d in deny)


def test_triage_pinned_mode_is_auto() -> None:
    assert pinned_mode("triage") == "auto"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/adapters/test_perms.py -k triage -v`
Expected: FAIL (`"triage" not in PROFILES`).

- [ ] **Step 3: Add the profile**

`src/kanbanmate/core/profiles.py:16`:

```python
PROFILES: tuple[str, ...] = ("docs", "prepare", "dev", "check", "merge", "triage")
```

`src/kanbanmate/adapters/perms.py`, add to `_PROFILE_ALLOW` (after `"check"`):

```python
    # triage — the skiff fast-track classifier (read-only). It reads the ticket + a quick code peek
    # + the sensitive-paths config, then records its decision (the **track** body field + the route
    # breadcrumb). It NEVER edits source, pushes, or merges: no ``Edit``, no broad ``Bash`` — only
    # read + code-search verbs + the kanban decision/terminal helpers. The universal deny-list applies
    # unchanged, so merge / force-push / history-rewrite stay banned.
    "triage": (
        "Read",
        "Bash(cat*)",
        "Bash(ls*)",
        "Bash(grep*)",
        "Bash(rg*)",
        "Bash(git status*)",
        "Bash(git log*)",
        "Bash(git diff*)",
        "Bash(git show*)",
        "Bash(gh issue view*)",
        "Bash(kanban-comment*)",
        "Bash(kanban-update-body*)",
        "Bash(kanban-route*)",
        "Bash(kanban-done*)",
    ),
```

Add to `_PINNED_MODE`:

```python
    "triage": "auto",
```

- [ ] **Step 4: Run tests + lint**

Run: `pytest tests/adapters/test_perms.py -k triage -v && pytest tests/ -k config_validate -v`
Expected: PASS (config-validate auto-accepts the new profile).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(skiff): read-only triage permission profile"
```

---

### Task 6: The `**track**` body field

**Files:**

- Modify: `src/kanbanmate/core/body_edit.py:25` (`PRESERVED_MARKERS`)
- Modify: `src/kanbanmate/core/ticket_fields.py` (`parse_ticket_fields` result + branch)
- Test: `tests/core/test_ticket_fields.py`, `tests/core/test_body_edit.py`

**Interfaces:**

- Consumes: existing `set_field` / `kanban-update-body --set-field track <lane>` (no change needed — `set_field` is generic).
- Produces: `parse_ticket_fields(body)["track"]` (the lane string, or `""`). `"track"` added to `PRESERVED_MARKERS` so the status-header transform stays region-disjoint from it.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_ticket_fields.py
from kanbanmate.core.ticket_fields import parse_ticket_fields


def test_parses_the_track_field() -> None:
    body = "**codename**: skiff\n**track**: express\n"
    fields = parse_ticket_fields(body)
    assert fields["track"] == "express"


def test_track_defaults_to_empty_when_absent() -> None:
    assert parse_ticket_fields("**codename**: x")["track"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_ticket_fields.py -k track -v`
Expected: FAIL with `KeyError: 'track'`.

- [ ] **Step 3: Add the field**

`src/kanbanmate/core/body_edit.py:25`:

```python
PRESERVED_MARKERS: tuple[str, ...] = ("roadmap", "codename", "design", "plans", "track")
```

`src/kanbanmate/core/ticket_fields.py` in `parse_ticket_fields`: extend the result dict default and add the branch:

```python
    result: dict[str, str] = {"codename": "", "design_path": "", "plan_paths": "", "track": ""}
    # ... inside the for loop, alongside the codename/design/plans branches:
        elif key == "track":
            result["track"] = val
```

(Update the docstring's "exactly three keys" to "four keys" and document `track`.)

- [ ] **Step 4: Run tests**

Run: `pytest tests/core/test_ticket_fields.py tests/core/test_body_edit.py -v`
Expected: PASS (the body_edit roundtrip test still preserves all markers, now including `track`).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(skiff): **track** ticket-body field"
```

---

### Task 7: Board columns `Triage` + `Scope`

**Files:**

- Modify: `src/kanbanmate/assets/columns.yml.tmpl` (add the two columns)
- Modify: `.claude/kanban/columns.yml` (the live board config — add the same two; `git add -f`)
- Test: `tests/cli/test_init.py` or `tests/core/test_columns.py` (the template parses with the new columns)

**Interfaces:**

- Produces: two new INERT columns. `Triage` is positioned after `Backlog`; `Scope` after `Plan` (visually near the design stages). `ReadyToDev` and the rest are unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_columns.py
import importlib.resources

from kanbanmate.core.columns import load_columns


def test_template_declares_triage_and_scope() -> None:
    text = (importlib.resources.files("kanbanmate.assets") / "columns.yml.tmpl").read_text()
    columns = load_columns(text)
    assert "Triage" in columns and columns["Triage"].name == "Triage"
    assert "Scope" in columns and columns["Scope"].name == "Scope"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/test_columns.py -k triage_and_scope -v`
Expected: FAIL (`"Triage" not in columns`).

- [ ] **Step 3: Add the columns to the template**

In `src/kanbanmate/assets/columns.yml.tmpl`, insert `Triage` right after the `Backlog` entry:

```yaml
- key: Triage
  name: Triage
  # Inert: the skiff fast-track classifier stage. The launch lives on the
  # Backlog -> Triage transition (a cheap agent classifies size + sensitivity
  # and records the lane). The engine then routes the card to the lane's entry
  # column (full -> Brainstorming, lite -> Scope, express -> Prepare feature).
```

And insert `Scope` right after the `Plan` entry:

```yaml
- key: Scope
  name: Scope
  # Inert: the lite-lane compressed design+plan stage. The launch lives on the
  # Triage -> Scope transition (one pass: mini-design + mini-plan, obvious
  # decisions taken autonomously, no human gate). Auto-advances to Prepare feature.
```

- [ ] **Step 4: Mirror into the live config**

Make the identical two insertions in `.claude/kanban/columns.yml`.

- [ ] **Step 5: Run tests**

Run: `pytest tests/core/test_columns.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git add -f .claude/kanban/columns.yml
git commit -m "feat(skiff): Triage + Scope board columns"
```

---

### Task 8: Transitions — triage routing + lane heads + prompts

**Files:**

- Modify: `src/kanbanmate/core/transitions_defaults.py` (replace `Backlog→Brainstorming`; add `Triage→Brainstorming`, `Triage→Scope`, `Triage→PrepareFeature`, `Scope→PrepareFeature`; add `_TRIAGE_PROMPT` + `_SCOPE_PROMPT`; make `create-branch` + `_IMPLEMENT_PROMPT` plan-adaptive)
- Test: `tests/core/test_transitions_defaults.py`

**Interfaces:**

- Consumes: `_AUTONOMY`, `_SCOPE_GUARD`, `_IDENTITY_THEN_STATE`, `_GROUNDING_DISCIPLINE`, `_CLEAN_STOP` (existing prompt blocks), `_BRAINSTORM_PROMPT`, the existing PrepareFeature-entry (create-branch) prompt constant.
- Produces: the routed flow. `Backlog→Triage` carries `advance: route`; each `Triage→{entry}` is a launch edge with the head stage's advance directive.

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/test_transitions_defaults.py (extend TestHybridAdvanceDirectives / add a class)
class TestSkiffRouting:
    def test_backlog_routes_through_triage(self) -> None:
        cfg = load_transitions(_render_doc("owner/repo"))
        # Backlog now launches the triage stage, which routes (advance: route).
        t = cfg.get("Backlog", "Triage")
        assert t is not None and t.profile == "triage" and t.advance == "route"
        assert t.prompt  # a launch transition
        # The old direct Backlog→Brainstorming launch is gone.
        assert cfg.get("Backlog", "Brainstorming") is None

    def test_triage_lane_entries_are_whitelisted_launches(self) -> None:
        cfg = load_transitions(_render_doc("owner/repo"))
        full = cfg.get("Triage", "Brainstorming")
        lite = cfg.get("Triage", "Scope")
        express = cfg.get("Triage", "PrepareFeature")
        assert full and full.advance == "auto:Spec" and full.prompt
        assert lite and lite.advance == "auto:PrepareFeature" and lite.prompt
        assert express and express.advance == "auto:InProgress" and express.prompt

    def test_scope_auto_advances_into_prepare_feature(self) -> None:
        cfg = load_transitions(_render_doc("owner/repo"))
        t = cfg.get("Scope", "PrepareFeature")
        assert t is not None and t.advance == "auto:InProgress" and t.prompt

    def test_track_entry_targets_all_exist_as_columns(self) -> None:
        from kanbanmate.core.transitions_defaults import TRACK_ENTRY
        cols = load_columns(
            (importlib.resources.files("kanbanmate.assets") / "columns.yml.tmpl").read_text()
        )
        for entry_key in TRACK_ENTRY.values():
            assert entry_key in cols
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/test_transitions_defaults.py -k Skiff -v`
Expected: FAIL.

- [ ] **Step 3: Add the prompt constants**

In `transitions_defaults.py`, near the other prompt constants, add `_TRIAGE_PROMPT` and `_SCOPE_PROMPT`. (Compose from the shared blocks; keep the `kanban-route` → `kanban-done` ordering and the conservative default.)

```python
_TRIAGE_PROMPT = (
    "/kanban Triage ticket {{code}} ({{codename}}) onto a fast-track lane.\n"
    + _IDENTITY_THEN_STATE
    + "You are the skiff TRIAGE stage. Classify this ticket on TWO axes and route it:\n"
    "- SIZE: trivial / small / substantial (read the ticket; take a QUICK code peek at the likely "
    "files with `rg`/`grep` to gauge effort — do NOT start implementing).\n"
    "- SENSITIVITY: read `.claude/kanban/sensitive.yml`. If the ticket's probable scope matches any "
    "sensitive path glob or keyword, OR the ticket carries a `sensitive`/listed `area:*` label → it "
    "is SENSITIVE.\n"
    "OVERRIDE: if the ticket body/labels carry an explicit `track:full|lite|express`, honour it — "
    "EXCEPT a `sensitive` match always wins and forces `full` (post a kanban-comment noting the "
    "override-down).\n"
    "DECIDE: `express` = trivial AND safe; `lite` = small AND safe; otherwise `full`. ANY doubt, any "
    "sensitivity, any failure to assess → `full` (the conservative default).\n"
    "RECORD your decision, in this order:\n"
    "1. `kanban-update-body {{code}} --set-field track <lane>` (durable; read later by the review).\n"
    "2. `kanban-route {{code}} <lane>` (the routing breadcrumb the engine consumes).\n"
    "3. `kanban-done {{code}}` (end the session; the engine moves the card to the lane entry).\n"
    "Do NOT move the card yourself, do NOT write code, do NOT open a PR.\n" + _CLEAN_STOP
)

_SCOPE_PROMPT = (
    "/kanban Scope ticket {{code}} ({{codename}}) — the LITE fast-track design+plan in one pass.\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + "You are the skiff LITE SCOPE stage (a small, safe ticket). Produce a COMPRESSED design+plan "
    "in a SINGLE pass — no separate brainstorm, no full DESIGN.md, no multi-phase plan:\n"
    "- Write a few-line scope note + a short checklist plan to "
    "`docs/features/{{codename}}/SCOPE.md` and `git add` + `git commit` it (the WIP branch carries "
    "it to the build stage).\n"
    "- Derive the codename + SemVer bump (usually patch/minor) and set them: "
    "`kanban-update-body {{code}} --set-field codename <codename>`.\n"
    + _AUTONOMY
    + "AUTONOMY: take every obvious, non-consequential decision yourself per the repo's conventions "
    "— do NOT ask the user. When a decision is genuinely ambiguous but NOT sensitive, decide, post "
    "the question + your choice + the alternative via `kanban-comment {{code}} \"…\"`, and continue.\n"
    + _GROUNDING_DISCIPLINE
    + "DONE = SCOPE.md committed + codename set. Then `kanban-done {{code}}` — the engine advances "
    "the card to Prepare feature (build).\n" + _CLEAN_STOP
)
```

- [ ] **Step 4: Rewire `DEFAULT_TRANSITIONS`**

Replace the `Backlog → Brainstorming` entry (lines ~607-620) with:

```python
    # Backlog → Triage: the skiff classifier (cheap, read-only). It records the lane (**track** +
    # route breadcrumb) and ends; the ENGINE then routes the card to the lane's entry column
    # (bin/kanban_session_end._routed_advance, advance: route).
    {
        "from": "Backlog",
        "to": "Triage",
        "profile": "triage",
        "prompt": _TRIAGE_PROMPT,
        "advance": "route",
        "permission_mode": "auto",
    },
    # Triage → Brainstorming: the FULL lane head (interactive brainstorm, unchanged). The one place
    # a human tmux-attaches to answer clarifying questions.
    {
        "from": "Triage",
        "to": "Brainstorming",
        "profile": "docs",
        "prompt": _BRAINSTORM_PROMPT,
        "advance": "auto:Spec",
        "permission_mode": "auto",
    },
    # Triage → Scope: the LITE lane head (compressed design+plan in one pass; no human gate).
    {
        "from": "Triage",
        "to": "Scope",
        "profile": "docs",
        "prompt": _SCOPE_PROMPT,
        "advance": "auto:PrepareFeature",
        "permission_mode": "auto",
    },
    # Triage → PrepareFeature: the EXPRESS lane head (no design — straight to create-branch/build;
    # design rationale lives in the PR body). create-branch runs on arrival (see the shared entry).
    {
        "from": "Triage",
        "to": "PrepareFeature",
        "profile": _PREPARE_PROFILE,          # match the existing ReadyToDev→PrepareFeature row
        "prompt": _PREPARE_PROMPT,            # the (now plan-adaptive) create-branch prompt
        "advance": "auto:InProgress",
        "permission_mode": "auto",
    },
    # Scope → PrepareFeature: the LITE lane continues into create-branch/build (engine auto-advance).
    {
        "from": "Scope",
        "to": "PrepareFeature",
        "profile": _PREPARE_PROFILE,
        "prompt": _PREPARE_PROMPT,
        "advance": "auto:InProgress",
        "permission_mode": "auto",
    },
```

> Read the existing `ReadyToDev → PrepareFeature` row to copy its exact `profile`/prompt constant names (referred to above as `_PREPARE_PROFILE` / `_PREPARE_PROMPT`). Keep that row as-is (the full lane's human-drag entry). The `Plan → ReadyToDev` no-op and all downstream rows are unchanged.

- [ ] **Step 5: Make create-branch + build prompts plan-adaptive**

Edit the create-branch prompt constant (`_PREPARE_PROMPT`) to add an adaptive preamble:

```
ADAPTIVE INPUTS: a prior stage may have left artifacts on the WIP branch.
- If `docs/features/{{codename}}/DESIGN.md` AND a plan dir exist (full lane) → use the codename + bump already set.
- If only `docs/features/{{codename}}/SCOPE.md` exists (lite lane) → use the codename already set; bump = the scope note's bump.
- If NEITHER exists (express lane) → derive the codename from the issue title (slug) and bump = patch; there is no DESIGN.md — the design rationale goes in the PR body.
```

Edit `_IMPLEMENT_PROMPT` to add, before `STOP AT PR CREATION`:

```
PLAN-ADAPTIVE: execute whatever the WIP branch carries —
- a full plan (`docs/features/{{codename}}/plan/`) → run it phase by phase;
- a SCOPE.md only → implement the checklist directly (no phase orchestration);
- neither (express) → scope the fix from the ticket, implement the minimal change, and write the design rationale (a few lines) into the PR body.
```

- [ ] **Step 6: Run tests + the round-trip + size**

Run: `pytest tests/core/test_transitions_defaults.py -v && make size`
Expected: PASS. If `transitions_defaults.py` nears the 1000-LOC ceiling, extract the prompt constants into a `core/transitions_prompts.py` module and import them (note in the commit).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(skiff): triage routing transitions + lite/express lane heads"
```

---

### Task 9: The `sensitive.yml` config

**Files:**

- Create: `src/kanbanmate/assets/sensitive.yml.tmpl` (shipped template)
- Create: `.claude/kanban/sensitive.yml` (live config; `git add -f`)
- Modify: `src/kanbanmate/cli/init.py` (copy the template into the clone at init, mirroring the columns.yml copy)
- Test: `tests/cli/test_init.py` (the template is copied into a fresh clone)

**Interfaces:**

- Produces: a versioned, operator-maintained sensitive-areas config the triage prompt reads via `cat`. No engine loader — the triage agent reads + reasons (the autonomy the operator chose).

- [ ] **Step 1: Write the template**

```yaml
# src/kanbanmate/assets/sensitive.yml.tmpl
# skiff fast-track — ANY match forces the FULL lane (triage reads this; it never fast-tracks a hit).
# Copied per-repo by `kanban init`; edit to fit the project. A missing/empty file is NOT "nothing is
# sensitive" — the triage prompt leans to `full` for anything it cannot confidently classify as safe.
paths: # globs matched against the ticket's probable scope
  - "**/auth/**"
  - "**/billing/**"
  - "src/kanbanmate/core/decide.py"
  - "src/kanbanmate/core/intent.py"
  - "src/kanbanmate/adapters/perms.py"
  - "src/kanbanmate/bin/kanban_session_end.py"
keywords: # case-insensitive substrings in the ticket text
  - security
  - credential
  - secret
  - migration
  - permission
labels: # GitHub labels that force full regardless of size
  - sensitive
  - security
```

- [ ] **Step 2: Copy it at init**

In `src/kanbanmate/cli/init.py`, mirror the `columns.yml` copy: add a `_SENSITIVE_TEMPLATE_RESOURCE = "sensitive.yml.tmpl"`, a `CLONE_SENSITIVE_RELPATH = Path(".claude") / "kanban" / "sensitive.yml"`, a reader, and a write into the clone in the same step that writes `columns.yml`.

- [ ] **Step 3: Write the live config + a test**

Copy the template content to `.claude/kanban/sensitive.yml`. Add a test asserting `kanban init` writes `sensitive.yml` into a fresh clone (mirror the existing columns.yml init test).

- [ ] **Step 4: Run tests + commit**

```bash
pytest tests/cli/test_init.py -v
git add -A && git add -f .claude/kanban/sensitive.yml
git commit -m "feat(skiff): sensitive.yml config gates the fast lanes"
```

---

### Task 10: Track-aware `pr-review`

**Files:**

- Modify: `.claude/skills/implement:pr-review/SKILL.md`
- (no unit test — validated by re-running review on a lite/express PR; verify manually)

- [ ] **Step 1: Read the track at Step 1**

Add to the skill's Step 1: read the ticket body's `**track**` field (default `full`). Set `MAX_CYCLES`: `full → 5`, `lite → 2`, `express → 1`.

- [ ] **Step 2: Scale the loop ceiling**

Replace the hard-coded `5` in §49 / the Step-5 `cycle < 5` / `CURRENT_CYCLE > 5` checks with `MAX_CYCLES`.

- [ ] **Step 3: Scale the filter + norms subset**

In Step 3: `full` filters against `DESIGN.md`; `lite` filters against `docs/features/${CODENAME}/SCOPE.md`; `express` filters against the ticket's acceptance criteria (no DESIGN.md). Pass a norms subset to `/pr-review-toolkit:review-pr`: `full` = all 8 agents; `lite` = correctness/security/test-coverage subset; `express` = `code-reviewer` + `silent-failure-hunter` only.

- [ ] **Step 4: Commit (in the `.claude/` config repo)**

```bash
# .claude/ is its own git repo (gitignored by this repo) — commit there.
git -C .claude add skills/implement:pr-review/SKILL.md
git -C .claude commit -m "feat(skiff): track-aware pr-review strictness"
```

---

### Task 11: Regenerate live config + board sync + docs

**Files:**

- Modify: `.claude/kanban/transitions.yml` (regenerate from `render_transitions_yaml`; `git add -f`)
- Modify: `docs/features/hybrid-flow/DESIGN.md` or a new `docs/features/skiff/DESIGN.md` (record the lanes); `IMPLEMENTATION.md`
- Run: the board provision/sync so the GitHub Project gains the `Triage` + `Scope` Status options

- [ ] **Step 1: Regenerate `transitions.yml`**

```bash
python -c "from kanbanmate.core.transitions_defaults import render_transitions_yaml; \
import pathlib; pathlib.Path('.claude/kanban/transitions.yml').write_text(render_transitions_yaml('LounisBou/KanbanMate'))"
```

Verify it round-trips: `python -c "from kanbanmate.core.transitions import load_transitions; load_transitions(open('.claude/kanban/transitions.yml').read()); print('ok')"`

- [ ] **Step 2: Add the Status options to the board**

The board's Status field must gain `Triage` + `Scope` options (the engine moves cards into them). Use the existing board reconcile (`Seeder.ensure_columns` via `app/board_provision.py` / the init reconcile path) against the live project. Confirm with the board `status_options` probe that both options now exist. **Do not** hand-create options in a way that loses existing option ids (the reconcile preserves them).

- [ ] **Step 3: Update DESIGN + IMPLEMENTATION**

Record the 3-lane flow, the routed-advance mechanism, and the safety properties in the design doc; add the IMPLEMENTATION.md row.

- [ ] **Step 4: Full gate**

Run: `make check` (lint + test + size) and `python -c "import kanbanmate"`.
Expected: zero lint/type errors, all tests pass, no module over 1000 LOC.

- [ ] **Step 5: Commit**

```bash
git add -A && git add -f .claude/kanban/transitions.yml docs/features/
git commit -m "chore(skiff): regenerate transitions + board sync + design delta"
```

---

### Task 12: End-to-end verification on staging

**Files:** none (verification only)

- [ ] **Step 1: Deploy to staging**

Push the branch to `staging` and deploy via the documented staging path (`scripts/deploy-staging.sh` from `~/staging/kanban-mate`). Restart the staging daemon so it loads the regenerated `transitions.yml` + the new `kanban-route` entry point (re-`pip install -e .`).

- [ ] **Step 2: Exercise each lane**

Create three throwaway tickets on the (staging) board and drag each `Backlog → Triage`. Confirm:

- a trivial-and-safe ticket → triage records `**track**: express` → engine moves it to `Prepare feature` → build → PRCI → Review (stops for human merge);
- a small-and-safe ticket → `lite` → `Scope` (SCOPE.md committed) → build → … → Review;
- a sensitive ticket (touches a `sensitive.yml` path, or labelled `sensitive`) → `full` → `Brainstorming` (full flow), even if tiny.

Verify via `kanban state --root <staging root> --project <id>` + the ticket bodies (`**track**` field) + the daemon log that each routed move fired within a few seconds (reflex) and that NO lane auto-merged.

- [ ] **Step 3: Record the result**

Note the per-lane wall-clock + any mis-classification in the PR description. Do not merge to `main` until each lane is verified live (per the operator rule: delivered ≠ merged — verify in a running build).

---

## Self-Review

**1. Spec coverage**

| Spec section                            | Task(s)                                                        |
| --------------------------------------- | -------------------------------------------------------------- |
| §3 decision 1 (auto-triage + override)  | 8 (`_TRIAGE_PROMPT`)                                           |
| §3 decision 2 (3 lanes)                 | 7, 8                                                           |
| §3 decision 3 (human merge all lanes)   | unchanged Review→Merge (Global Constraints; verified Task 12)  |
| §3 decision 4 (sensitive config + read) | 9, 8                                                           |
| §3 decision 5 (visible Triage column)   | 7                                                              |
| §3 decision 6 (comment-and-continue)    | 8 (`_SCOPE_PROMPT` autonomy block)                             |
| §6 triage stage                         | 3, 8, 9                                                        |
| §7 routed-advance engine                | 1, 2, 3, 4                                                     |
| §8 lane heads                           | 8                                                              |
| §9 adaptive tail prompts                | 8 (Step 5)                                                     |
| §10 track-aware review                  | 6, 10                                                          |
| §12 safety invariants                   | 5 (deny inherited), 4 (whitelist guard), Global Constraints    |
| §13 scope of changes                    | all                                                            |
| §14 edge cases                          | 1 (TTL/corrupt), 4 (unknown lane / rate-limit / unwhitelisted) |
| §15 testing                             | tests in 1–8                                                   |
| Board Status options                    | 11 Step 2                                                      |

No gaps.

**2. Placeholder scan:** `_PREPARE_PROFILE` / `_PREPARE_PROMPT` in Task 8 are explicitly flagged as "read the existing ReadyToDev→PrepareFeature row and copy its real constant names" — not a silent placeholder. All test/impl code blocks are complete.

**3. Type consistency:** `record_agent_route(issue, lane, *, now)` / `recent_agent_route(issue, *, now) -> str` are used identically in Tasks 1, 3, 4. `route_entry_column(lane) -> str | None` consistent in Tasks 2, 4. `RoutedAdvanceResult` values (`"routed"`/`"stopped"`/`"parked_blocked"`) map onto the existing `advance_result` sticky logic in Task 4 Step 4. `TRACK_ENTRY` keys (`full`/`lite`/`express`) == `TRACK_VALUES` == the `kanban-route` lane arg == the `**track**` field values — one closed vocabulary throughout.
