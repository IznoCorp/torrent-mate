"""Thin MCP tool bodies — read serializers + pinned/PAUSE-guarded write routers (conduit §6).

Each tool body is THIN: pure routing plus the two safety guards, no domain logic and no direct
GitHub writes. The write tools route through the IDENTICAL ``core`` / ``app`` / port functions the
``kanban-*`` bins call (one audited write path, no duplicated GitHub logic):

* every write tool FIRST calls :func:`kanbanmate.mcp.pin.pin_violation` and returns the refusal —
  performing ZERO I/O — on a pin mismatch (DESIGN §7);
* then checks ``store.kill_switch_active()`` (``ports/store.py:491``) and refuses under PAUSE;
* then performs the single routed action.

There is NO ``merge`` tool — merge stays human / merge-agent only (DESIGN §6, locked decision 6).
The ``columns`` model and ``pinned``/``now`` values are PASSED IN by the caller (``server.py``,
Phase 3) — this module never constructs the wiring.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.core.body_edit import (
    append_section,
    set_field,
    validate_roadmap_matches_title,
)
from kanbanmate.core.columns import resolve_target_column
from kanbanmate.core.domain import Column
from kanbanmate.core.transitions import TransitionConfig
from kanbanmate.mcp import resources
from kanbanmate.mcp.pin import pin_violation
from kanbanmate.ports.board import BoardReader, BoardWriter, Seeder
from kanbanmate.ports.store import StateStore

# ---------------------------------------------------------------------------
# Read tools (NOT pinned) — mirror the resources (some clients invoke tools
# more reliably than they read resources; DESIGN §6.1 / open question (a)).
# ---------------------------------------------------------------------------


def get_board(board_reader: BoardReader, store: StateStore, *, root: Path) -> dict[str, object]:
    """Read tool: the unified board read-model (same as ``kanban://board``)."""
    return resources.board(board_reader, store, root=root)


def get_ticket(board_reader: BoardReader, issue: int) -> dict[str, object]:
    """Read tool: one ticket's rich context (same as ``kanban://ticket/{n}``)."""
    return resources.ticket(board_reader, issue)


def get_state(board_reader: BoardReader, store: StateStore, *, root: Path) -> dict[str, object]:
    """Read tool: alias of :func:`get_board` (the unified read model)."""
    return get_board(board_reader, store, root=root)


# ---------------------------------------------------------------------------
# Write tools (PINNED + PAUSE-guarded). Each returns a refusal string on a
# guard trip (performing zero I/O) or a confirmation string on success.
# ---------------------------------------------------------------------------


def _guard(issue: int, pinned: int, store: StateStore) -> str | None:
    """Return a refusal string when a write must be refused (pin mismatch or PAUSE), else ``None``.

    Runs the two inherited safety invariants in order, BEFORE any I/O (DESIGN §7): the pure
    :func:`~kanbanmate.mcp.pin.pin_violation` pin check first (zero I/O on mismatch), then the
    ``store.kill_switch_active()`` PAUSE floor.

    Args:
        issue: The issue the write tool was asked to act on.
        pinned: The server's pinned issue (the agent's own ticket).
        store: The store whose PAUSE kill-switch to consult.

    Returns:
        A refusal message when the write must be refused; ``None`` when it may proceed.
    """
    violation = pin_violation(issue, pinned)
    if violation is not None:
        return violation
    if store.kill_switch_active():
        return f"refusing to write to #{issue}: the PAUSE kill-switch is engaged"
    return None


def comment(
    board_writer: BoardWriter,
    store: StateStore,
    *,
    issue: int,
    pinned: int,
    body: str,
) -> str:
    """Post a comment on the agent's ticket (parity ``bin/kanban_comment.py:207``).

    Routes through ``board_writer.comment(issue, body)`` (``ports/board.py:113``) after the
    pin + PAUSE guards.
    """
    refusal = _guard(issue, pinned, store)
    if refusal is not None:
        return refusal
    board_writer.comment(issue, body)
    return f"commented on #{issue}"


def progress(
    board_writer: BoardWriter,
    store: StateStore,
    *,
    issue: int,
    pinned: int,
    line: str,
    stage: str | None = None,
    now: float | None = None,
) -> str:
    """Append a progress line to the stage sticky, or a free-form note (parity ``kanban_progress``).

    With a ``stage`` key, routes through
    ``app.stage_signal.upsert_stage_comment(writer, issue, stage, append=line, now=…)``
    (``app/stage_signal.py:48``). Without a stage, falls back to a stamped free-form
    ``board_writer.comment(issue, stamped)`` (parity ``bin/kanban_progress.py:200,222``). Guarded
    first by pin + PAUSE.
    """
    refusal = _guard(issue, pinned, store)
    if refusal is not None:
        return refusal
    when = now if now is not None else time.time()
    if stage is not None:
        upsert_stage_comment(board_writer, issue, stage, append=line, now=when)
        return f"progress on #{issue} [{stage}]: {line}"
    # Free-form fallback: a compact UTC-stamped markdown list item (mirrors kanban_progress._timestamped).
    stamp = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(when))
    board_writer.comment(issue, f"- {stamp} {line}")
    return f"progress on #{issue} (note): {line}"


