"""Agent helper: move a ticket's card to a non-triggering column via the intent queue (DESIGN §8).

``kanban-move <issue> <column> [--no-wait]`` advances a ticket's Status to ``column`` by **enqueuing
a ``move`` intent** into the SAME ``~/.kanban/intents/`` queue the operator ``kanban move`` uses
(0.4.0 move-unification). The daemon is the SOLE board writer: it drains the intent, derives
agent-authority from its launch bookkeeping (the issue is in the running set), re-validates the
guardrails (non-triggering destination / Merge deny / R1 own-ticket / wildcard-aware re-fire), then
applies the move + advances the diff baseline (so the move never re-fires a launch). ``column`` may be
given as either the stable column ``key`` or its human-readable ``name`` — both resolve locally to a
canonical column KEY, which is what the daemon validates against.

**Why an intent, not a direct GitHub call.** Pre-0.4.0 this helper called
:meth:`~kanbanmate.adapters.github.client.GithubClient.move_card` directly — a SECOND board-write
path bypassing the audited intent queue. Routing the agent move through the queue gives ONE write
path with uniform daemon-derived authority (the intent's ``caller`` field is advisory ONLY — the
daemon NEVER trusts it). The helper is now **network-free** (no GitHub client, no token).

**Guardrails the helper keeps (two layers — daemon-side is authoritative).**

* **R1 own-ticket (layer 1).** :func:`~kanbanmate.bin._pin.check_pin` refuses a worktree pinned to a
  different issue BEFORE any write; the daemon's ``validate_intent(..., launching_issue=intent.issue)``
  re-enforces R1 (layer 2).
* **Anti-loop / non-triggering destination (cheap pre-flight, UX only).** A fast launch-target refusal
  (DESIGN §8.0.5) fails fast with a clear message before enqueuing — but it is advisory; the daemon's
  wildcard-aware ``validate_intent`` is authoritative (it also catches ``(*, to)`` wildcards the static
  launch-target set misses).
* **Merge deny.** Enforced daemon-side (``validate_intent`` rejects an agent move into ``Merge``).

**Advance breadcrumb (load-bearing, synchronous — ONLY on a CONFIRMED move).** The helper writes the
advance breadcrumb (:meth:`~kanbanmate.ports.store.StateStore.record_agent_advance`) SYNCHRONOUSLY,
keyed by the ISSUE number, BEFORE ``claude`` exits — but ONLY on the ``--wait`` (default) path, after
the daemon confirms a terminal ``done``/timeout result, NEVER under ``--no-wait``. It MUST stay
written here (not by the daemon drain), because ``bin/kanban_session_end.py`` reads it to pick the
✅(advanced)/⚠️(died) split and races the asynchronous daemon poll — a daemon-written breadcrumb could
land AFTER the REPL exited → ⚠️ mis-finalize. Its meaning is "the agent REQUESTED its own advance and
the daemon ACCEPTED it" (a confirmed move), which is exactly what the ✅/⚠️ split needs.

**Why ``--no-wait`` drops NO breadcrumb (the false-✅ fix).** Under ``--no-wait`` the helper returns
the moment the intent is enqueued — it never polls the daemon's terminal result, so it cannot tell an
accepted move from a daemon-REJECTED one. Writing the optimistic breadcrumb there would leave a FALSE
✅ on a rejected move (session-end would read it as "advanced"). So the breadcrumb is written ONLY on
the ``--wait`` path, gated on a non-rejected (``done``/timeout) result: a confirmed move drops it, a
``rejected`` move drops nothing. ``--wait`` is the default precisely because it is the only path that
can guarantee the breadcrumb's ✅ promise.

This is a leaf entrypoint (DESIGN §3.2): it resolves the per-clone registry + columns + transitions
locally (no GitHub network), enqueues the intent, nudges the daemon, drops the breadcrumb, and
optionally waits for the daemon's terminal result. On bad/missing arguments or a launch-target
destination it fails cleanly (non-zero exit, clear stderr) and never lets an unexpected error crash
the calling agent shell.
"""

from __future__ import annotations

import sys
import time
import uuid

