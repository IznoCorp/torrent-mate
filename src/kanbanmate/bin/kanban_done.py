"""Agent helper: signal the agent has FINISHED — its terminal step (#1, Option 1).

``kanban-done <issue>`` is the concrete terminal action a launched agent runs as its FINAL step
(replacing the no-op "End the session" prose — see DESIGN §8.x). It drops a persisted DONE
breadcrumb (:meth:`~kanbanmate.ports.store.StateStore.record_agent_done`) keyed by the issue
number. The daemon's reaper consumes it on its next tick: for an ALIVE + IDLE session whose done
breadcrumb is present it cleanly EXITS the REPL (:meth:`~kanbanmate.ports.workspace.Sessions.end_session`)
so ``claude`` exits and the trailing ``; kanban-session-end <issue>`` fires (teardown → the card
flows). Without this signal the interactive REPL idles forever and the slot is never freed.

This is a leaf entrypoint (DESIGN §3.2): a pure local store write, no GitHub network. It is
PIN-aware (R1, §29.1) and FAIL-SOFT: a bad/missing argument exits non-zero with clear stderr and
never crashes the calling agent shell. The store root is resolved from ``$KANBAN_ROOT`` (the
launch injects the launching daemon's root for a non-default daemon — the km-worktree-helper-root
fix); absent/empty falls back to ~/.kanban.
"""

from __future__ import annotations

import sys
import time

from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.bin._pin import check_pin, parse_issue_arg, resolve_kanban_root

_PROG = "kanban-done"


def main(argv: list[str] | None = None) -> int:
    """Record the agent-done breadcrumb for ``<issue>`` (its terminal step).

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

    # Pin enforcement (R1, §29.1): refuse a mismatched issue when the worktree is pinned.
    pin_error = check_pin(issue)
    if pin_error is not None:
        print(f"{_PROG}: {pin_error}", file=sys.stderr)
        return 1

    try:
        # Resolve the store root from $KANBAN_ROOT (#1 km-root fix); None → ~/.kanban default.
        store = FsStateStore(resolve_kanban_root())
        store.record_agent_done(issue, now=time.time())
    except Exception as exc:  # noqa: BLE001 — never crash the caller; report + exit non-zero.
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return 1

    print(f"done #{issue}: the agent signalled completion; the daemon will end the session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
