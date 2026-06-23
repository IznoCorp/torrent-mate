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

    print(
        f"route #{issue}: lane {lane!r} recorded; the engine will move the card to its lane entry."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
