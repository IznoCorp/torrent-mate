"""Drain the board-mutation intent queue — the daemon-side executor (cockpit PR2).

This is the tick's intent step (4c, after ``drain_queue`` and before ``report_status``): the daemon is
the **sole** board writer for intents, so an operator/agent enqueues an
:class:`~kanbanmate.core.intent.Intent` and the daemon executes it here. The step is **wholly
fail-soft** — it never raises into the tick — and each intent is processed under its own try/except so
one bad intent never blocks the rest.

Load-bearing invariants (from the adversarial design review):

* **Authority is DERIVED here, never trusted from the intent.** An intent whose issue is a
  daemon-tracked in-flight agent ticket (``running``) is ``agent``-authority (bridled, R1-bound to its
  own issue); otherwise ``operator`` (broad). The intent's ``caller`` field is advisory only.
* **Ordering:** intents are executed in ``requested_at`` order; a second intent for the same issue in
  one drain is DEFERRED (left pending) so it runs on the next tick against fresh state — no
  last-writer-wins clobber.
* **Optimistic concurrency:** a move re-reads the card's CURRENT column from the snapshot; if it is
  already in the destination the move is a no-op ``done`` (idempotent → crash-safe re-drain).
* **Baseline advance:** a successful move writes ``next_columns[item_id] = to_col`` so the next diff
  does NOT re-fire (and re-launch) the move — exactly as ``process_transition`` advances the baseline.
* **PAUSE matrix:** under the kill-switch, agent-authority intents are HELD (left pending, resume on
  un-pause); operator intents still execute (the operator is who acts during a pause).

v1 executes only ``move`` (operator-only live; the agent path is validated + tested ahead but agents
do not enqueue yet). Ticket/pill CRUD kinds are rejected here until PR3 wires their executors.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kanbanmate.core.intent import Intent, IntentRejected, validate_intent
from kanbanmate.core.status_update import STATUS_VALUES

if TYPE_CHECKING:  # pragma: no cover - type-only imports (no runtime cycle)
    from kanbanmate.app.actions import Deps
    from kanbanmate.app.tick import TickConfig
    from kanbanmate.core.domain import BoardSnapshot, Column, Ticket
    from kanbanmate.core.intent import Authority
    from kanbanmate.core.transitions import TransitionConfig
    from kanbanmate.ports.board import Seeder
    from kanbanmate.ports.store import TicketState

logger = logging.getLogger(__name__)

# Result-file TTL (cockpit DESIGN §10 Result GC): a ``<id>.result.json`` lingers this long after it
# is written so a CLI ``--wait`` (10s poll cadence) has ample time to read it, then it is GC'd. One
# hour is generous vs the wait cadence while keeping ``intents/`` bounded.
_RESULT_TTL_SECONDS = 3600.0


def drain_intents(
    deps: Deps,
    config: TickConfig,
    *,
    snapshot: BoardSnapshot | None,
    next_columns: dict[str, str],
    running: tuple[TicketState, ...],
    status_events: list[tuple[str, int | None, str]],
    now: float,
    kill_switch: bool,
) -> None:
    """Execute the pending board-mutation intents (the tick's fail-soft intent step).

    Wholly fail-soft: the entire body is wrapped so ANY exception is logged and swallowed — it must
    never raise into :func:`kanbanmate.app.tick.tick`. Mutates ``next_columns`` (baseline advance) and
    appends to ``status_events`` (dashboard ring) in place.

    Args:
        deps: The injected adapter bundle (``store`` / ``board_writer`` / ``board_reader``).
        config: The per-tick policy (``transitions`` / ``columns`` feed validation).
        snapshot: The tick's board snapshot, or ``None`` (a fresh one is fetched when intents exist,
            since resolving an arbitrary issue → ``item_id`` + current column needs the board).
        next_columns: The in-memory diff baseline (mutated on a successful move).
        running: The daemon's in-flight tickets (its launch bookkeeping → agent authority).
        status_events: This tick's dashboard event ring (appended to).
        now: The tick's wall-clock time.
        kill_switch: Whether ``~/.kanban/PAUSE`` is engaged (the PAUSE matrix).
    """
    try:
        # Result GC (cockpit DESIGN §10): TTL-expire stale ``<id>.result.json`` files so ``intents/``
        # never grows unbounded. Runs FIRST — even when no intents are pending — because results
        # outlive their pending markers (the CLI ``--wait`` reads them after the drain cleared the
        # pending file). Fail-soft (the store method swallows per-file errors; the whole drain is
        # wrapped too).
        deps.store.gc_intent_results(now=now, ttl=_RESULT_TTL_SECONDS)
        pending = deps.store.list_pending_intents()
        if not pending:
            return
        transitions = config.transitions
        if transitions is None:
            # No whitelist → moves cannot be validated; skip (the wiring always supplies one in
            # production, so this only guards a misconfigured/test path).
            return
        # Resolving an arbitrary issue → (item_id, current column) needs the board; the probe is
        # unchanged at enqueue time (the move IS the change), so fetch a snapshot when absent.
        snap = snapshot if snapshot is not None else deps.board_reader.snapshot()
        by_issue = {t.issue_number: t for t in snap.tickets if t.issue_number is not None}
        running_issues = {st.issue_number for st in running}

        # Load every pending intent; order by requested_at (tie-break by id) — NOT glob order — so
        # same-issue intents execute oldest-first (the rest are deferred below).
        loaded = [(iid, deps.store.load_intent(iid)) for iid in pending]
        loaded.sort(key=lambda pair: (_requested_at(pair[1]), pair[0]))

        processed_issues: set[int] = set()
        for intent_id, payload in loaded:
            try:
                _process_intent(
                    deps,
                    transitions=transitions,
                    columns=config.columns,
                    intent_id=intent_id,
                    payload=payload,
                    by_issue=by_issue,
                    running_issues=running_issues,
                    next_columns=next_columns,
                    status_events=status_events,
                    processed_issues=processed_issues,
                    kill_switch=kill_switch,
                )
            except Exception:  # noqa: BLE001 — one bad intent must never block the others / the tick
                logger.exception("intent %s raised; rejecting it", intent_id)
                _result(deps, intent_id, "rejected", "internal error processing intent")
                deps.store.clear_intent(intent_id)
    except Exception:  # noqa: BLE001 — the whole step is observability-grade: NEVER raise into the tick
        logger.warning("drain_intents failed; intents will retry next tick", exc_info=True)


def _process_intent(
    deps: Deps,
    *,
    transitions: TransitionConfig,
    columns: dict[str, Column],
    intent_id: str,
    payload: dict[str, object] | None,
    by_issue: dict[int, Ticket],
    running_issues: set[int],
    next_columns: dict[str, str],
    status_events: list[tuple[str, int | None, str]],
    processed_issues: set[int],
    kill_switch: bool,
) -> None:
    """Validate + execute ONE intent: common gates then per-kind dispatch (caller isolates)."""
    intent = _parse_intent(payload)
    if intent is None:
        # Poison/unparseable marker — reject + clear so the caller's --wait unblocks (drain.py pattern).
        _result(deps, intent_id, "rejected", "intent file corrupt/unparseable")
        deps.store.clear_intent(intent_id)
        return

    # Same-issue ordering: only the earliest intent for an issue runs this drain; defer the rest
    # (leave them PENDING) so they run next tick against fresh state — no clobber.
    if intent.issue is not None and intent.issue in processed_issues:
        _result(deps, intent_id, "deferred", "another intent for this issue ran first this tick")
        return

    # Authority is DERIVED from the daemon's bookkeeping, NOT the intent's caller (§5): an issue with
    # a live agent the daemon launched is agent-authority (bridled, R1-bound to its own issue).
    authority: Authority = "agent" if (intent.issue in running_issues) else "operator"

    # PAUSE matrix: hold agent-authority intents (resume on un-pause); operators still act.
    if kill_switch and authority == "agent":
        _result(deps, intent_id, "held", "board paused (PAUSE); agent intent held until resume")
        return

    if intent.kind == "move":
        _execute_move(
            deps,
            intent,
            intent_id=intent_id,
            authority=authority,
            transitions=transitions,
            columns=columns,
            by_issue=by_issue,
            next_columns=next_columns,
            status_events=status_events,
            processed_issues=processed_issues,
        )
    elif intent.kind == "ticket_create":
        _execute_ticket_create(
            deps,
            intent,
            intent_id=intent_id,
            authority=authority,
            transitions=transitions,
            columns=columns,
            status_events=status_events,
        )
    elif intent.kind == "ticket_edit":
        _execute_ticket_edit(
            deps,
            intent,
            intent_id=intent_id,
            authority=authority,
            transitions=transitions,
            columns=columns,
            status_events=status_events,
        )
    elif intent.kind == "ticket_close":
        _execute_ticket_close(
            deps,
            intent,
            intent_id=intent_id,
            authority=authority,
            transitions=transitions,
            columns=columns,
            status_events=status_events,
        )
    elif intent.kind in ("pill_set_health", "pill_note", "pill_clear"):
        _execute_pill(
            deps,
            intent,
            intent_id=intent_id,
            authority=authority,
            transitions=transitions,
            columns=columns,
            status_events=status_events,
        )
    else:
        _result(
            deps, intent_id, "rejected", f"intent kind {intent.kind!r} not executed in this version"
        )
        deps.store.clear_intent(intent_id)


def _execute_move(
    deps: Deps,
    intent: Intent,
    *,
    intent_id: str,
    authority: Authority,
    transitions: TransitionConfig,
    columns: dict[str, Column],
    by_issue: dict[int, Ticket],
    next_columns: dict[str, str],
    status_events: list[tuple[str, int | None, str]],
    processed_issues: set[int],
) -> None:
    """Execute a ``move`` intent: validate (re-fire/Merge/R1 guards) then move with idempotence."""
    ticket = by_issue.get(intent.issue) if intent.issue is not None else None
    if ticket is None:
        _result(deps, intent_id, "rejected", f"issue #{intent.issue} not on the board")
        deps.store.clear_intent(intent_id)
        return
    from_col = ticket.column_key
    item_id = ticket.item_id

    try:
        validate_intent(
            intent,
            authority=authority,
            transitions=transitions,
            columns=columns,
            from_col=from_col,
            launching_issue=intent.issue,
        )
    except IntentRejected as exc:
        _result(deps, intent_id, "rejected", str(exc))
        deps.store.clear_intent(intent_id)
        return

    to_col = str(intent.args["to_col"])
    if intent.issue is not None:
        processed_issues.add(intent.issue)

    # Optimistic concurrency / idempotence: if the card is ALREADY in the destination (a fresher
    # move, or a crash-resume after the move already landed), this is a no-op success.
    if from_col == to_col:
        next_columns[item_id] = to_col
        _result(deps, intent_id, "done", f"already in {to_col}")
        deps.store.clear_intent(intent_id)
        return

    # Crash-safety breadcrumb: mark claimed BEFORE the mutation, so a re-drain after a crash sees the
    # move may have landed and the idempotent from_col==to_col check above resolves it.
    _result(deps, intent_id, "claimed", f"moving {from_col}->{to_col}")
    deps.board_writer.move_card(item_id, to_col)
    # Baseline advance: record the move so the next diff does NOT re-fire/relaunch it.
    next_columns[item_id] = to_col
    status_events.append(("auto", intent.issue, f"moved → {to_col}"))
    _result(deps, intent_id, "done", f"moved {from_col}->{to_col}")
    deps.store.clear_intent(intent_id)


def _execute_ticket_create(
    deps: Deps,
    intent: Intent,
    *,
    intent_id: str,
    authority: Authority,
    transitions: TransitionConfig,
    columns: dict[str, Column],
    status_events: list[tuple[str, int | None, str]],
) -> None:
    """Execute a ``ticket_create`` intent: idempotent multi-step create + add-to-project + (move).

    Operator-only (validate rejects agents). The three GitHub mutations (create_issue →
    add_to_project → optional move) are NOT atomic, so a per-step checkpoint is persisted back into
    the intent (``_created_number`` / ``_node_id`` / ``_item_id``) BEFORE the terminal result: a crash
    mid-way re-drains and RESUMES from the checkpoint rather than re-creating a duplicate issue.
    """
    try:
        validate_intent(
            intent,
            authority=authority,
            transitions=transitions,
            columns=columns,
            launching_issue=intent.issue,
        )
    except IntentRejected as exc:
        _result(deps, intent_id, "rejected", str(exc))
        deps.store.clear_intent(intent_id)
        return

    args = intent.args
    title = str(args.get("title") or "")
    if not title:
        _result(deps, intent_id, "rejected", "ticket_create requires a non-empty title")
        deps.store.clear_intent(intent_id)
        return
    body = str(args.get("body") or "")
    raw_labels = args.get("labels")
    labels = [str(x) for x in raw_labels] if isinstance(raw_labels, list) else []
    initial_col = args.get("column")

    # create_issue / add_to_project live on the Seeder side of the GitHub client (the same instance
    # backing board_writer in production). A wiring without a seeder cannot create tickets.
    seeder = deps.seeder
    if seeder is None:
        _result(deps, intent_id, "rejected", "ticket_create unavailable: no seeder configured")
        deps.store.clear_intent(intent_id)
        return

    # Resume from the checkpoint if a prior partial run got this far.
    number = args.get("_created_number")
    node_id = args.get("_node_id")
    item_id = args.get("_item_id")

    # Step 1 — create the issue (checkpoint immediately so a crash never re-creates it).
    if not isinstance(number, int) or not isinstance(node_id, str):
        _result(deps, intent_id, "claimed", "creating issue")
        node_id, number = seeder.create_issue(deps.repo, title, body, labels)
        intent = _checkpoint(deps, intent_id, intent, _created_number=number, _node_id=node_id)

    # Step 2 — add it to the project (checkpoint the item id).
    if not isinstance(item_id, str):
        item_id = seeder.add_to_project(deps.project_id, node_id)
        intent = _checkpoint(deps, intent_id, intent, _item_id=item_id)

    # Step 3 — move it to the requested initial column (validated non-triggering above).
    if isinstance(initial_col, str) and initial_col:
        deps.board_writer.move_card(item_id, initial_col)

    status_events.append(("auto", number, f"created #{number}"))
    _result(deps, intent_id, "done", f"created #{number}")
    deps.store.clear_intent(intent_id)


def _execute_ticket_edit(
    deps: Deps,
    intent: Intent,
    *,
    intent_id: str,
    authority: Authority,
    transitions: TransitionConfig,
    columns: dict[str, Column],
    status_events: list[tuple[str, int | None, str]],
) -> None:
    """Execute a ``ticket_edit`` intent: replace the issue body (operator-only). Idempotent."""
    try:
        validate_intent(
            intent,
            authority=authority,
            transitions=transitions,
            columns=columns,
            launching_issue=intent.issue,
        )
    except IntentRejected as exc:
        _result(deps, intent_id, "rejected", str(exc))
        deps.store.clear_intent(intent_id)
        return

    seeder = deps.seeder
    body = intent.args.get("body")
    if intent.issue is None or not isinstance(body, str):
        _result(deps, intent_id, "rejected", "ticket_edit requires an issue and a body")
        deps.store.clear_intent(intent_id)
        return
    if seeder is None:
        _result(deps, intent_id, "rejected", "ticket_edit unavailable: no seeder configured")
        deps.store.clear_intent(intent_id)
        return

    node_id = _resolve_node_id(seeder, intent.issue)
    if node_id is None:
        _result(deps, intent_id, "rejected", f"issue #{intent.issue} not found")
        deps.store.clear_intent(intent_id)
        return

    _result(deps, intent_id, "claimed", "editing body")
    seeder.update_issue_body(node_id, body)
    status_events.append(("auto", intent.issue, "edited body"))
    _result(deps, intent_id, "done", f"edited #{intent.issue} body")
    deps.store.clear_intent(intent_id)


def _execute_ticket_close(
    deps: Deps,
    intent: Intent,
    *,
    intent_id: str,
    authority: Authority,
    transitions: TransitionConfig,
    columns: dict[str, Column],
    status_events: list[tuple[str, int | None, str]],
) -> None:
    """Execute a ``ticket_close`` intent: close the issue (operator-only). Idempotent on GitHub."""
    try:
        validate_intent(
            intent,
            authority=authority,
            transitions=transitions,
            columns=columns,
            launching_issue=intent.issue,
        )
    except IntentRejected as exc:
        _result(deps, intent_id, "rejected", str(exc))
        deps.store.clear_intent(intent_id)
        return

    seeder = deps.seeder
    if intent.issue is None:
        _result(deps, intent_id, "rejected", "ticket_close requires an issue")
        deps.store.clear_intent(intent_id)
        return
    if seeder is None:
        _result(deps, intent_id, "rejected", "ticket_close unavailable: no seeder configured")
        deps.store.clear_intent(intent_id)
        return

    node_id = _resolve_node_id(seeder, intent.issue)
    if node_id is None:
        _result(deps, intent_id, "rejected", f"issue #{intent.issue} not found")
        deps.store.clear_intent(intent_id)
        return

    _result(deps, intent_id, "claimed", "closing issue")
    seeder.close_issue(node_id)
    status_events.append(("teardown", intent.issue, "closed"))
    _result(deps, intent_id, "done", f"closed #{intent.issue}")
    deps.store.clear_intent(intent_id)


def _execute_pill(
    deps: Deps,
    intent: Intent,
    *,
    intent_id: str,
    authority: Authority,
    transitions: TransitionConfig,
    columns: dict[str, Column],
    status_events: list[tuple[str, int | None, str]],
) -> None:
    """Execute a ``pill_*`` intent: set/clear the OPERATOR pill override (operator-only).

    These write the override markers only — the daemon's ``report_status`` (the next tick step) reads
    them and re-renders, so the GitHub pill moves via the existing re-create-on-enum-change path.
    """
    try:
        validate_intent(
            intent,
            authority=authority,
            transitions=transitions,
            columns=columns,
            launching_issue=intent.issue,
        )
    except IntentRejected as exc:
        _result(deps, intent_id, "rejected", str(exc))
        deps.store.clear_intent(intent_id)
        return

    if intent.kind == "pill_set_health":
        enum = intent.args.get("enum")
        if not isinstance(enum, str) or enum not in STATUS_VALUES:
            _result(deps, intent_id, "rejected", f"unknown health enum {enum!r}")
            deps.store.clear_intent(intent_id)
            return
        deps.store.set_status_override_enum(enum)
        note = intent.args.get("note")
        if isinstance(note, str) and note:
            deps.store.set_status_override_note(note)
        status_events.append(("auto", None, f"pill → {enum} (operator)"))
        _result(deps, intent_id, "done", f"pill forced to {enum}")
    elif intent.kind == "pill_note":
        text = intent.args.get("text")
        deps.store.set_status_override_note(str(text) if text is not None else None)
        _result(deps, intent_id, "done", "operator note set")
    else:  # pill_clear
        deps.store.set_status_override_enum(None)
        deps.store.set_status_override_note(None)
        status_events.append(("auto", None, "pill override cleared"))
        _result(deps, intent_id, "done", "pill override cleared")
    deps.store.clear_intent(intent_id)


def _resolve_node_id(seeder: Seeder, issue: int) -> str | None:
    """Resolve an issue NUMBER to its global node id via ``fetch_issue``, or ``None`` on failure."""
    try:
        return seeder.fetch_issue(issue).node_id
    except Exception:  # noqa: BLE001 — a lookup failure → a clean rejection, never a crash
        logger.warning("intent: fetch_issue(#%s) failed", issue, exc_info=True)
        return None


def _checkpoint(deps: Deps, intent_id: str, intent: Intent, **extra: object) -> Intent:
    """Persist a partial-progress checkpoint into the intent + return the updated in-memory Intent.

    Re-enqueues the intent file with ``extra`` merged into its args so a crash-resume reads the
    progress (and skips already-completed sub-steps); returns the updated :class:`Intent` so the
    current run continues with the merged args.
    """
    from dataclasses import replace

    merged = {**intent.args, **extra}
    updated = replace(intent, args=merged)
    deps.store.enqueue_intent(
        intent_id,
        {
            "kind": updated.kind,
            "issue": updated.issue,
            "args": merged,
            "requested_at": updated.requested_at,
            "caller": updated.caller,
        },
    )
    return updated


def _parse_intent(payload: dict[str, object] | None) -> Intent | None:
    """Coerce a persisted intent payload into an :class:`Intent`, or ``None`` when unparseable."""
    if not isinstance(payload, dict):
        return None
    kind = payload.get("kind")
    if not isinstance(kind, str):
        return None
    raw_issue = payload.get("issue")
    issue = raw_issue if isinstance(raw_issue, int) else None
    raw_args = payload.get("args")
    args = raw_args if isinstance(raw_args, dict) else {}
    return Intent(
        kind=kind,
        issue=issue,
        args=args,
        requested_at=_requested_at(payload),
        caller=str(payload.get("caller", "operator")),
    )


def _requested_at(payload: dict[str, object] | None) -> float:
    """Return the intent's ``requested_at`` as a float (0.0 when absent/odd — orders such first)."""
    if isinstance(payload, dict):
        raw = payload.get("requested_at")
        if isinstance(raw, (int, float)):
            return float(raw)
    return 0.0


def _result(deps: Deps, intent_id: str, state: str, detail: str = "") -> None:
    """Persist an intent's (interim or terminal) result for the CLI ``--wait`` to poll."""
    deps.store.save_intent_result(
        intent_id, {"intent_id": intent_id, "state": state, "detail": detail}
    )
