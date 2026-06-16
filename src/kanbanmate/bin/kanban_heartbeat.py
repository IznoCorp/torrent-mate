"""Agent liveness heartbeat hook: refresh a running ticket's heartbeat (DESIGN §8.3, PoC #67).

Baked by :class:`~kanbanmate.app.actions.LaunchAction` into each worktree's
``.claude/settings.json`` as a **PostToolUse hook** with matcher ``"*"`` — a command string
``kanban-heartbeat <issue>`` with the issue baked in by the dispatcher (DESIGN §8.3). It therefore
fires after *every* tool the agent uses, so an agent that keeps working never stales out of the
reaper's ``HEARTBEAT_TTL`` window. An agent that emits **no** tool for the whole TTL (dead/hung)
goes silent and is reaped by the tick's reap step (:func:`~kanbanmate.app.tick._reap_stale_agents`).

Hard contracts of this shim (DESIGN §8.3, all three enforced by :func:`main`):

* **Always exits 0.** A non-zero PostToolUse hook exit (in particular ``2``) would *block* the
  agent's tool use; a heartbeat must never influence the agent, so every path returns ``0``.
* **Import-light cold-start guard.** ``argv[1]`` is parsed to ``int`` *before* importing
  :mod:`kanbanmate`, so a missing/non-int arg short-circuits to ``exit 0`` without paying the
  package-import cost (it fires synchronously after every tool; cold start ~100 ms, never blocks).
  A slow or broken engine import then cannot stall the hot path for a malformed invocation.
* **No resurrection.** :meth:`~kanbanmate.ports.store.StateStore.touch_heartbeat` is a no-op when
  the ticket's state is absent, so a late hook firing *after a Cancel teardown* (§8.2) never
  recreates a torn-down ticket's state. This shim only forwards the call; the semantic lives in the
  store adapter and is reused verbatim here.

stdin (the hook's JSON payload) is intentionally ignored — the issue is baked into argv by the
dispatcher, not read from the payload.
"""

from __future__ import annotations

import sys
import time


def main(argv: list[str] | None = None) -> int:
    """Refresh the heartbeat of the ticket named in ``argv``; always return ``0``.

    The hot path is deliberately tiny: the issue number is parsed *before* importing
    :mod:`kanbanmate` so a malformed (or arg-less) invocation never pays the engine-import cost
    and never stalls on a slow/broken import. With a valid issue, the engine is imported, the
    filesystem store is built from the launching daemon's root (``$KANBAN_ROOT`` when set, else
    ``~/.kanban`` — the km-worktree-helper-root fix, #1), and the heartbeat is refreshed. Every
    failure is swallowed — a missed heartbeat must never block or influence the agent (DESIGN §8.3).

    Args:
        argv: Optional argument vector (excluding the program name); defaults to
            :data:`sys.argv` ``[1:]``. ``argv[0]`` (the first element here) must be the issue
            number; anything else short-circuits to a silent ``exit 0``.

    Returns:
        Always ``0`` — exit 2 would block the agent's tool use and is never emitted.
    """
    raw_argv = sys.argv[1:] if argv is None else argv

    # Cold-start guard (DESIGN §8.3): parse the issue to int BEFORE importing kanbanmate, so a
    # missing/non-int arg short-circuits to exit 0 without the package-import cost. Keeping this
    # branch import-light means a slow or broken engine import cannot stall the hot path for a
    # malformed call — so the leading-``#`` strip (defect 3) is inlined here rather than importing
    # the shared ``parse_issue_arg`` (which would defeat the import-light intent).
    try:
        issue = int(raw_argv[0].strip().lstrip("#"))
    except (IndexError, ValueError):
        return 0  # malformed/arg-less call — fail-soft, no heavy import

    # Bare except: a heartbeat is best-effort. ANY failure (engine import error, unreadable state,
    # filesystem hiccup) is swallowed so the hook never blocks or influences the agent. The import
    # is local to this branch so it only runs once a valid issue is in hand.
    try:
        from kanbanmate.bin._pin import helper_store

        # Root-aware exactly like the other write-capable helpers (kanban-done / kanban-move /
        # kanban-progress / kanban-session-end): honour ``$KANBAN_ROOT`` AND the project pin —
        # both exported into the agent's worktree env (actions._agent_command) — so this PostToolUse
        # hook writes the heartbeat under the SAME per-project sub-root the daemon reaper reads, not
        # the hardcoded ~/.kanban (the km-agent "never_refreshed" root cause #1, extended to
        # multi-project §3.2). N=1 → the bare runtime root, byte-identical.
        store = helper_store()
        # touch_heartbeat is no-resurrection: a no-op when state/<issue>.json is absent (e.g. after
        # a Cancel teardown), so a late hook never recreates a torn-down ticket's state (§8.3).
        store.touch_heartbeat(issue, time.time())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — fail-soft is the whole point (DESIGN §8.3)
        pass
    return 0  # ALWAYS exit 0 — never block/influence the agent (DESIGN §8.3)


if __name__ == "__main__":
    sys.exit(main())
