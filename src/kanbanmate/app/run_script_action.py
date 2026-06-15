"""The mechanical run-script command action (DESIGN §11).

Extracted from :mod:`kanbanmate.app.actions` (ceiling-relief split, mirroring the earlier
:mod:`kanbanmate.app.bounce` extraction): once the trust-audit fixes landed, ``actions.py`` reached
the 1000-LOC hard ceiling, so the self-contained :class:`RunScriptAction` lifts out cleanly.

The class is the COMMAND OBJECT a RUN_SCRIPT verdict carries; the PRODUCTION routing happens in
:func:`kanbanmate.app.transition_step.process_transition` (which reads the fields and routes via
:func:`kanbanmate.app.script_route.route_script_verdict`). The :meth:`RunScriptAction.execute`
method is a LEGACY log-only fallback the production path does NOT call — retained only for the
standalone unit tests that exercise the fail-soft subprocess seam (minor (e)).

It is RE-EXPORTED from :mod:`kanbanmate.app.actions` (an explicit assignment at the bottom of that
module) so every existing ``from kanbanmate.app.actions import RunScriptAction`` keeps resolving
unchanged — the move is purely a ceiling-relief split, not an API change.

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` (DESIGN §3.2). This module names
only the pure :class:`~kanbanmate.core.domain.Ticket` and the adapter bundle
:class:`~kanbanmate.app.actions.Deps` (imported top-level — ``actions`` defines ``Deps`` before it
re-imports this class at its own module bottom, so there is no import cycle).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from kanbanmate.app.actions import Deps
from kanbanmate.core.domain import Ticket

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunScriptAction:
    """Run a mechanical (no-LLM) transition script and report its exit code (DESIGN §11).

    Ported from the mechanical-runner half of the PoC ``runner.py`` ``_apply_script``
    (L595-622). A ``run_script`` transition (e.g. ``check-pr-ready.sh``) spends no agent
    session: it runs a plain subprocess in the ticket's worktree and reports ``(exit_code,
    output)``. The subprocess lives in the workspace adapter (the L2 seam), so this action stays
    ``subprocess``-free — it calls :meth:`~kanbanmate.ports.workspace.Workspace.run_transition_script`.

    The dataclass is the COMMAND OBJECT a RUN_SCRIPT verdict carries (``script`` / ``on_fail`` /
    ``advance`` / ``to_column``): :func:`kanbanmate.app.transition_step.process_transition` reads
    those fields and routes the verdict via :func:`kanbanmate.app.script_route.route_script_verdict`
    (running the script through :func:`run_check_script` under the watchdog). The :meth:`execute`
    method below is a LEGACY log-only fallback (minor (e)) — the production RUN_SCRIPT path does NOT
    call it (it routes through ``transition_step`` directly); it is retained only for the standalone
    unit tests that exercise the fail-soft subprocess seam. It records the verdict by logging only
    and performs NO routing.

    Attributes:
        ticket: The ticket whose worktree roots the run.
        script: The script path to run (relative to the clone, or absolute).
        on_fail: The transition's ``on_fail`` policy (routed by ``transition_step``).
        advance: The transition's ``advance`` directive (routed by ``transition_step``).
        to_column: The transition's destination column (carried for the advance).
    """

    ticket: Ticket
    script: str
    on_fail: str = ""
    advance: str = "stop"
    to_column: str = ""

    def execute(self, deps: Deps) -> None:
        """Discover the worktree branch, build the env, and run the script (log-only fallback).

        Args:
            deps: The adapter bundle to act through.
        """
        issue = self.ticket.issue_number
        if issue is None:
            return
        try:
            # Discover the per-ticket worktree branch (idempotent read via the workspace port);
            # a fresh detached worktree reports ``None`` (mapped to "" for the env var).
            branch = deps.workspace.discover_branch(issue) or ""
            # Port _script_env: the check scripts hard-require KANBAN_REPO + KANBAN_BRANCH (their
            # ``: "${KANBAN_REPO:?}"`` guards exit 1 without them). KANBAN_REPO is the board repo
            # slug threaded onto Deps; KANBAN_BRANCH is the discovered worktree branch.
            env = {"KANBAN_REPO": deps.repo, "KANBAN_BRANCH": branch}
            exit_code, output = deps.workspace.run_transition_script(issue, self.script, env)
        except Exception:
            # Fail-soft: a wedged/raising runner is logged, never raised out of the tick.
            logger.exception("run_script '%s' failed for #%s; continuing", self.script, issue)
            return
        # Record the verdict (exit 0 vs non-zero) by logging only — the production routing owns the
        # board moves; this fallback never moves the card.
        logger.info(
            "run_script '%s' for #%s exited %d (advance=%r on_fail=%r); output: %s",
            self.script,
            issue,
            exit_code,
            self.advance,
            self.on_fail,
            output.strip(),
        )
