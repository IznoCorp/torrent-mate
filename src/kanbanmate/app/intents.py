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

``move`` executes for BOTH authorities: the operator path (``kanban move``) and — since 0.4.0 — the
agent path (``kanban-move`` now ENQUEUES a ``move`` intent rather than writing the board directly, so
this drain is the single audited write path). Authority is DERIVED here from the running set
(``intent.issue in running_issues`` → ``agent``), never from the spoofable ``caller`` field, so an
agent's own in-flight ticket is bridled (R1 / Merge deny / re-fire) while an operator move is broad.
Ticket/pill CRUD kinds are validated + tested ahead but rejected here until PR3 wires their executors.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from pathlib import Path
from typing import TYPE_CHECKING

from kanbanmate.core.columns import resolve_column
from kanbanmate.core.intent import Intent, IntentRejected, validate_intent
from kanbanmate.core.profiles import SAFE_LAUNCH_PROFILES
from kanbanmate.core.status_update import STATUS_VALUES

if TYPE_CHECKING:  # pragma: no cover - type-only imports (no runtime cycle)
    from kanbanmate.adapters.github.types import IssueRef
    from kanbanmate.app.actions import Deps
    from kanbanmate.app.tick import TickConfig
    from kanbanmate.core.domain import BoardSnapshot, Column, Ticket
    from kanbanmate.core.intent import Authority
    from kanbanmate.core.transitions import TransitionConfig
    from kanbanmate.ports.board import Seeder
    from kanbanmate.ports.store import TicketState

logger = logging.getLogger(__name__)

# The canonical default runtime root (mirrors ``cli.app._DEFAULT_ROOT`` / ``actions._DEFAULT_KANBAN_ROOT``)
# used to locate the launch-authorization secret when the daemon runs the DEFAULT root (empty
# ``Deps.kanban_root``). The launch secret lives at ``<root>/launch_secret`` and is shared between the
# daemon (this executor) and the config-UI process (the sole legitimate ``launch`` producer).
_DEFAULT_KANBAN_ROOT = Path("~/.kanban/").expanduser()