def move(
    store: StateStore,
    columns: dict[str, Column],
    transitions: TransitionConfig,
    *,
    issue: int,
    pinned: int,
    to_col: str,
    from_col: str | None = None,
    now: float | None = None,
) -> str:
    """Enqueue a column-move intent for the daemon to drain (parity ``bin/kanban_move.py:233-246``).

    Resolves ``to_col`` (a key OR a display name) to its :class:`~kanbanmate.core.domain.Column`
    via ``core.columns.resolve_target_column`` (relocated, Phase 1), mirrors the bin's UX-only
    pair-aware anti-loop pre-flight (``bin/kanban_move.py:209-230`` — refuse when ``(from_col,
    to_col)`` is itself a prompt-bearing launch transition), then enqueues the intent
    (``store.enqueue_intent``) + nudges the daemon (``store.nudge_daemon``). The payload carries the
    column KEY (the daemon validates the key). The AUTHORITATIVE gate stays the daemon's
    ``validate_intent`` — this shell does not re-implement R1 / the Merge deny / the re-fire guard.

    Guarded first by pin + PAUSE.
    """
    refusal = _guard(issue, pinned, store)
    if refusal is not None:
        return refusal
    # resolve_target_column raises KeyError (with a "known columns: …" message) on an unknown target.
    # Catch it and surface that message as a friendly refusal string — keeping the zero-I/O,
    # actionable-feedback contract every other guard uses, instead of leaking the bare KeyError repr.
    try:
        column = resolve_target_column(columns, to_col)
    except KeyError as exc:
        return f"refusing to move #{issue}: {exc.args[0]}"
    # PAIR-AWARE pre-flight anti-loop guard (UX only — the daemon's validate_intent is authoritative).
    # Refuse ONLY when the (from, to) pair is ITSELF a prompt-bearing launch transition (a genuine
    # launch re-fire), never every move whose destination merely happens to be some launch target.
    if from_col:
        pair = transitions.get(from_col, column.key)
        if pair is not None and pair.prompt:
            return (
                f"refusing to move #{issue} {from_col!r}->{column.name!r} (anti-loop): "
                f"that pair is a prompt-bearing launch transition; an agent may not re-fire a launch"
            )
    intent_id = uuid.uuid4().hex[:12]
    store.enqueue_intent(
        intent_id,
        {
            "kind": "move",
            "issue": issue,
            "args": {"to_col": column.key},  # column KEY, not name (the daemon validates the key)
            "requested_at": now if now is not None else time.time(),
            "caller": "agent",  # ADVISORY only — the daemon derives authority from its bookkeeping
        },
    )
    # CONVENTION: every enqueue_intent is paired with nudge_daemon so the daemon drains near-instantly.
    store.nudge_daemon()
    return f"enqueued move of #{issue} -> {column.name} (intent {intent_id})"


def done(store: StateStore, *, issue: int, pinned: int, now: float | None = None) -> str:
    """Drop the agent's done breadcrumb (parity ``bin/kanban_done.py:66``).

    Routes through ``store.record_agent_done(issue, now=…)`` (``ports/store.py:413``) after the
    pin + PAUSE guards.
    """
    refusal = _guard(issue, pinned, store)
    if refusal is not None:
        return refusal
    store.record_agent_done(issue, now=now if now is not None else time.time())
    return f"done #{issue}: the agent signalled completion; the daemon will end the session"