from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.bin._clone_config import load_clone_columns as _load_clone_columns
from kanbanmate.bin._clone_config import load_clone_transitions as _load_clone_transitions
from kanbanmate.bin._clone_config import resolve_entry as _resolve_entry
from kanbanmate.bin._pin import check_pin, helper_store_root, parse_issue_arg
from kanbanmate.core.domain import Column

# The three per-clone config loaders (``_resolve_entry`` / ``_load_clone_columns`` /
# ``_load_clone_transitions``) were LIFTED into :mod:`kanbanmate.bin._clone_config` so the
# session-end auto-advance backstop (hybrid flow) shares ONE source of truth. They are re-imported
# under their original private names here for BACK-COMPAT (existing tests import them off this
# module), keeping ``kanban-move`` small under the 1000-LOC ceiling. ``__all__`` lists them so the
# re-export is EXPLICIT (mypy's no-implicit-reexport under strict).
__all__ = [
    "_load_clone_columns",
    "_load_clone_transitions",
    "_resolve_entry",
    "main",
    "resolve_target_column",
]

_PROG = "kanban-move"

#: Result states that END the ``--wait`` poll (the daemon wrote a terminal outcome). Mirrors
#: ``cli/move._TERMINAL_STATES``.
_TERMINAL_STATES: frozenset[str] = frozenset({"done", "rejected"})

#: The agent ``--wait`` budget. Kept short (well under the prompt-delivery budgets): with the daemon
#: nudge (0.4.0) the drain happens within ~1 tick, so the wait resolves near-instantly; a timeout is
#: benign (the daemon still applies the move) but lets the agent get a definitive answer.
_WAIT_TIMEOUT_SECONDS = 15.0
_WAIT_POLL_SECONDS = 0.5


def resolve_target_column(columns: dict[str, Column], target: str) -> Column:
    """Resolve a CLI ``target`` (a column ``key`` *or* ``name``) to its :class:`Column`.

    The operator/agent may name the destination by either its stable ``key`` (e.g.
    ``"Backlog"``) or its human-readable ``name`` (e.g. ``"In Progress"``). Both map to
    the same column.

    Args:
        columns: The loaded column model (keyed by column ``key``).
        target: The destination column, given as a ``key`` or a ``name``.

    Returns:
        The matching :class:`Column`.

    Raises:
        KeyError: When ``target`` matches no column key or name.
    """
    if target in columns:
        return columns[target]
    for column in columns.values():
        if column.name == target:
            return column
    known = ", ".join(sorted(columns)) or "(none)"
    raise KeyError(f"unknown column {target!r}; known columns: {known}")


def _parse_argv(raw_argv: list[str]) -> tuple[int, str, bool] | int:
    """Parse ``<issue> <column> [--no-wait]`` into ``(issue, target, wait)`` or a usage exit code.

    The ``--no-wait`` flag may appear before or after the positionals. ``--wait`` is the default
    (the agent gets a definitive answer + the breadcrumb-cleanup-on-reject safety).

    Args:
        raw_argv: The argument vector (excluding the program name).

    Returns:
        ``(issue, target, wait)`` on success, or an integer exit code (``2``) on a usage error
        (the caller has already printed the message).
    """
    wait = True
    positionals: list[str] = []
    for token in raw_argv:
        if token in ("--no-wait", "--no_wait"):
            wait = False
        elif token == "--wait":
            wait = True
        else:
            positionals.append(token)
    if len(positionals) != 2:
        print(f"usage: {_PROG} <issue> <column> [--no-wait]", file=sys.stderr)
        return 2
    try:
        issue = parse_issue_arg(positionals[0])
    except ValueError:
        print(f"{_PROG}: issue must be an integer, got {positionals[0]!r}", file=sys.stderr)
        return 2
    return issue, positionals[1], wait


