"""Agent helper: signal a ticket's agent session has ended (DESIGN §8.1.f / §8.3).

``kanban-session-end <issue>`` runs after the agent's ``claude`` process exits (the dispatcher
wires it as ``claude … ; kanban-session-end <issue>`` so it fires whether the agent exited
cleanly, crashed, or was interrupted — the trailing ``;`` is intentional). The session is OVER, so
it **tears the runtime state down exhaustively** (the cap slot, the running state, the breadcrumb,
and any queue/moves/retries markers via :meth:`~kanbanmate.ports.store.StateStore.purge_ticket`)
and — when the agent ended WITHOUT either advancing its card OR signalling a clean ``kanban-done`` —
finalizes the stage sticky to ⚠️ *interrupted* (DESIGN §8.1.f, port of the PoC
``cli/session_end.py::finalize_session``).

The ✅/⚠️ split is decided by TWO breadcrumbs (DESIGN §8.1.d), both keyed by the **issue number**:

* **advance** (dropped via ``kanban-move`` before ``claude`` exits) — PRESENT → the agent advanced
  its card; the daemon's ✅-on-advance finalize (8.1.e) already flipped the LEFT stage to ✅ done,
  so session-end leaves the sticky untouched.
* **done** (dropped via ``kanban-done``, #FIX3) — PRESENT (and no advance) → an advance:stop stage
  (brainstorm/design/plan) that completed CLEANLY: it never advances, so session-end finalizes the
  stage sticky ✅ done itself (no daemon-side finalize runs for a done-without-advance).
* NEITHER present → the agent ended without advancing or signalling done; session-end finalizes the
  current stage ⚠️ interrupted (a genuine crash/interrupt — the ONLY ⚠️ case).

**Ordering (load-bearing — DESIGN §8.1.f).** BOTH breadcrumbs MUST be read BEFORE
:meth:`~kanbanmate.adapters.store.fs_store.FsStateStore.purge_ticket`, because ``purge_ticket``
PURGES them (DESIGN §8.1.d — a torn-down ticket leaves no stale breadcrumb). Reading after the
purge would always observe "absent" and wrongly finalize ⚠️ even after a clean ✅ advance/done,
silently breaking the headline split. The correct order is: load state → read advance breadcrumb →
read done breadcrumb → purge ticket → branch on the breadcrumbs.

This is a leaf entrypoint (DESIGN §3.2): the purge touches only the local state store (no
network); the ⚠️ finalize wires a :class:`~kanbanmate.adapters.github.client.GithubClient` from the
loaded token + the per-clone registry (mirroring ``bin/kanban_comment.py`` / ``bin/kanban_move.py``).
The whole path is FAIL-SOFT: a missing token / unreachable API / GitHub error never breaks the
always-run session-end (the upsert is internally fail-soft, and the leaf swallows wiring errors to a
non-zero exit). On a bad/missing argument it fails cleanly (non-zero exit, clear stderr) and never
crashes the calling agent shell.
"""

from __future__ import annotations

import sys
import time
from dataclasses import asdict
from typing import Literal

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.app.body_status import update_body_status
from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.app.status_reporter import extract_latest_progress
from kanbanmate.bin._clone_config import (
    auto_advance_target,
    load_clone_columns,
    load_clone_transitions,
    resolve_entry,
    resolve_entry_token,
)
from kanbanmate.bin._pin import helper_store_root, parse_issue_arg
from kanbanmate.cli.init import ProjectEntry
from kanbanmate.core.columns import resolve_column
from kanbanmate.core.stage_comment import StageStatus, fmt_timestamp, header_from_state
from kanbanmate.ports.store import TicketState

_PROG = "kanban-session-end"

# The Blocked column the auto-advance backstop parks a rate-limited runaway in (DESIGN §13). The
# stable column KEY in the shipped board model; resolved to its display NAME before move_card.
_BLOCKED_KEY = "Blocked"

