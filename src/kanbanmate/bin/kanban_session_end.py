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

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.token import load_token
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.app.stage_signal import upsert_stage_comment
from kanbanmate.bin._pin import _registry_root, parse_issue_arg, resolve_kanban_root
from kanbanmate.cli.init import ProjectEntry, _load_registry, _projects_path
from kanbanmate.core.stage_comment import fmt_timestamp, header_from_state

_PROG = "kanban-session-end"


def _resolve_entry() -> ProjectEntry:
    """Resolve the single registered project from the per-clone registry.

    v1 runs one repo per clone (DESIGN §4.3), so the registry must hold exactly one
    entry; anything else is an operator misconfiguration we surface loudly. The registry is read
    from the runtime root resolved by :func:`_registry_root` (``$KANBAN_ROOT`` when set, else the
    ~/.kanban default — the km-worktree-helper-root fix, #1).

    Returns:
        The sole :class:`~kanbanmate.cli.init.ProjectEntry`.

    Raises:
        RuntimeError: When the registry does not hold exactly one project.
    """
    projects_path = _projects_path(_registry_root())
    registry = _load_registry(projects_path)
    if len(registry) != 1:
        raise RuntimeError(
            f"expected exactly one registered project in {projects_path}, found {len(registry)}"
        )
    return next(iter(registry.values()))


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
    4b. Else if the done breadcrumb was present (#FIX3) → a clean advance:stop completion that never
       advances; finalize the stage sticky ✅ done via a fail-soft ``GithubClient`` and return.
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
        # Resolve the store root from $KANBAN_ROOT (#1 km-root fix); None → ~/.kanban (DESIGN §4.1).
        store = FsStateStore(resolve_kanban_root())
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

        # 4. The agent advanced its own card: the daemon's ✅-on-advance finalize (8.1.e) already
        #    flipped the LEFT stage to ✅ done. Leave the sticky untouched (the ✅/⚠️ split — the
        #    breadcrumb decided). purge_ticket already purged the breadcrumb above, so no explicit
        #    clear_agent_advance is needed.
        if advanced:
            print(
                f"{_PROG}: ticket #{issue} advanced; runtime record removed "
                "(slot freed, breadcrumb consumed), per-issue budgets preserved, sticky kept ✅."
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
            try:
                entry = _resolve_entry()
                client = GithubClient(load_token(), project_id=entry.project_id, repo=entry.repo)
                header = header_from_state(
                    asdict(state), issue, stage, "done", finished=fmt_timestamp(now)
                )
                upsert_stage_comment(client, issue, stage, header=header, now=now)
            except Exception as exc:  # noqa: BLE001 — fail-soft: a finalize error never breaks session-end.
                print(
                    f"{_PROG}: warning: could not finalize ✅ done sticky for #{issue}: {exc}",
                    file=sys.stderr,
                )
            print(
                f"{_PROG}: ticket #{issue} done (clean completion, no advance); runtime record "
                "removed (slot freed), per-issue budgets preserved, sticky finalized ✅."
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
            client = GithubClient(load_token(), project_id=entry.project_id, repo=entry.repo)
            # The widened TicketState (8.1.d) makes the ⚠️ sticky carry the SAME metadata bullets
            # the PoC rendered (full parity) — build the header via header_from_state, never a bare
            # HeaderInfo. asdict converts the frozen dataclass to the mapping header_from_state reads.
            header = header_from_state(
                asdict(state), issue, stage, "interrupted", finished=fmt_timestamp(now)
            )
            upsert_stage_comment(client, issue, stage, header=header, now=now)
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