def main(argv: list[str] | None = None) -> int:
    """Entry point: ENQUEUE a move of a ticket's card to a non-launch-target column (0.4.0).

    Resolves the single registered project, loads the clone's column model (name→key) and its
    transition whitelist, and **refuses** (cheap pre-flight, DESIGN §8.0.5) when the resolved target
    is a launch-transition target — BEFORE enqueuing. For any other target it enqueues a ``move``
    intent (``caller="agent"``, advisory) into the SAME ``intents/`` queue the operator uses, nudges
    the daemon (so it drains near-instantly), and — with ``--wait`` (default) — polls the daemon's
    terminal result, writing the advance breadcrumb ONLY on a confirmed (non-rejected) outcome so a
    refused move leaves no false ✅-signal. Under ``--no-wait`` it returns immediately after the
    enqueue and writes NO breadcrumb (it cannot confirm the move, so it promises nothing). The daemon
    is the SOLE board writer; it re-validates the authoritative guardrails under agent-authority.

    Failure handling: a usage error exits ``2``; a launch-target destination, a pin mismatch, a
    daemon rejection, or any wiring failure is reported to stderr and exits ``1`` — never a traceback
    that would crash the calling agent.

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``. Expects ``<issue> <column> [--no-wait]``.

    Returns:
        ``0`` on a successful enqueue (or a benign ``--wait`` timeout / ``done`` result), ``2`` on a
        usage error, ``1`` on a launch-target destination, a pin mismatch, a daemon rejection, or any
        other failure.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    parsed = _parse_argv(raw_argv)
    if isinstance(parsed, int):
        return parsed
    issue, target, wait = parsed

    # Pin enforcement (R1, §29.1, layer 1): refuse a mismatched issue when the worktree is pinned
    # (absent pin → unpinned operator use). Checked BEFORE any write so no intent is ever enqueued.
    pin_error = check_pin(issue)
    if pin_error is not None:
        print(f"{_PROG}: {pin_error}", file=sys.stderr)
        return 1

    try:
        entry = _resolve_entry()
        columns = _load_clone_columns(entry)
        # Resolve the CLI target (a key OR a human name) to its Column so we enqueue a canonical
        # column KEY — the same key the daemon's validate_intent tests membership against.
        column = resolve_target_column(columns, target)
        launch_targets = _load_clone_transitions(entry).launch_target_columns()
        # Cheap pre-flight anti-loop guard (DESIGN §8.0.5, UX only): an agent may NEVER move a card
        # into a launch-transition target — re-entering one re-fires its prompt-bearing transition
        # and forms an orchestration loop. This fails fast with a clear message BEFORE enqueuing; the
        # daemon's wildcard-aware validate_intent is the AUTHORITATIVE check (it also catches
        # ``(*, to)`` wildcards the static launch-target set misses).
        if column.key in launch_targets:
            print(
                f"{_PROG}: refusing to move #{issue} into "
                f"{column.name!r} (anti-loop, DESIGN §8.0.5) — a launch-transition target; "
                f"agents may only move cards into non-launch columns",
                file=sys.stderr,
            )
            return 1

        # Enqueue the move intent into the SAME per-project queue the daemon drains. The store is
        # rooted at the per-project sub-root when the worktree is project-pinned (multi-project §3.2),
        # else the bare runtime root (#1 km-root fix; N=1 byte-identical). The NUDGE the enqueue bumps
        # is wired to the runtime root, so the single daemon wakes regardless of which project moved.
        # No item_id read is needed — the daemon resolves issue → item_id from its snapshot in
        # _execute_move. The module-scoped ``FsStateStore`` is used so tests can monkeypatch it.
        _store_root, _nudge_root = helper_store_root()
        store = (
            FsStateStore(_store_root)
            if _nudge_root is None
            else FsStateStore(_store_root, nudge_root=_nudge_root)
        )
        intent_id = uuid.uuid4().hex[:12]
        store.enqueue_intent(
            intent_id,
            {
                "kind": "move",
                "issue": issue,
                "args": {"to_col": column.key},  # column KEY, not name (daemon validates the key)
                "requested_at": time.time(),
                "caller": "agent",  # ADVISORY only — the daemon derives authority from its bookkeeping
            },
        )
        # Nudge the daemon so it wakes from its inter-tick sleep and drains this intent near-instantly
        # (0.4.0). Best-effort (the method swallows failures → normal-interval cadence). CONVENTION:
        # every enqueue_intent is paired with nudge_daemon (see also cli/move).
        store.nudge_daemon()

        # Advance breadcrumb: written ONLY on the --wait path, and ONLY for a CONFIRMED (non-rejected)
        # result — see _wait_for_result. Under --no-wait the helper cannot confirm the move landed (it
        # never polls the daemon's terminal result), so writing the optimistic breadcrumb here would
        # leave a FALSE ✅ on a daemon-REJECTED move (session-end reads the breadcrumb as "advanced").
        # The breadcrumb is therefore deferred into the --wait path's confirmed branch; --no-wait drops
        # NOTHING. NO dedup marker is recorded either way (the move must still produce the next poll
        # diff so the daemon reacts to it).
        if wait:
            return _wait_for_result(store, issue=issue, intent_id=intent_id, to_col=column.key)
    except Exception as exc:  # noqa: BLE001 — never crash the caller; report + exit non-zero.
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 1

    print(f"enqueued move of #{issue} -> {column.name} (intent {intent_id})")
    return 0


def _wait_for_result(store: FsStateStore, *, issue: int, intent_id: str, to_col: str) -> int:
    """Poll the daemon's intent result; write the advance breadcrumb ONLY on a confirmed move.

    Blocks up to :data:`_WAIT_TIMEOUT_SECONDS` for a terminal ``done``/``rejected`` result. On
    ``rejected`` it writes NO breadcrumb (the move never landed → no false ✅-signal for session-end),
    prints the rejection reason, and returns ``1``. On ``done`` it writes the advance breadcrumb (the
    confirmed "agent requested + daemon accepted its advance" promise the ✅/⚠️ split reads) and
    returns ``0``. A timeout is benign — the daemon will still apply the move — so it ALSO writes the
    breadcrumb (the move is enqueued + un-rejected; the most likely outcome is acceptance) and returns
    ``0`` with a hint.

    The breadcrumb is written HERE, not at enqueue time, so it is only ever dropped once the move is
    confirmed un-rejected. Under ``--no-wait`` this function is never called, so no breadcrumb is
    written at all (the helper cannot confirm the move there, so it must promise nothing).

    Args:
        store: The state store (the result file lives under its root).
        issue: The moved ticket's issue number (the breadcrumb key).
        intent_id: The enqueued intent's id (its result-file stem).
        to_col: The destination column KEY (for the human messages).

    Returns:
        ``0`` on a ``done`` result or a benign timeout (breadcrumb written), ``1`` on a daemon
        ``rejected`` result (no breadcrumb).
    """
    deadline = time.time() + _WAIT_TIMEOUT_SECONDS
    while time.time() < deadline:
        result = store.load_intent_result(intent_id)
        state = result.get("state") if result else None
        if state in _TERMINAL_STATES:
            detail = str(result.get("detail", "")) if result else ""
            if state == "rejected":
                # The daemon refused the move — write NO breadcrumb so session-end does not read a
                # false ✅ (the move never landed).
                print(f"{_PROG}: move of #{issue} -> {to_col} REJECTED — {detail}", file=sys.stderr)
                return 1
            # CONFIRMED move (``done``) → drop the advance breadcrumb now, keyed by ISSUE (8.1.d).
            _record_advance(store, issue)
            print(f"moved #{issue} -> {to_col} — {detail}".rstrip(" —"))
            return 0
        time.sleep(_WAIT_POLL_SECONDS)

    # Timeout is benign: the daemon still applies the move on a later tick. The move was enqueued and
    # never rejected within the budget, so drop the breadcrumb (the expected outcome is acceptance).
    _record_advance(store, issue)
    print(
        f"enqueued move of #{issue} -> {to_col} (intent {intent_id}); still pending after "
        f"{_WAIT_TIMEOUT_SECONDS:.0f}s — the daemon will apply it shortly"
    )
    return 0


def _record_advance(store: FsStateStore, issue: int) -> None:
    """Drop the advance breadcrumb for ``issue``, warn-not-abort (the move is already enqueued).

    Written SYNCHRONOUSLY (keyed by the ISSUE number, the 8.1.d invariant) on a confirmed/un-rejected
    move so ``bin/kanban_session_end.py`` reads it as ✅ advanced. A breadcrumb-write failure must NEVER
    change the exit code — the move already landed — so it only logs a warning.

    Args:
        store: The state store the breadcrumb is written under.
        issue: The moved ticket's issue number (the breadcrumb key).
    """
    try:
        store.record_agent_advance(issue, now=time.time())
    except Exception as exc:  # noqa: BLE001 — warn-not-abort: the move is already enqueued/confirmed.
        print(
            f"{_PROG}: warning: could not record advance breadcrumb for #{issue}: {exc}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