# The outcome of :func:`_auto_advance` (Candidate 4): ``advanced`` (moved to the auto target),
# ``stopped`` (advance:stop / no item id / unknown target → no move), or ``parked_blocked`` (the
# rate-limit backstop parked the card in Blocked). The done-branch caller uses this to make the
# finalized sticky reflect the REAL outcome — a ⛔ blocked sticky on a parked card, not a misleading
# ✅ done.
AutoAdvanceResult = Literal["advanced", "stopped", "parked_blocked"]


def _read_latest_progress(client: GithubClient, issue: int, stage: str) -> str | None:
    """Read the latest progress milestone off ``issue``'s ``stage`` sticky (BUG A; fully fail-soft).

    Session-end producers hold a raw :class:`GithubClient` (not a ``Deps``), so they fetch the issue
    comments here and delegate to the PURE
    :func:`kanbanmate.app.status_reporter.extract_latest_progress`. The whole read is wrapped: ANY
    error (unreachable API, parse error) degrades to ``None`` so the body header simply falls back to
    its static summary — a finalize must never break the always-run session-end.

    Args:
        client: The wired GitHub client (also the comment-reader).
        issue: The issue number whose sticky to read.
        stage: The stage owning the sticky to locate.

    Returns:
        The latest progress milestone text, or ``None`` on a miss / error.
    """
    try:
        return extract_latest_progress(client.list_issue_comments(issue), stage)
    except Exception:  # noqa: BLE001 — fail-soft: a progress read never breaks session-end.
        return None


def _resolve_entry() -> ProjectEntry:
    """Resolve the single registered project from the per-clone registry.

    Back-compat thin wrapper over :func:`kanbanmate.bin._clone_config.resolve_entry` (the loader
    was lifted into the shared ``_clone_config`` module so this leaf and ``kanban-move`` read the
    SAME source of truth). Existing tests monkeypatch ``_resolve_entry`` on this module, so the
    name is preserved here.

    Returns:
        The sole :class:`~kanbanmate.cli.init.ProjectEntry`.

    Raises:
        RuntimeError: When the registry does not hold exactly one project.
    """
    return resolve_entry()


def _resolve_entry_token(entry: ProjectEntry) -> str:
    """Resolve the PER-ENTRY GitHub token for ``entry`` (multi-org §6, #4).

    Thin delegate to the shared :func:`kanbanmate.bin._clone_config.resolve_entry_token` so the
    session-end finalize authenticates with the SAME per-org PAT the daemon used (a second org's
    entry carries a ``token_ref``; N=1 → the shared token). Kept module-level for monkeypatching.

    Args:
        entry: The resolved registry entry (its ``token_ref`` selects the token file).

    Returns:
        The resolved token string for this entry.
    """
    return resolve_entry_token(entry)