def update_body(
    seeder: Seeder,
    store: StateStore,
    *,
    issue: int,
    pinned: int,
    set_field_kv: tuple[str, str] | None = None,
    append_section_ht: tuple[str, str] | None = None,
) -> str:
    """Coherence-gated issue-body edit (parity ``bin/kanban_update_body.py:205-227``).

    Resolves the issue's node id via ``seeder.fetch_issue(issue)`` (``ports/board.py:306``), applies
    EXACTLY ONE pure transform — ``core.body_edit.set_field(body, key, value)`` (``core/body_edit.py:66``)
    OR ``append_section(body, heading, text)`` (``core/body_edit.py:103``) — then runs the post-write
    coherence gate ``validate_roadmap_matches_title(new_body, title)`` (``core/body_edit.py:258``). A
    non-``None`` message means the ticket↔roadmap binding would desync: the tool REFUSES and surfaces
    that message, NEVER calling ``update_issue_body``. On ``None`` it patches via
    ``seeder.update_issue_body(node_id, new_body)`` (``ports/board.py:289``).

    Guarded first by pin + PAUSE. Exactly one of ``set_field_kv`` / ``append_section_ht`` must be set.
    """
    refusal = _guard(issue, pinned, store)
    if refusal is not None:
        return refusal
    if (set_field_kv is None) == (append_section_ht is None):
        return f"refusing to edit #{issue}: pass exactly one of set_field or append_section"
    issue_ref = seeder.fetch_issue(issue)
    if set_field_kv is not None:
        key, value = set_field_kv
        new_body = set_field(issue_ref.body, key, value)
    else:
        assert append_section_ht is not None  # narrows mypy; the XOR check above guarantees it
        heading, text = append_section_ht
        new_body = append_section(issue_ref.body, heading, text)
    coherence_error = validate_roadmap_matches_title(new_body, issue_ref.title)
    if coherence_error is not None:
        return f"refusing to edit #{issue}: {coherence_error}"
    if not issue_ref.node_id:
        return f"refusing to edit #{issue}: could not resolve a node id"
    seeder.update_issue_body(issue_ref.node_id, new_body)
    return f"updated body of #{issue}"


def update_main(
    store: StateStore,
    *,
    base_clone: str | Path,
    dev_repo: str | Path,
) -> str:
    """Post-merge ``main`` refresh of the base/dev clones (parity ``bin/kanban_update_main``).

    NOT pinned and takes no issue (it has no board effect), so the pin guard does not apply — but the
    PAUSE kill-switch floor is unconditional for every write tool (DESIGN §7): the operator's
    emergency stop must halt the WHOLE write surface, this git-mutating tool included. So it checks
    ``store.kill_switch_active()`` first and refuses (zero git I/O) when PAUSE is engaged, then routes
    through the relocated git-sync adapter (Phase 1): ``adapters.workspace.base_sync.fetch_base(
    base_clone)`` then ``ff_dev_clone(dev_repo)``. The clone paths are RESOLVED SERVER-SIDE and passed
    in by the caller (``server.main`` reads them from the registry via
    ``cli.init.resolve_clone_paths``) — the MCP client supplies NO paths (DESIGN §6 / §7: zero agent
    input to a write tool).

    Args:
        store: The store whose PAUSE kill-switch to consult before any git I/O.
        base_clone: The base/bare clone to fetch ``origin/main`` into.
        dev_repo: The operator's dev clone to best-effort fast-forward on ``main``.

    Returns:
        A confirmation string, or a PAUSE refusal string (performing zero git I/O).
    """
    if store.kill_switch_active():
        return "refusing to refresh main: the PAUSE kill-switch is engaged"
    # Local import: keep the adapters edge function-local so the read serializers stay import-cheap.
    from kanbanmate.adapters.workspace.base_sync import fetch_base, ff_dev_clone

    fetch_base(base_clone)
    ff_dev_clone(dev_repo)
    return "refreshed main: fetched origin/main into the base clone, fast-forwarded the dev clone"