# Filename of the launch-authorization secret under the runtime root (0600). See ``launch_auth_token``.
LAUNCH_SECRET_FILENAME = "launch_secret"

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
                    concurrency_cap=config.concurrency_cap,
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
    concurrency_cap: int,
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
    elif intent.kind == "launch":
        _execute_launch(
            deps,
            intent,
            intent_id=intent_id,
            authority=authority,
            transitions=transitions,
            columns=columns,
            by_issue=by_issue,
            running_issues=running_issues,
            status_events=status_events,
            processed_issues=processed_issues,
            concurrency_cap=concurrency_cap,
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

    # Resolve the intent destination to its Column. ``to_col`` is a column KEY (e.g. ``PRCI``);
    # ``move_card`` indexes the GitHub Status options by display NAME (e.g. ``PR/CI``), so the raw
    # key raised KeyError for the one column whose key != name (``PRCI``/``PR/CI``). Mirror the
    # session-end / script-route move paths, which already translate via ``resolve_column`` (which
    # also normalises the name/key seam in the idempotence check below — ``from_col`` is the GitHub
    # NAME the adapter emits as ``column_key``, while ``to_col`` is the engine KEY).
    to_column = resolve_column(columns, to_col)
    if to_column is None:
        _result(deps, intent_id, "rejected", f"unknown destination column {to_col!r}")
        deps.store.clear_intent(intent_id)
        return
    from_column = resolve_column(columns, from_col)

    # Optimistic concurrency / idempotence: if the card is ALREADY in the destination (a fresher
    # move, or a crash-resume after the move already landed), this is a no-op success.
    if from_column is not None and from_column.key == to_column.key:
        next_columns[item_id] = to_column.key
        _result(deps, intent_id, "done", f"already in {to_column.name}")
        deps.store.clear_intent(intent_id)
        return

    # Crash-safety breadcrumb: mark claimed BEFORE the mutation, so a re-drain after a crash sees the
    # move may have landed and the idempotent check above resolves it.
    _result(deps, intent_id, "claimed", f"moving {from_col}->{to_column.name}")
    deps.board_writer.move_card(item_id, to_column.name)
    # Baseline advance — but NOT for a launch-bearing edge. An operator move INTO a triggering column
    # must fire that column's entry agent, exactly like a GitHub board drag: the launch is driven by
    # diff(baseline, snapshot), so advancing the baseline here would suppress it (the live #55
    # ReadyToDev→PrepareFeature bug — the prepare/create-branch agent never fired). Leaving the
    # baseline UNADVANCED makes the next tick re-detect the arrival and run decide() (which applies the
    # anti-loop / rate-limit / kill-switch guards and itself advances the baseline once it launches —
    # so it fires exactly once, no loop). Non-launch edges (no-op / unlisted / script-only) still
    # advance: pure board mutations that must never re-fire or bounce.
    from_key = from_column.key if from_column is not None else from_col
    edge = transitions.get(from_key, to_column.key)
    if edge is None or not edge.prompt:
        next_columns[item_id] = to_column.key
    status_events.append(("auto", intent.issue, f"moved → {to_column.name}"))
    _result(deps, intent_id, "done", f"moved {from_col}->{to_column.name}")
    deps.store.clear_intent(intent_id)


def _execute_launch(
    deps: Deps,
    intent: Intent,
    *,
    intent_id: str,
    authority: Authority,
    transitions: TransitionConfig,
    columns: dict[str, Column],
    by_issue: dict[int, Ticket],
    running_issues: set[int],
    status_events: list[tuple[str, int | None, str]],
    processed_issues: set[int],
    concurrency_cap: int,
) -> None:
    """Execute an ad-hoc ``launch`` intent: start a Claude agent on a ticket WITHOUT a board move.

    Operator-only (``validate_intent`` rejects agents — ``launch`` is absent from
    ``AGENT_ALLOWED_KINDS``). Boots a bare ``claude`` in the ticket's worktree, delivers the
    operator's free-form prompt, and persists RUNNING state — but performs NO transition (the
    :class:`~kanbanmate.app.actions.LaunchAction` carries ``advance="stop"``), so the card stays in
    its current column. The use case is a one-off fix driven by an agent without exercising the
    column flow (operator 2026-06-21).

    Guards: refuses when an agent is already tracked for the issue (no double-launch), when the issue
    is absent from the board, when the prompt is empty, or when the concurrency cap is full. The slot
    is reserved BEFORE the launch and RELEASED if the launch raises (no slot leak).
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

    if intent.issue is None:
        _result(deps, intent_id, "rejected", "launch requires an issue")
        deps.store.clear_intent(intent_id)
        return

    # No double-launch: the daemon's own running-set is authoritative (the UI only offers the launch
    # form when idle, but an intent may have been enqueued while an agent was already starting).
    if intent.issue in running_issues:
        _result(deps, intent_id, "rejected", f"agent already running on #{intent.issue}")
        deps.store.clear_intent(intent_id)
        return

    ticket = by_issue.get(intent.issue)
    if ticket is None:
        _result(deps, intent_id, "rejected", f"issue #{intent.issue} not on the board")
        deps.store.clear_intent(intent_id)
        return

    # Prompt is OPTIONAL: empty → launch a BARE claude (the operator takes control of the terminal and
    # types instructions directly). A non-empty prompt is delivered verbatim into the REPL on launch.
    prompt = str(intent.args.get("prompt") or "").strip()
    launch_prompt = prompt if prompt else None
    # The ad-hoc use case is "make a fix" → default to `dev` (edit/commit/push). RESTRICT to the safe
    # set: `merge` (which lifts the gh-pr-merge ban) is engine-gated to Review→Merge ONLY and must
    # NEVER be attachable via an ad-hoc launch — that would break merge=human-only and is reachable by
    # a bridled agent (a launch intent for a non-running issue resolves to operator authority). Reject
    # anything outside the safe set loudly (not a silent degrade) so the operator sees the refusal.
    profile = str(intent.args.get("profile") or "dev")
    if profile not in SAFE_LAUNCH_PROFILES:
        _result(
            deps,
            intent_id,
            "rejected",
            f"profile {profile!r} not allowed for ad-hoc launch "
            f"(merge is engine-gated; allowed: {sorted(SAFE_LAUNCH_PROFILES)})",
        )
        deps.store.clear_intent(intent_id)
        return

    # FIX 4: authority for a launch on an IDLE issue derives to OPERATOR, so the running-set check
    # above does NOT stop a bridled agent (same UID) from enqueuing a launch for an arbitrary idle
    # ticket. Require a valid operator ``op_token`` HMAC the config-UI mints from the runtime-root
    # secret; refuse loudly otherwise. This RAISES THE BAR (defense-in-depth) — it is NOT airtight:
    # a same-uid broad-Bash agent (e.g. ``dev``) could ``cat <root>/launch_secret`` and mint a valid
    # token. The ``launch_secret`` read paths are denied across all profiles in adapters/perms.py to
    # narrow that, but the authoritative boundary is OS isolation (a distinct uid). Checked AFTER the
    # profile is resolved so the token binds the EXACT profile (no profile-swap replay), and BEFORE
    # reserving a slot or constructing the action (a rejected launch leaks nothing).
    if not _verify_launch_authorization(deps, intent, profile):
        _result(
            deps,
            intent_id,
            "rejected",
            "launch not operator-authorized (missing/invalid op_token); ad-hoc launches must come "
            "from the operator UI — refusing a possibly agent-forged launch",
        )
        deps.store.clear_intent(intent_id)
        return

    # Reserve a slot so an ad-hoc launch still respects the concurrency cap (idempotent per issue).
    if not deps.store.reserve_slot(intent.issue, concurrency_cap):
        _result(deps, intent_id, "rejected", "no free agent slot (concurrency cap reached)")
        deps.store.clear_intent(intent_id)
        return

    processed_issues.add(intent.issue)
    _result(deps, intent_id, "claimed", f"launching agent on #{intent.issue}")

    # Lazy import: keeps the heavy actions module off intents.py's import-time path (consistent with
    # this module's other lazy imports). app->app is permitted by the layering contract; no cycle.
    from kanbanmate.app.actions import LaunchAction  # noqa: PLC0415

    action = LaunchAction(
        ticket=ticket,
        prompt=launch_prompt,  # None → bare claude (operator types in the terminal); else verbatim
        profile=profile,
        permission_mode="auto",
        advance="stop",  # ad-hoc: NEVER move the card (no transition fires)
        fill_prompt=False,  # operator free-form prompt: deliver verbatim (NO placeholder fill)
        terminate_on_exit=True,  # the tmux session DISAPPEARS when the operator exits claude
    )
    try:
        action.execute(deps)
    except Exception as exc:  # noqa: BLE001 — release the slot so a failed launch never leaks it
        deps.store.release_slot(intent.issue)
        logger.exception("ad-hoc launch for #%s failed", intent.issue)
        _result(deps, intent_id, "rejected", f"launch failed: {exc}")
        deps.store.clear_intent(intent_id)
        return

    status_events.append(("launch", intent.issue, f"ad-hoc agent launched ({profile})"))
    _result(deps, intent_id, "done", f"launched agent on #{intent.issue}")
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
    """Execute a ``ticket_edit`` intent: rewrite the issue body (operator-only). Idempotent.

    Two EXPLICIT semantics — chosen by which arg the producer carries (never both):

    * ``args["body"]`` — the CLI ``kanban ticket edit --body`` path: a FULL-body REPLACE (the operator
      supplies the complete intended body, exactly as the CLI contract documents). No merge — the body
      is written as-is. This is the ONLY currently-live producer.
    * ``args["freeform"]`` — a marker-SAFE merge: the current GitHub body is fetched and split into
      protected regions (the ``STATUS_BEGIN/END`` status header, the ``**roadmap**``/``**codename**``/
      ``**design**``/``**plans**`` markers, ``## Brainstorm``) + the operator-editable freeform; the new
      freeform replaces only the freeform region and the protected regions are re-appended verbatim.
      NOTE: no live producer enqueues ``freeform`` today — the SPA ``PATCH /ticket/{n}/body`` route does
      this same merge INLINE and patches GitHub synchronously (it does not go through the intent path).
      This branch is implemented + tested, RESERVED for routing the SPA edit through the daemon (single
      audited writer) later.

    Carrying the semantics EXPLICITLY (a distinct ``freeform`` key for the merge path) keeps ``--body``
    a true replace, so neither producer is mis-interpreted (a ``body`` treated as freeform would
    re-append STALE markers and silently drop the operator's full-body intent).
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

    seeder = deps.seeder
    # Exactly ONE of ``freeform`` (SPA merge) / ``body`` (CLI full replace) selects the semantics.
    freeform = intent.args.get("freeform")
    body = intent.args.get("body")
    is_merge = isinstance(freeform, str)
    new_text = freeform if is_merge else body
    if intent.issue is None or not isinstance(new_text, str):
        _result(
            deps,
            intent_id,
            "rejected",
            "ticket_edit requires an issue and a 'freeform' (merge) or 'body' (full replace) string",
        )
        deps.store.clear_intent(intent_id)
        return
    if seeder is None:
        _result(deps, intent_id, "rejected", "ticket_edit unavailable: no seeder configured")
        deps.store.clear_intent(intent_id)
        return

    # FIX 1: fetch the issue ONCE (reused for the node id AND — on the merge path — the current body +
    # title). A fetch failure REJECTS the intent (mirroring the SPA route's 404). We must NEVER fall
    # back to an empty current body on the merge path: ``split_body_regions("")`` yields no protected
    # regions, so the merge would write ONLY the new freeform and PERMANENTLY DELETE the real body's
    # status block + markers + ``## Brainstorm`` — an unrecoverable overwrite.
    issue_ref = _fetch_issue_ref(seeder, intent.issue)
    if issue_ref is None:
        _result(deps, intent_id, "rejected", f"issue #{intent.issue} not found")
        deps.store.clear_intent(intent_id)
        return

    _result(deps, intent_id, "claimed", "editing body")

    if is_merge:
        from kanbanmate.core.body_edit import validate_roadmap_matches_title  # noqa: PLC0415
        from kanbanmate.core.body_regions import (  # noqa: PLC0415
            merge_body_regions,
            split_body_regions,
        )

        regions = split_body_regions(issue_ref.body or "")
        merged = merge_body_regions(regions, new_freeform=new_text)
        # FIX 3: enforce the same coherence gate the SPA route runs — a merge must not desync the
        # ticket↔roadmap binding (a stray ``**roadmap**`` that disagrees with the title [CODE]).
        coherence_error = validate_roadmap_matches_title(merged, issue_ref.title or "")
        if coherence_error:
            _result(deps, intent_id, "rejected", coherence_error)
            deps.store.clear_intent(intent_id)
            return
        final_body = merged
    else:
        # CLI full-body replace: the operator supplied the complete intended body — write it verbatim.
        final_body = new_text

    seeder.update_issue_body(issue_ref.node_id, final_body)
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
    ref = _fetch_issue_ref(seeder, issue)
    return ref.node_id if ref is not None else None


def _fetch_issue_ref(seeder: Seeder, issue: int) -> IssueRef | None:
    """Fetch an issue's :class:`IssueRef` (node id + title + body), or ``None`` on failure.

    A single fetch backs both the node id and (on the ticket_edit merge path) the current body + title,
    so the executor never fetches the same issue twice. A lookup failure is a clean ``None`` (the
    caller rejects the intent) — never a crash and never a fail-soft empty body that would let a merge
    clobber the real protected regions.
    """
    try:
        return seeder.fetch_issue(issue)
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


def _runtime_root(deps: Deps) -> Path:
    """Resolve the daemon's top-level runtime root (where the launch secret lives).

    ``Deps.kanban_root`` is the registry's top-level runtime root (``registry_wiring`` threads
    ``kanban_root=str(root)``), the SAME directory the config-UI resolves via ``_kanban_root()`` — so
    the launch secret stored there is shared across the two processes. An empty ``kanban_root`` (the
    legacy default daemon) maps to ``~/.kanban``.
    """
    return Path(deps.kanban_root).expanduser() if deps.kanban_root else _DEFAULT_KANBAN_ROOT


def load_launch_secret(root: Path, *, create: bool = False) -> bytes | None:
    """Load (or, when ``create``, lazily mint) the launch-authorization secret under ``root``.

    The secret keys the ``op_token`` HMAC that proves a ``launch`` intent was minted by the operator's
    config-UI (the SOLE legitimate ``launch`` producer) and not forged by a bridled agent that can
    write the shared intents directory. It lives at ``<root>/launch_secret`` with ``0600`` perms.

    The UI producer calls this with ``create=True`` (mint-on-first-use); the daemon verifier calls it
    with ``create=False`` (a missing secret means no operator has ever minted a token, so every launch
    is unverifiable → rejected, never silently trusted).

    Args:
        root: The runtime root the secret file lives under.
        create: When ``True`` and the file is absent, generate a strong random secret (0600).

    Returns:
        The secret bytes, or ``None`` when absent (and ``create`` is ``False``) or unreadable.
    """
    path = root / LAUNCH_SECRET_FILENAME
    try:
        if path.exists():
            data = path.read_bytes().strip()
            return data or None
        if not create:
            return None
        root.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_hex(32).encode("ascii")
        # O_EXCL so a concurrent minter never truncates an existing secret (last-writer race); if it
        # lost the race, fall through to re-reading the winner's bytes.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return path.read_bytes().strip() or None
        with os.fdopen(fd, "wb") as fh:
            fh.write(secret)
        return secret
    except OSError:
        logger.warning("launch secret at %s unreadable/unwritable", path, exc_info=True)
        return None


def compute_launch_token(secret: bytes, issue: int, profile: str) -> str:
    """Return the operator ``op_token`` HMAC binding a launch to its ``(issue, profile)``.

    Binding both fields means a captured token cannot be replayed for a DIFFERENT ticket or to escalate
    to a different (e.g. broader) profile.

    Args:
        secret: The launch-authorization secret (see :func:`load_launch_secret`).
        issue: The target issue number.
        profile: The requested permission profile.

    Returns:
        A hex HMAC-SHA256 digest.
    """
    msg = f"{issue}:{profile}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _verify_launch_authorization(deps: Deps, intent: Intent, profile: str) -> bool:
    """Return ``True`` when ``intent`` carries a valid operator ``op_token`` for ``(issue, profile)``.

    FIX 4 (launch escalation): a ``launch`` intent targeting an IDLE issue resolves to OPERATOR
    authority (authority is ``agent`` only when the issue is in the running set), and ``validate_intent``
    has no structural ``launch`` check — so a bridled agent (same UID, can write the intents dir) could
    enqueue a launch for an arbitrary idle ticket and be handed a privileged ``dev`` agent. The config-
    UI (the only legitimate launch producer) mints an ``op_token`` HMAC keyed by ``<root>/launch_secret``;
    the daemon recomputes it here. A token-less / wrong-token launch is refused (constant-time compare).
    This is DEFENSE-IN-DEPTH, not an airtight barrier: an agent that can read the runtime-root secret
    (a same-uid broad-Bash profile) could mint a valid token. ``launch_secret`` reads are denied across
    profiles (adapters/perms.py) to narrow that; the authoritative boundary is a distinct OS uid.
    """
    secret = load_launch_secret(_runtime_root(deps), create=False)
    if secret is None:
        # No secret minted yet → no launch can be proven operator-originated → refuse (never trust).
        return False
    token = intent.args.get("op_token")
    if not isinstance(token, str) or not token:
        return False
    expected = (
        compute_launch_token(secret, intent.issue, profile) if intent.issue is not None else ""
    )
    return bool(expected) and hmac.compare_digest(token, expected)


def _result(deps: Deps, intent_id: str, state: str, detail: str = "") -> None:
    """Persist an intent's (interim or terminal) result for the CLI ``--wait`` to poll."""
    deps.store.save_intent_result(
        intent_id, {"intent_id": intent_id, "state": state, "detail": detail}
    )