def _auto_advance(
    state: TicketState,
    issue: int,
    client: GithubClient,
    entry: ProjectEntry,
    store: FsStateStore,
    *,
    now: float,
) -> AutoAdvanceResult:
    """Honour a clean-done LAUNCH stage's ``advance:auto:<col>`` directive (DESIGN §13 backstop).

    Mirrors ``app/script_route._route_success``'s auto-advance for the LAUNCH-stage path the engine
    previously left dead: when a launch stage carries ``advance:auto:<col>`` and the agent ran
    ``kanban-done`` WITHOUT moving its own card (the caller is inside ``done and not advanced``),
    the ENGINE moves the card to ``<col>`` so the daemon's next ``diff`` fires the next stage.

    Candidate 4: this RETURNS its outcome (``advanced`` / ``stopped`` / ``parked_blocked``) so the
    caller can finalize the stage sticky to MATCH it. Previously the caller finalized ✅ done BEFORE
    calling this, leaving a misleading ✅-done sticky on a card this function then parked in Blocked
    on a rate-limited runaway. The caller now finalizes AFTER reading this result.

    Discipline (matching the script-route gold standard):

    * **clean-done gate** — only the caller's ``done and not advanced`` branch reaches here; an
      interrupt (neither breadcrumb) goes to ⚠️, an agent self-move returned at branch 4. No double
      move.
    * **stop = no move** — :func:`auto_advance_target` returns ``None`` for ``advance:stop`` (the
      ReadyToDev + Review human gates) → the card STOPS. This preserves the HYBRID human-review gates.
    * **KEY → NAME** — the directive carries a column KEY; resolve it to the board's display NAME
      via :func:`~kanbanmate.core.columns.resolve_column` (the script-route ``_to_board_name``
      pattern) so a multiword column ("PR/CI") lands instead of raising ``KeyError`` in move_card.
    * **rate-limit + anti-loop** — the OUTER per-issue rate-limit backstop: at/over
      ``move_rate_limit_per_hour`` AUTO/bot moves this hour, the card is parked in Blocked instead
      (bounding a runaway auto-advance chain). The engine move is the SANCTIONED mover (like the
      script-route auto-move), so it moves directly via ``client.move_card`` — NEVER through
      ``kanban_move.main()`` (whose AGENT anti-loop guard would refuse a launch-target column).
    * **records the move, NOT an advance** — a successful move calls
      :meth:`~kanbanmate.ports.store.StateStore.record_move_for_item` (feeds the rate-limit + makes
      the daemon diff fire the next stage). It MUST NOT call ``record_agent_advance``: the engine
      move is not an agent advance (the ✅/⚠️ sticky discriminator), and the sticky is already ✅.
    * **fail-soft** — every board op is wrapped; on any error a warning is logged to stderr and the
      session-end still returns 0 (it is the always-run leaf). The card simply does not advance —
      no loop, no crash. Idempotency: a re-run hits the purged-state early return (no breadcrumb,
      no move); a move to the column the card already sits in is a GitHub no-op.

    Args:
        state: The loaded :class:`~kanbanmate.ports.store.TicketState` (carries ``advance`` +
            ``item_id``).
        issue: The ticket's issue number (the rate-limit + comment key).
        client: The fail-soft :class:`~kanbanmate.adapters.github.client.GithubClient` (wired once
            by the caller for both the sticky finalize and this move).
        entry: The resolved project registry entry (the clone path for the column + transition
            config loaders).
        store: The runtime state store (the rate-limit ledger).
        now: The current wall-clock time (the rate-limit window + the recorded move timestamp).
    """
    target_key = auto_advance_target(state.advance)
    if target_key is None:
        # advance:stop (or empty/malformed) → the card STOPS (the ReadyToDev/Review human gates). The
        # previously-dead config was a no-op for launch stages; for a stop directive that is still
        # correct — nothing to do.
        return "stopped"
    if not state.item_id:
        # No persisted card node id → nothing to move (a draft/old-format state); fail-soft no-op.
        return "stopped"
    try:
        columns = load_clone_columns(entry)
        cfg = load_clone_transitions(entry)
    except Exception as exc:  # noqa: BLE001 — fail-soft: a config-read failure never breaks session-end.
        print(
            f"{_PROG}: warning: could not load clone config for #{issue} auto-advance: {exc}",
            file=sys.stderr,
        )
        return "stopped"

    # Resolve the directive KEY → the board's display NAME (defect-2 pattern) so a multiword
    # target ("PR/CI") lands. An unknown target column → fail-soft no-op (never raise).
    target_col = resolve_column(columns, target_key)
    if target_col is None:
        print(
            f"{_PROG}: warning: auto-advance target {target_key!r} for #{issue} is not a known "
            "column; skipping the engine move",
            file=sys.stderr,
        )
        return "stopped"
    target_name = target_col.name

    # OUTER per-issue rate-limit backstop (matching _route_success: the
    # cap-th move allowed, the (cap+1)-th parked). Bounds a runaway auto-advance chain. The engine
    # move is the only feeder of this counter on a launch stage (the agent's own kanban-move never
    # records it, and the reaper park is excluded — Candidate 1), so the human workflow is never
    # rate-limited.
    if store.move_count_for_item_last_hour(issue, now=now) >= cfg.move_rate_limit_per_hour:
        blocked_col = resolve_column(columns, _BLOCKED_KEY)
        blocked_name = blocked_col.name if blocked_col is not None else _BLOCKED_KEY
        try:
            client.move_card(state.item_id, blocked_name)
            client.comment(
                issue,
                "KanbanMate: auto-advance rate limit exceeded — parked in Blocked.",
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft: a park-board-op error never breaks session-end.
            print(
                f"{_PROG}: warning: could not park #{issue} in Blocked (rate limit): {exc}",
                file=sys.stderr,
            )
        # Record the engine's own park move so a later tick recognises it + the counter stays
        # bounded (defense-in-depth, matching _park_runaway).
        store.record_move_for_item(issue, now=now)
        print(
            f"{_PROG}: ticket #{issue} auto-advance rate-limited — parked in Blocked.",
            file=sys.stderr,
        )
        return "parked_blocked"

    # Within the limit → the SANCTIONED engine auto-advance move. Direct client.move_card (NOT
    # kanban_move.main, whose agent anti-loop guard would refuse a launch-target column). Record
    # the move so the daemon's next diff sees (stage → target) and fires the target transition.
    try:
        client.move_card(state.item_id, target_name)
        store.record_move_for_item(issue, now=now)
        print(f"{_PROG}: ticket #{issue} auto-advanced -> {target_name} (engine backstop).")
        return "advanced"
    except Exception as exc:  # noqa: BLE001 — fail-soft: the engine move must never break session-end.
        print(
            f"{_PROG}: warning: could not auto-advance #{issue} to {target_name!r}: {exc}",
            file=sys.stderr,
        )
        # A failed move did not park or advance; treat as a no-op (the card stays where it is). The
        # caller finalizes ✅ done — the clean-completion outcome the agent signalled.
        return "stopped"


def main(argv: list[str] | None = None) -> int:
    """Entry point: release the ticket's slot, then finalize ⚠️ iff it died without advancing.

    Ports the PoC ``finalize_session`` onto NEW's ports, keyed by the issue number throughout
    (DESIGN §8.1.d/.f):

    1. Load the persisted ``TicketState``. ``None`` → the state was purged by a Cancel teardown:
       idempotently purge the ticket, do NO GitHub I/O, and return (no-resurrection early-return).
    2. Read the advance breadcrumb (:meth:`recent_agent_advance`) AND the done breadcrumb
       (:meth:`recent_agent_done`, #FIX3) BEFORE the purge — the purge removes both (DESIGN §8.1.d),
       so reading them first is mandatory or the ✅/⚠️ split mis-fires.
    3. ``purge_ticket`` (frees the cap slot + running state + the now-consumed breadcrumbs +
       any queue/moves/retries markers — the session is over).
    4. If the advance breadcrumb was present → the agent advanced; the daemon's 8.1.e already
       finalized ✅, so leave the sticky untouched and return.
    4b. Else if the done breadcrumb was present (#FIX3) → a clean completion that never advances:
       run the ``advance:auto`` backstop FIRST, then finalize the stage sticky to MATCH its outcome
       (✅ done normally, ⛔ blocked when the backstop rate-limit-parked the card — Candidate 4) via
       a fail-soft ``GithubClient`` and return.
    5. Otherwise (NEITHER breadcrumb) → a genuine crash/interrupt: resolve the stage from
       ``TicketState.stage`` alone (8.1.d persists it directly — no separate ``columns/`` marker)
       and finalize the sticky ⚠️ *interrupted* via a fail-soft ``GithubClient``. An empty stage
       means nothing to finalize → return silently.

    Failure handling: a usage error exits ``2``; a store/wiring failure is reported to stderr and
    exits ``1`` — never a traceback that would crash the calling agent shell. The ⚠️ finalize is
    fail-soft (a missing token / unreachable API / GitHub error never breaks session-end).

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``. Expects exactly ``<issue>``.

    Returns:
        ``0`` on success, ``2`` on a usage error, ``1`` on any other failure.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    if len(raw_argv) != 1:
        print(f"usage: {_PROG} <issue>", file=sys.stderr)
        return 2
    try:
        issue = parse_issue_arg(raw_argv[0])
    except ValueError:
        print(f"{_PROG}: issue must be an integer, got {raw_argv[0]!r}", file=sys.stderr)
        return 2

    try:
        # Resolve the store at the per-project sub-root when the worktree is project-pinned
        # (multi-project §3.2), else the bare runtime root (#1 km-root fix; N=1 byte-identical). The
        # session-end runs as ``; kanban-session-end`` in the agent's worktree cwd, so the upward
        # project-pin search resolves the SAME sub-root the daemon launched + wrote state to. The
        # module-scoped ``FsStateStore`` is used so tests can monkeypatch it.
        _store_root, _nudge_root = helper_store_root()
        store = (
            FsStateStore(_store_root)
            if _nudge_root is None
            else FsStateStore(_store_root, nudge_root=_nudge_root)
        )
        now = time.time()

        # 1. No-resurrection early-return: a purged state (Cancel teardown already cleaned up the
        #    slot, state and breadcrumb) means there is nothing to finalize. Idempotently purge the
        #    ticket (a no-op once already purged) and return BEFORE any GitHub I/O (DESIGN §8.1.f).
        #    keep_budgets=True (13.8): a session-end is an inter-session idle, not an abandonment —
        #    preserve the per-issue §6 rate-limit / fix-CI retry budgets (PoC end_session fidelity).
        state = store.load(issue)
        if state is None:
            store.purge_ticket(issue, keep_budgets=True)
            print(
                f"{_PROG}: ticket #{issue} state already purged; "
                "runtime record removed, per-issue budgets preserved."
            )
            return 0

        # 2. Read the breadcrumb FIRST — purge_ticket (step 3) PURGES it (DESIGN §8.1.d), so a
        #    read after the purge would always look "absent" and wrongly finalize ⚠️ even after
        #    a clean ✅ advance. Keyed by the ISSUE number (8.1.d invariant), matching the writer
        #    in bin/kanban_move.py.
        advanced = store.recent_agent_advance(issue, now=now)

        # FIX3: a clean advance:stop stage (brainstorm/design/plan) runs kanban-done (DONE breadcrumb)
        # and NEVER advances — so it must finalize ✅ done, not ⚠️ interrupted. Read the DONE breadcrumb
        # BEFORE purge_ticket (purge clears done/<issue> too — same load-bearing ordering as the advance
        # breadcrumb above), so a post-purge read would always look "absent". Keyed by the issue number.
        done = store.recent_agent_done(issue, now=now)

        # 3. The agent process exited, so tear the RUNTIME state down: purge the cap slot + running
        #    state (the reaper stops aging the ticket) + the now-consumed breadcrumb + the queue
        #    marker. This is ``purge_ticket`` (the session is over), NOT the slot-only
        #    ``release_slot`` (13.7 PoC split). keep_budgets=True (13.8): a session-end is an
        #    inter-session idle, not an abandonment, so the per-issue §6 rate-limit history
        #    (``moves/``) and fix-CI retry counters (``retries/``) are PRESERVED across the gap
        #    (PoC end_session fidelity — only Cancel / reset drops them). Idempotent: a session-end
        #    / teardown race never double-frees.
        store.purge_ticket(issue, keep_budgets=True)

        # 4. The agent advanced its own card. The daemon's ✅-on-advance finalize (8.1.e) USUALLY
        #    flipped the LEFT stage to ✅ done already — but that finalize only runs when the card
        #    actually advanced via the diff/RUN_SCRIPT path. When the ENGINE advanced the card
        #    instead (e.g. a clean kanban-done on a launch stage with advance:auto, or an
        #    InProgress→PR/CI advance the daemon drove), the left-stage ✅ finalize can race or be
        #    missed → the sticky is stranded 🟡 running. DEFENSE-IN-DEPTH (BUG B): finalize the
        #    persisted state.stage sticky ✅ done HERE too. upsert_stage_comment header-swaps in place
        #    (idempotent — a no-op if already ✅), so this is safe regardless of which path advanced
        #    the card. Mirrors the 4b/4c done-without-advance finalize. Fully fail-soft.
        if advanced:
            stage = state.stage
            if stage:
                try:
                    entry = _resolve_entry()
                    # Per-entry token (#4): a second org's entry carries a ``token_ref``; N=1 → shared.
                    client = GithubClient(
                        _resolve_entry_token(entry), project_id=entry.project_id, repo=entry.repo
                    )
                    header = header_from_state(
                        asdict(state), issue, stage, "done", finished=fmt_timestamp(now)
                    )
                    upsert_stage_comment(client, issue, stage, header=header, now=now)
                    # Mirror the ✅ finalize in the body-top status header (idempotent, body-diff-gated).
                    # BUG A: surface the latest milestone (None → falls back to "stage complete").
                    update_body_status(
                        client,
                        issue,
                        stage=stage,
                        state="done",
                        summary="stage complete",
                        now=now,
                        latest_progress=_read_latest_progress(client, issue, stage),
                    )
                except Exception as exc:  # noqa: BLE001 — fail-soft: a finalize error never breaks session-end.
                    print(
                        f"{_PROG}: warning: could not finalize ✅ sticky for advanced #{issue}: {exc}",
                        file=sys.stderr,
                    )
            print(
                f"{_PROG}: ticket #{issue} advanced; runtime record removed "
                "(slot freed, breadcrumb consumed), per-issue budgets preserved, sticky finalized ✅."
            )
            return 0

        # 4b. FIX3: the agent finished cleanly via kanban-done but did NOT advance its card (the
        #     advance:stop stages — brainstorm/design/plan — drop a DONE breadcrumb and stop). This
        #     is a CLEAN completion, not a crash, so finalize the stage sticky ✅ done (NOT ⚠️
        #     interrupted). The ⚠️ path below is reserved for NEITHER breadcrumb present (a genuine
        #     crash/interrupt). Unlike the advance path (the daemon's 8.1.e already finalized ✅), no
        #     daemon-side finalize runs for a done-without-advance, so session-end finalizes it here.
        if done:
            stage = state.stage
            if not stage:
                print(
                    f"{_PROG}: ticket #{issue} done (no advance), no recorded stage; "
                    "runtime record removed (slot freed), per-issue budgets preserved."
                )
                return 0
            # Wire a fail-soft GithubClient ONCE for BOTH the ✅ sticky finalize AND the
            # auto-advance backstop (4c). Both share the same entry/client; an unreachable API
            # must never break the always-run session-end, so the wiring is wrapped.
            try:
                entry = _resolve_entry()
                # Per-entry token (#4): a second org's entry carries a ``token_ref``; N=1 → shared.
                client = GithubClient(
                    _resolve_entry_token(entry), project_id=entry.project_id, repo=entry.repo
                )
            except Exception as exc:  # noqa: BLE001 — fail-soft: wiring failure never breaks session-end.
                print(
                    f"{_PROG}: warning: could not wire GitHub client for #{issue}: {exc}",
                    file=sys.stderr,
                )
                # No client → neither the sticky finalize nor the auto-advance can run; the slot is
                # already freed (step 3), so report the clean done and return (fail-soft).
                print(
                    f"{_PROG}: ticket #{issue} done (clean completion, no advance); runtime record "
                    "removed (slot freed), per-issue budgets preserved (GitHub finalize skipped)."
                )
                return 0
            # 4c. ENGINE auto-advance backstop (DESIGN §13 hybrid flow). A clean-done LAUNCH stage
            #     whose persisted ``advance`` is ``auto:<col>`` and whose agent did NOT advance its
            #     own card (we are inside ``done and not advanced``) is moved to ``<col>`` by the
            #     engine — turning the previously-DEAD ``advance:auto`` config into a live move so
            #     the daemon's next diff fires the next stage. ``advance:stop`` (the ReadyToDev + Review
            #     human gates) returns "stopped" here → the card STOPS (no move). Idempotent +
            #     fail-soft + rate-limited; see :func:`_auto_advance`.
            #
            # Candidate 4: run the auto-advance FIRST, then finalize the sticky to MATCH its outcome.
            # On a rate-limited runaway _auto_advance parks the card in Blocked → the sticky must be
            # ⛔ blocked, not a misleading ✅ done on a now-Blocked card. Otherwise finalize ✅ done.
            advance_result = _auto_advance(state, issue, client, entry, store, now=now)
            sticky_status: StageStatus
            if advance_result == "parked_blocked":
                sticky_status = "blocked"
                body_summary = "rate-limited — parked in Blocked"
                report_tail = "card parked in Blocked, sticky finalized ⛔."
            else:
                sticky_status = "done"
                body_summary = "stage complete"
                report_tail = "sticky finalized ✅."
            try:
                header = header_from_state(
                    asdict(state), issue, stage, sticky_status, finished=fmt_timestamp(now)
                )
                upsert_stage_comment(client, issue, stage, header=header, now=now)
            except Exception as exc:  # noqa: BLE001 — fail-soft: a finalize error never breaks session-end.
                print(
                    f"{_PROG}: warning: could not finalize {sticky_status} sticky for #{issue}: {exc}",
                    file=sys.stderr,
                )
            # FIX 5: mirror the finalized sticky in the body-top status header (done OR blocked).
            # BUG A: surface the latest milestone (None → falls back to the static body_summary).
            update_body_status(
                client,
                issue,
                stage=stage,
                state=sticky_status,
                summary=body_summary,
                now=now,
                latest_progress=_read_latest_progress(client, issue, stage),
            )
            print(
                f"{_PROG}: ticket #{issue} done (clean completion, no advance); runtime record "
                f"removed (slot freed), per-issue budgets preserved, {report_tail}"
            )
            return 0

        # 5. NEITHER advance NOR done breadcrumb → genuine crash/interrupt. Finalize the current
        #    stage ⚠️ interrupted from the loaded TicketState. The stage resolves from
        #    TicketState.stage ALONE (8.1.d persists the launch stage directly; OLD's
        #    get_item_column fallback is collapsed). An old-format state with no recorded stage has
        #    nothing to finalize.
        stage = state.stage
        if not stage:
            print(
                f"{_PROG}: ticket #{issue} has no recorded stage; runtime record removed "
                "(slot freed), per-issue budgets preserved."
            )
            return 0

        # Wire a fail-soft GithubClient for the ⚠️ finalize (mirrors bin/kanban_comment.py /
        # bin/kanban_move.py). The whole finalize is best-effort: a missing token / unreachable
        # API / GitHub error must NEVER break the always-run session-end (the upsert is internally
        # fail-soft, and the wiring itself is wrapped here so it cannot crash the leaf).
        try:
            entry = _resolve_entry()
            # Per-entry token (#4): a second org's entry carries a ``token_ref``; N=1 → shared token.
            client = GithubClient(
                _resolve_entry_token(entry), project_id=entry.project_id, repo=entry.repo
            )
            # The widened TicketState (8.1.d) makes the ⚠️ sticky carry the SAME metadata bullets
            # the PoC rendered (full parity) — build the header via header_from_state, never a bare
            # HeaderInfo. asdict converts the frozen dataclass to the mapping header_from_state reads.
            header = header_from_state(
                asdict(state), issue, stage, "interrupted", finished=fmt_timestamp(now)
            )
            upsert_stage_comment(client, issue, stage, header=header, now=now)
            # FIX 5: mirror the ⚠️ interrupted sticky in the body-top status header. The client
            # is wired (this branch); ``update_body_status`` is itself fully fail-soft.
            # BUG A: surface the agent's last milestone before it crashed (None → falls back to the
            # static "session ended without advancing").
            update_body_status(
                client,
                issue,
                stage=stage,
                state="interrupted",
                summary="session ended without advancing",
                now=now,
                latest_progress=_read_latest_progress(client, issue, stage),
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft: a finalize error never breaks session-end.
            print(
                f"{_PROG}: warning: could not finalize ⚠️ sticky for #{issue}: {exc}",
                file=sys.stderr,
            )
    except Exception as exc:  # noqa: BLE001 — never crash the caller; report + exit non-zero.
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 1

    print(
        f"{_PROG}: ticket #{issue} session ended; runtime record removed "
        "(slot freed, breadcrumb consumed), per-issue budgets preserved, sticky finalized ⚠️."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
