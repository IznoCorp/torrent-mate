"""Command-pattern actions: the imperative side-effects of one tick (DESIGN §3.3).

:func:`kanbanmate.core.decide.decide` produces a pure :class:`~kanbanmate.core.domain.Action`
describing *what* to do; this module holds the four command objects that know *how* to do it.
Each action carries only its own ``Ticket`` and is executed against an injected :class:`Deps`
bundle, so the actions speak exclusively to ``ports`` Protocols and never name a concrete
adapter (that is :mod:`kanbanmate.app.wiring`'s job).

The behaviours are ported from the PoC ``engine/launch.py`` (LaunchAction),
``engine/teardown.py`` (TeardownAction / ResetAction), and ``engine/reaper.py`` (the reap step
that the tick wraps in a TeardownAction). The PoC's n8n / webhook-payload / HMAC bits are
dropped entirely — the polling diff is the only ingress now (DESIGN §3.1).

Layering: ``app`` may import ``core``, ``ports`` and ``adapters`` but MUST NOT import ``cli``
or ``daemon`` (DESIGN §3.2). These actions import only ``core`` + ``ports``.
"""

from __future__ import annotations

import logging
import shlex
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from kanbanmate.adapters.perms import (
    KANBAN_BIN_RELDIR,
    ensure_manual_merge_mode,
    materialise_settings,
    provision_worktree_bin,
    provision_worktree_skills,
    write_issue_pin,
)
from kanbanmate.adapters.workspace.worktree import wip_branch
from kanbanmate.app.stage_signal import (
    _cancel_open_stickys,
    _done_open_stickys,
    upsert_stage_comment,
)
from kanbanmate.core.domain import Ticket
from kanbanmate.core.launch_argv import build_claude_argv, wrap_with_session_end
from kanbanmate.app.prompt_delivery import poll_pane, submit_prompt_with_retries
from kanbanmate.core.body_edit import declares_dependency_on, title_code
from kanbanmate.core.launch_keys import (
    build_sendkeys_sequence,
)
from kanbanmate.core.placeholders import fill
from kanbanmate.core.stage_comment import HeaderInfo, fmt_timestamp
from kanbanmate.core.ticket_fields import parse_ticket_fields
from kanbanmate.app.health_reporter import _NullHealthReporter
from kanbanmate.app.status_reporter import _NullStatusReporter
from kanbanmate.ports.board import (
    BoardReader,
    BoardWriter,
    ProjectHealthReporter,
    ProjectStatusReporter,
    PullRequests,
    Seeder,
)
from kanbanmate.ports.clock import Clock
from kanbanmate.ports.store import StateStore, TicketState, TicketStatus
from kanbanmate.ports.workspace import Sessions, Workspace

logger = logging.getLogger(__name__)

# The default integration base the per-ticket WIP branch is first created off (DESIGN §13). Matches
# the ``Workspace.ensure_worktree`` default; kept here so a config can override it per-repo later.
DEFAULT_BASE = "main"

# The LEGACY/test-only default for ``Deps.profile`` (DESIGN §10). ``docs`` is the minimal floor
# (the kill-switch downgrades every profile to it; an unknown profile name degrades to it). NOTE
# (genesis phase 20): the production launch no longer falls back to ``Deps.profile`` —
# :meth:`LaunchAction._resolve_profile` resolves the profile from the matched TRANSITION's
# ``profile`` ONLY (transitions-only model, DESIGN §8.0.6), so this literal is now DEAD as a live
# launch floor — it is only a back-compat default for the now-unused ``Deps.profile`` field, NOT
# the launch profile. Reconciled ``safe`` → ``docs`` so no stale ``safe`` floor reference remains.
DEFAULT_PROFILE = "docs"

# The status a freshly launched ticket records. The single source of truth is
# :class:`~kanbanmate.ports.store.TicketStatus`; the reaper only ages tickets whose
# ``status`` is ``TicketStatus.RUNNING``.
STATUS_RUNNING: TicketStatus = TicketStatus.RUNNING


@dataclass(frozen=True)
class Deps:
    """Injected adapter bundle the command actions execute against.

    Frozen so an action can never mutate its dependency wiring mid-tick. Every field is a
    ``ports`` Protocol — the concrete adapters are assembled once in
    :func:`kanbanmate.app.wiring.build_deps`. ``base`` and ``agent_command`` are small policy
    knobs threaded through so the launch flow stays a pure function of its inputs.

    Attributes:
        board_writer: Board write side (``move_card`` / ``comment``).
        board_reader: Board read side (``cheap_probe`` / ``snapshot``); held so an action that
            needs a fresh read can use it without a second wiring path.
        workspace: Per-ticket git-worktree management.
        sessions: Detached tmux session lifecycle.
        store: Persisted per-ticket runtime state.
        clock: Wall-clock source (injected for deterministic tests).
        pull_requests: PR close side (Cancel teardown only; DESIGN §8.2). The
            same concrete ``GithubClient`` instance that backs ``board_writer``
            satisfies it, so one client is wired into both ports.
        base: The integration base branch the per-ticket WIP branch is first created off.
        agent_command: DEAD knob (minor (d)). NOTHING reads it: ``LaunchAction._agent_command``
            ALWAYS builds the bare ``claude`` argv via ``build_claude_argv`` (both the prompt-bearing
            AND the ``prompt=None`` paths), so this field is never the launch body. It is retained
            ONLY so existing ``Deps(...)`` constructions and the ``WiringConfig.agent_command``
            threading compile — editing it (or ``agent_command`` in ``config.yml``) changes NOTHING.
            Do NOT add a fallback that consumes it; the bare-claude command is unconditional.
        profile: DEAD knob (minor (d)). The launch resolves its profile from the matched
            TRANSITION's ``profile`` ONLY (:meth:`LaunchAction._resolve_profile`, transitions-only
            model — DESIGN §8.0.6), never from this global. Retained only so existing ``Deps(...)``
            constructions compile; it is unused by every code path. Defaults to ``docs``.
        repo: The board's ``owner/name`` slug, exported as ``KANBAN_REPO`` into a transition
            script's env (:class:`RunScriptAction`; port of the PoC ``_script_env``). Defaulted
            ``""`` so existing constructions compile; the composition root threads
            :attr:`WiringConfig.repo` here (wired with the tick in phase 12.8/12.9).
        session_end_bin: The path to (or name of) the ``kanban-session-end`` shim appended after
            the launched ``claude`` command (``claude … ; kanban-session-end <issue>``). Defaults
            to ``"kanban-session-end"`` (the installed console-script resolves on PATH — see
            ``pyproject [project.scripts]``); a real wiring may pass the absolute installed path.
            Defaulted so existing ``Deps(...)`` constructions compile unchanged.
        kanban_root: The launching daemon's runtime root (e.g. ``~/.kanban-km``). When non-empty it
            is exported as ``KANBAN_ROOT`` on the launched command (:meth:`LaunchAction._agent_command`)
            so the trailing ``; kanban-session-end`` AND the agent's kanban-* helpers
            (``kanban-done`` / ``kanban-move`` / …) target the CORRECT root rather than the hardcoded
            ``~/.kanban`` (the km-worktree-helper-root bug, #1). Empty (the default daemon) leaves the
            command line byte-identical. Threaded from :attr:`WiringConfig.kanban_root`. Defaulted
            ``""`` so existing ``Deps(...)`` constructions compile unchanged.
        config_dir: The project's ``.claude`` directory — the source of
            ``skills``/``commands``/``agents`` the launch COPIES into the worktree via
            :func:`~kanbanmate.adapters.perms.provision_worktree_skills` so the agent resolves
            the ``/implement:*`` skills its column prompt invokes (they live in the gitignored
            config repo, absent from the clone checkout). An empty ``config_dir`` skips
            provisioning (offline tests / no config). Threaded from
            :attr:`WiringConfig.config_dir` (registry → wiring → here). Defaulted ``""`` so
            existing ``Deps(...)`` constructions compile unchanged.
        status_reporter: The rolling project status-update side of the board (the live dashboard,
            phase-24 §24.3). The same concrete ``GithubClient`` instance that backs
            ``board_writer`` satisfies :class:`~kanbanmate.ports.board.ProjectStatusReporter`, so
            one client is wired into this slot too. Consumed ONLY by
            :func:`kanbanmate.app.status_reporter.report_status` (the tick's fail-soft last step);
            tests stub it. Defaulted to a no-op reporter (:class:`_NullStatusReporter`) so existing
            ``Deps(...)`` constructions compile unchanged and a tick without a real reporter simply
            posts nothing.
        health_reporter: The per-card Health single-select side of the board (the custom
            chip carrying the operator's vocabulary — health-field). The same ``GithubClient``
            backs it; consumed only by :func:`kanbanmate.app.health_reporter.apply_health`.
            Defaulted to a no-op so existing constructions compile.
        project_id: The board's ``ProjectV2`` node id, threaded onto ``Deps`` so the status
            reporter can ``create_status_update`` on it (the reporter is the only consumer; the
            board client already holds its own copy for read/move). Threaded from
            :attr:`WiringConfig.project_id`. Defaulted ``""`` so existing ``Deps(...)`` constructions
            compile unchanged (an empty id only matters when a real reporter is wired).
        sleeper: The blocking-sleep boundary the launch's trust/ready poll waits on between
            ``capture-pane`` snapshots (phase-25 §25.1; PoC ``poll_trust_dialog`` ``sleeper=``).
            Production wires :func:`time.sleep`; tests inject a no-op so the bounded poll runs
            offline without real waiting. Defaulted to :func:`time.sleep` so existing ``Deps(...)``
            constructions compile unchanged.
    """

    board_writer: BoardWriter
    board_reader: BoardReader
    workspace: Workspace
    sessions: Sessions
    store: StateStore
    clock: Clock
    pull_requests: PullRequests
    base: str = DEFAULT_BASE
    agent_command: str = "claude"
    profile: str = DEFAULT_PROFILE
    repo: str = ""
    session_end_bin: str = "kanban-session-end"
    # The launching daemon's runtime root, exported as KANBAN_ROOT on the launched command so the
    # agent's helpers target the CORRECT root (km-root bug, #1; see the docstring). Empty → the
    # default ~/.kanban daemon needs no override. Threaded from WiringConfig.kanban_root.
    kanban_root: str = ""
    config_dir: str = ""
    # The rolling status-update reporter + the board id it posts on (phase-24 §24.3). Defaulted to
    # a no-op reporter so existing constructions compile and a tick with no real reporter is inert.
    status_reporter: ProjectStatusReporter = field(default_factory=lambda: _NullStatusReporter())
    # The per-card Health single-select reporter (health-field); see the docstring above.
    health_reporter: ProjectHealthReporter = field(default_factory=_NullHealthReporter)
    project_id: str = ""
    # The issue/project create side (cockpit PR3 ticket_create). The production GithubClient
    # implements Seeder; defaulted to None so existing constructions compile (a tick with no seeder
    # rejects ticket_create rather than crashing).
    seeder: Seeder | None = None
    # The blocking-sleep boundary the launch's trust/ready poll waits on (phase-25 §25.1). Defaulted
    # to time.sleep; tests inject a no-op so the bounded capture-pane poll runs offline.
    sleeper: Callable[[float], None] = time.sleep


@dataclass(frozen=True)
class LaunchAction:
    """Start a Claude Code agent for a ticket that entered an agent column.

    Ported from the PoC ``engine/launch.py`` ``start_session`` (the n8n/payload bits dropped):

    1. ensure the per-ticket worktree exists on its WIP branch ``kanban/ticket-<n>`` (idempotent);
    2. materialise the permission profile into ``<worktree>/.claude/settings.json`` (DESIGN
       §10) so the agent boots under a pinned mode + concrete allow/deny — merge stays
       human-only, force-push and history rewrite are denied;
    3. launch a detached tmux session ``ticket-<n>`` running the agent command in that worktree;
    4. persist the running :class:`TicketState` (session id, item id, heartbeat=now) so the
       reaper can later find and age the agent;
    5. post a sticky "started" comment when the ticket has an issue number.

    The order matters: the worktree and session exist *before* state is persisted, so a crash
    between steps never records a running ticket with no live session (the reaper would block it
    on the next tick — safe, not silently wrong).

    Per-transition routing (phase 12; delivery restored to PoC parity in phase-25 §25.1). The
    matched whitelist transition's routing is carried on the action itself (NOT on :class:`Deps`,
    which holds only static policy knobs). The launch ALWAYS starts a BARE ``claude`` (no positional
    prompt — :meth:`_agent_command`). When :attr:`prompt` is set, the launch then FILLS it
    (``{{code}}`` / ``{{title}}`` / … substituted via :func:`kanbanmate.core.placeholders.fill`)
    and SEND-KEYS the filled ``/implement:*`` prompt INTO the live REPL (:meth:`_deliver_prompt`,
    after a bounded trust/ready poll) — the headline parity fix (the PoC typed the prompt into the
    agent's own session + pressed Enter; the intervening genesis regression appended it as claude's
    POSITIONAL message, which opened the REPL but never SUBMITTED it, so the agent sat idle and got
    reaped). When :attr:`prompt` is ``None`` the bare ``claude`` session boots without an injected
    first message (back-compat).

    The remaining transition routing (:attr:`script`, :attr:`on_fail`, :attr:`advance`) is carried
    for phase 13's script-gate + auto-advance / on_fail consumption; phase 12 only fills + launches.

    **Transition-only permission resolution (genesis phase 20 — FAIL-LOUD).** The profile the
    agent runs under is resolved by :meth:`_resolve_profile` from the matched **transition**'s
    :attr:`profile` (``transitions.yml``) ONLY — the agent launches AT the transition, so its
    profile comes from the transition (DESIGN §8.0.6). There is NO per-column default tier and NO
    silent global (the PoC model: permissions resolved by the ``(from, to)`` transition, not one
    global ``Deps.profile``).

    When :attr:`profile` is empty the launch FAILS LOUD (:meth:`execute` raises ``ValueError``
    BEFORE any worktree/session is created) — it NEVER silently falls back to :attr:`Deps.profile`
    (which is now a legacy/test-only knob; see :attr:`Deps.profile`). The §10 safety floor is
    intact: the resolved profile still flows through
    :func:`~kanbanmate.adapters.perms.materialise_settings` /
    :func:`~kanbanmate.core.launch_argv.build_claude_argv`, which reject a bypass mode.

    Attributes:
        ticket: The ticket that entered the agent column.
        prompt: The matched transition's launch prompt template. When set, it is FILLED and
            SEND-KEYS'd into the live REPL after launch (the per-transition ``/implement:*`` prompt;
            :meth:`_deliver_prompt`, phase-25 §25.1); ``None`` boots a bare ``claude`` with no
            injected first message.
        script: The matched transition's script (a launch-transition gate, consumed in phase 13).
        profile: The matched **transition**'s permission profile — the SOLE profile source
            (transitions-only model, DESIGN §8.0.6). FAILS LOUD when empty (no column default, no
            silent global; see :meth:`_resolve_profile`).
        permission_mode: The matched transition's ``claude --permission-mode``. Persisted as the
            ticket's ``mode`` (the 🟡 header + finalizers reload it) instead of
            ``pinned_mode(profile)`` when set.
        on_fail: The matched transition's ``on_fail`` policy, threaded for phase 13.
        advance: The matched transition's ``advance`` directive, threaded for phase 13.
    """

    ticket: Ticket
    prompt: str | None = None
    script: str | None = None
    profile: str = ""
    permission_mode: str = "auto"
    on_fail: str = ""
    advance: str = "stop"
    # The retry budget to PERSIST on the launched state. A fresh board-move launch leaves this 0 (a
    # new stage starts with a clean budget); a reaper RELAUNCH (:func:`kanbanmate.app.reaper._try_relaunch`)
    # passes ``state.retries + 1`` so the bumped budget SURVIVES this action's fresh state write —
    # without it ``execute`` would default ``TicketState.retries`` to 0 and silently RESET the reaper's
    # retry budget, defeating ``RETRY_LIMIT`` (a dead session would relaunch forever).
    retries: int = 0

    def _resolve_profile(self) -> str:
        """Resolve the launch profile from the matched transition ONLY (FAIL-LOUD; phase 20).

        Transitions-only model (DESIGN §8.0.6): the agent launches AT the transition, so its
        profile is the matched **transition**'s :attr:`profile` (``transitions.yml``) — there is
        NO per-column default tier. When :attr:`profile` is empty the launch is UNRESOLVED — raise
        so the caller aborts BEFORE creating a worktree/session, rather than silently running under
        a global default (:attr:`Deps.profile` is NOT consulted here — that is the security
        invariant adversarial verification checks).

        Returns:
            The resolved non-empty transition profile name.

        Raises:
            ValueError: When the transition profile is empty (no column default, no silent global
                fallback — the launch must fail loud, DESIGN §10).
        """
        if not self.profile:
            raise ValueError(
                f"LaunchAction for #{self.ticket.issue_number}: no permission profile resolved "
                "— the matched transition's `profile` is not set (DESIGN §8.0.6: the profile "
                "lives on the transition; DESIGN §10: no silent global default; set one in "
                "transitions.yml)"
            )
        return self.profile

    def execute(self, deps: Deps) -> None:
        """Run the launch flow against the injected dependencies.

        Args:
            deps: The adapter bundle to act through.
        """
        issue = self.ticket.issue_number
        # Worktrees/sessions are keyed by issue number throughout (DESIGN §3.3); a draft item
        # with no issue cannot get a worktree, so there is nothing to launch.
        if issue is None:
            return

        # The tmux session NAME stays the Sessions correlation key (``ticket-<n>``). The CLAUDE
        # session id is the generated uuid below — the two are deliberately distinct.
        session_name = f"ticket-{issue}"
        now = deps.clock.now()

        # Generate the claude session uuid up front: it is the SINGLE SOURCE OF TRUTH for
        # resumability (``claude --resume <uuid>``, DESIGN §8.3) — NO file scan (port of PoC
        # launch.py:219). It is both passed into the ``claude --session-id`` argv AND persisted as
        # the ``TicketState.session_id`` so the reaper can relaunch the exact session.
        session_uuid = str(uuid.uuid4())

        # Transition-only profile resolution (phase 20, DESIGN §8.0.6): the agent launches AT the
        # transition, so its profile is the matched transition's ``profile``. An unresolved (empty)
        # profile FAILS LOUD here — BEFORE any worktree/session is created — rather than silently
        # running under a global ``Deps.profile`` default. ``_resolve_profile`` raises when empty.
        profile = self._resolve_profile()

        # 1. Idempotent worktree on the per-ticket WIP branch ``kanban/ticket-<n>`` (DESIGN §13 —
        #    reused so the prior stage's committed docs/features/<codename>/ artifacts are present).
        worktree = deps.workspace.ensure_worktree(issue, base=deps.base)
        # 2. Materialise the permission profile into the worktree BEFORE the session starts, so
        # the agent reads its pinned mode + concrete allow/deny on startup (DESIGN §10: merge is
        # human-only; force-push / history rewrite denied across all profiles). Thread the
        # per-transition ``permission_mode`` (minor (a)) so the worktree's ``defaultMode`` matches
        # the mode the launch command emits — not the profile's hardwired pinned default.
        materialise_settings(profile, worktree, issue=issue, permission_mode=self.permission_mode)
        # 2b. Provision the project's skills/commands/agents into the worktree (COPY, not symlink)
        # so the agent can resolve the ``/implement:*`` skills its column prompt invokes (an empty
        # ``deps.config_dir`` makes this a no-op). Then PIN IMPLEMENTATION.md to ``**PR merge**:
        # manual`` so an auto-triggered pr-review hands off to a human (DESIGN §10: merge is human-
        # only), and PIN the worktree to THIS issue (``.claude/kanban-issue``, §29.1): the kanban-*
        # helpers read it and refuse a mismatched issue (R1 — an agent only touches its own ticket).
        provision_worktree_skills(worktree, deps.config_dir)
        # 2c. Provision the engine's OWN kanban-* helper console scripts as symlinks under
        # ``<worktree>/.claude/kanban-bin/`` (phase 38). The agent's tmux session inherits the
        # shell's ``pyenv global`` python, which may be a DIFFERENT interpreter than the one running
        # the daemon — and pyenv shims dispatch per ACTIVE version, so a helper added after that
        # install (the live ``kanban-update-body`` case) exits 127 there. Prepending this dir to the
        # agent's PATH (see ``_agent_command``) pins every helper to the engine's interpreter,
        # regardless of the agent's pyenv-global version. FAIL-SOFT: an unresolved helper is skipped.
        provision_worktree_bin(worktree)
        ensure_manual_merge_mode(worktree)
        write_issue_pin(worktree, issue)
        # 3. Build the BARE agent command: the real ``claude --session-id <uuid> --permission-mode
        # <mode> --add-dir <worktree> ; kanban-session-end <issue>`` line (build_claude_argv +
        # wrap_with_session_end). The prompt is NO LONGER a positional in this command — see 4b
        # (phase-25 §25.1): the PoC launched BARE claude, then send-keys the prompt INTO the REPL.
        command = self._agent_command(deps, issue, worktree, session_uuid)
        # 3b. FILL the prompt BEFORE the session is created (minor (c)): the FILL is fail-loud on an
        # unknown placeholder key, and running it AFTER ``sessions.launch`` (the old order) leaked an
        # untracked bare-claude tmux session on a KeyError — the session existed but no state was
        # saved, so the reaper could never own it. Hoisting the fill above the launch means a typo'd
        # token aborts BEFORE any session/state exists (nothing to clean up). ``None`` for a bare
        # (prompt-less) launch — nothing is delivered into the REPL.
        filled_prompt = (
            self._fill_prompt(deps, issue, worktree) if self.prompt is not None else None
        )
        # 4. Launch the agent in a detached tmux session rooted at the worktree. The launch return
        # value is no longer used for session_id — the uuid is the authoritative session id.
        deps.sessions.launch(session_name, str(worktree), command)
        # 4b. PROMPT DELIVERY (phase-25 §25.1, PoC start_session L246-255). The bare ``claude``
        # opened above shows a trust dialog and/or a REPL that is NOT yet ready when launch returns.
        # Composing the prompt as a positional (the old bug) opened the REPL but NEVER submitted the
        # message → the agent sat idle at ``❯`` and got reaped. Instead: POLL capture-pane for the
        # trust dialog OR a ready REPL (bounded, injected sleeper), then SEND-KEYS the PRE-FILLED
        # prompt + Enter INTO the live REPL (a trust-dismiss Enter first iff the dialog was seen). A
        # prompt=None launch (bare claude) delivers nothing — it boots without an injected message.
        if filled_prompt is not None:
            self._deliver_prompt(deps, issue, session_name, filled_prompt)
        # Fresh-session breadcrumb hygiene (#FIX2): a stale done/<issue> breadcrumb (1800s TTL) or
        # end_attempts counter from a PRIOR stage can survive into this launch and make the reaper
        # done-exit THIS fresh agent prematurely. Clear both so the new session's done-exit gate
        # depends ONLY on this session's own kanban-done. Each is independently fail-soft (a clear
        # failure must never abort a launch the agent has already started — the breadcrumb only
        # matters to the NEXT reap tick, which still ages it out at the TTL). Done BEFORE the
        # running-state save so even if the save is the last successful step, the markers are gone.
        try:
            deps.store.clear_agent_done(issue)
        except Exception:
            logger.exception("launch breadcrumb-clear (done) failed for #%s; continuing", issue)
        try:
            deps.store.clear_end_attempts(issue)
        except Exception:
            logger.exception(
                "launch breadcrumb-clear (end_attempts) failed for #%s; continuing", issue
            )
        # 5. Persist the running state so the reaper can age/own the agent. heartbeat=now means
        # a freshly launched agent is never immediately stale on the next reap sweep. The widened
        # state (DESIGN §8.1.d) is the SINGLE SOURCE OF TRUTH the finalizers (✅ advance / ⚠️
        # session-end / ⛔ reaper) reload to render bullet-for-bullet identical terminal headers:
        # the launch column key feeds both the 🟡 header (8.1.c) and the persisted ``stage``, and
        # the same profile/mode/started/worktree feed both the 🟡 header and the persisted state.
        # ``mode`` is the per-transition ``permission_mode`` (phase 12) — defaulted ``"auto"``,
        # which equals ``pinned_mode(<any profile>)`` so the legacy path is byte-identical.
        # session_id semantics: was the tmux NAME (the launch return value); is now the claude
        # ``--session-id`` UUID so ``claude --resume <session_id>`` reattaches the live session
        # (DESIGN §8.3). The tmux NAME stays ``ticket-<n>`` as the Sessions correlation key.
        deps.store.save(
            TicketState(
                issue_number=issue,
                item_id=self.ticket.item_id,
                session_id=session_uuid,
                status=STATUS_RUNNING,
                heartbeat=now,
                stage=self.ticket.column_key,
                profile=profile,
                mode=self.permission_mode,
                started=now,
                worktree=str(worktree),
                # Carry the retry budget (0 for a normal launch; the incremented value for a reaper
                # relaunch) so a relaunch does NOT reset ``retries`` to 0 — defeating RETRY_LIMIT.
                retries=self.retries,
                # Relaunch inputs (phase-25 §25.2, PoC ``launch.py`` "Re-launch inputs persisted"):
                # persist the prompt + script + on_fail + advance so the reaper can rebuild the EXACT
                # LaunchAction and RE-DELIVER the prompt via the 25.1 send-keys path. Without these a
                # reaper relaunch is promptless (an idle agent re-reaped at the TTL). ``mode`` already
                # carries the permission_mode and ``profile`` the resolved profile.
                prompt=self.prompt,
                script=self.script,
                on_fail=self.on_fail,
                advance=self.advance,
                # Persist the ticket title + body (defect 4) so a reaper RELAUNCH rebuilds the Ticket
                # with the REAL fields, not ``ticket-N`` / empty body — otherwise parse_ticket_fields
                # yields empties and the Plan/Prepare prompts force a DESYNC exit on relaunch.
                title=self.ticket.title,
                body=self.ticket.body,
            )
        )
        # 6. Stage-sticky running header (🟡 "in progress", DESIGN §8.1.c). The upsert is
        # fail-soft (it swallows any GitHub error), so signaling never breaks the launch.
        upsert_stage_comment(
            deps.board_writer,
            issue,
            stage=self.ticket.column_key,
            header=HeaderInfo(
                stage=self.ticket.column_key,
                status="running",
                session=session_uuid,
                profile=profile,
                started=fmt_timestamp(now),
                worktree=Path(worktree).name,
                log_hint=f"kanban logs {issue}",
            ),
            now=now,
        )
        # 7. Per-dispatch audit record — the NEW LAST step (port of PoC
        # launch.py:297-309 + audit.append_dispatch). One structured JSON line
        # per dispatch under ``<root>/log/dispatch.jsonl``, carrying the full PoC
        # field set keyed off the locals confirmed in scope above. ``ts=now`` is
        # the injected clock's now (deterministic); the store stamps ``logged_at``
        # with ``time.time()`` so the port stays clock-free. The reaper relaunch
        # reuses this SAME LaunchAction path, so a relaunch ALSO appends a record
        # (faithful: the PoC's launch_next went through start_session too).
        #
        # FAIL-SOFT + LAST: wrapped in its own try/except so an audit-log write
        # failure NEVER breaks a launch — the agent already started, so even a
        # failure here leaves a fully-launched ticket (state saved, 🟡 posted).
        record: dict[str, object] = {
            "issue": issue,
            "repo": deps.repo,
            "to": self.ticket.column_key,
            "permission_profile": profile,
            "session_uuid": session_uuid,
            "worktree": str(worktree),
            "tmux": session_name,
            "ts": now,
        }
        try:
            deps.store.append_dispatch(record)
        except Exception:
            logger.exception("dispatch-audit append failed for #%s; continuing", issue)

    def _agent_command(self, deps: Deps, issue: int, worktree: Path, session_uuid: str) -> str:
        """Assemble the BARE ``claude`` command line launched inside the agent's tmux session.

        Builds the real argv via :func:`kanbanmate.core.launch_argv.build_claude_argv`
        (``claude --session-id <uuid> --permission-mode <mode> --add-dir <worktree>``) and wraps it
        with :func:`~kanbanmate.core.launch_argv.wrap_with_session_end` so the line ends in
        ``; kanban-session-end <issue>`` (the ``;`` always fires the slot-release on exit, DESIGN
        §8.3).

        **The prompt is NO LONGER part of this command (phase-25 §25.1).** The PoC launched a BARE
        ``claude`` and send-keys the filled prompt INTO the live REPL (:meth:`_deliver_prompt`); the
        intervening genesis regression appended the filled prompt as claude's POSITIONAL first
        message — which opened the REPL but never SUBMITTED it (no Enter inside the REPL), so the
        agent sat idle and got reaped. Removing that positional append restores PoC fidelity: the
        launched command is bare on BOTH the prompt-bearing and ``prompt=None`` paths, and the
        prompt is delivered separately by :meth:`_deliver_prompt`.

        The ``--permission-mode`` value is :attr:`permission_mode` (the per-transition mode phase
        12 routes AND persists as :attr:`TicketState.mode`), so the argv flag, the persisted state,
        and phase-12 behaviour stay consistent. PLAN-DRIFT (anticipated): the plan's literal
        ``mode = pinned_mode(deps.profile)`` predates phase 12 — using ``self.permission_mode``
        here keeps the launch consistent with the value already persisted on the state.

        Args:
            deps: The adapter bundle (its ``session_end_bin`` is injected into the wrapper).
            issue: The ticket issue number (feeds the ``; kanban-session-end <issue>`` wrapper).
            worktree: The per-ticket worktree path (``--add-dir`` target).
            session_uuid: The generated claude session uuid (``--session-id`` value).

        Returns:
            The bare shell command line to run inside the session (no positional prompt).
        """
        # ``profile`` is guard-only here (build_claude_argv rejects a bypass profile); it is NOT
        # emitted into the argv. ``permission_mode`` is the per-transition mode (see docstring).
        # Transition-only resolution (phase 20, DESIGN §8.0.6): the matched transition's profile,
        # FAIL-LOUD when empty; NO column default, NO silent ``deps.profile`` global. ``execute``
        # has already called this (so a launch that reaches here always resolves), but
        # ``_agent_command`` re-resolves to stay self-contained.
        profile = self._resolve_profile()
        argv = build_claude_argv(session_uuid, str(worktree), profile, self.permission_mode)
        # NO positional prompt append (phase-25 §25.1). The prompt is delivered into the live REPL
        # by ``_deliver_prompt`` AFTER launch, not composed into the launched command line.
        command = wrap_with_session_end(argv, issue, session_end_bin=deps.session_end_bin)
        # PATH prefix (phase 38): prepend the worktree's kanban-bin symlink dir so BOTH ``claude``
        # AND the trailing ``; kanban-session-end <issue>`` resolve the engine's OWN helper scripts,
        # not whatever ``pyenv global`` python the agent's tmux session inherited (the live-e2e
        # ``kanban-update-body`` 127 case). The dir is provisioned in ``execute`` (step 2c) and holds
        # ONLY kanban-* symlinks. Composing the PATH prefix is an app/adapters concern (it needs the
        # absolute worktree path + the materialised dir), so core/launch_argv stays pure. ``"$PATH"``
        # is left unquoted by shlex.quote (it must EXPAND in the agent's shell); the dir is quoted so
        # a worktree path with spaces stays one segment.
        bin_dir = Path(worktree) / KANBAN_BIN_RELDIR
        path_prefix = f'export PATH={shlex.quote(str(bin_dir))}:"$PATH"; '
        # Inject the daemon's runtime root so the trailing ``; kanban-session-end`` AND the agent's
        # kanban-* helpers target the CORRECT root, not hardcoded ~/.kanban (km-root bug, #1). Only
        # when non-default — the default ~/.kanban daemon keeps a byte-identical command line.
        root_prefix = (
            f"export KANBAN_ROOT={shlex.quote(deps.kanban_root)}; " if deps.kanban_root else ""
        )
        return f"{root_prefix}{path_prefix}{command}"

    def _fill_prompt(self, deps: Deps, issue: int, worktree: Path) -> str:
        """FILL the transition prompt against the launch context (minor (c): hoisted pre-launch).

        Split out of :meth:`_deliver_prompt` so the FILL runs BEFORE ``sessions.launch`` (minor
        (c)): the fill is fail-loud on an unknown placeholder key, and running it after the session
        was created leaked an untracked bare-claude tmux session on a KeyError. Now a typo'd token
        raises here, before any session exists. The context is the SAME one the old order used, so
        every ``{{code}}`` / ``{{title}}`` / ``{{branch}}`` / ``{{script_output}}`` / enrichment
        placeholder resolves identically.

        Args:
            deps: The adapter bundle (the board reader + store feed the enrichment context).
            issue: The ticket issue number (feeds the ``{{code}}`` placeholder).
            worktree: The per-ticket worktree path (its branch feeds ``{{branch}}``).

        Returns:
            The filled prompt string ready to send-keys into the REPL.

        Raises:
            KeyError: When the prompt references an unknown placeholder (fail-loud, pre-launch).
        """
        assert self.prompt is not None  # guarded by the caller; narrows the type for mypy
        ctx = self._launch_context(deps, issue, worktree)
        return fill(self.prompt, ctx)

    def _deliver_prompt(self, deps: Deps, issue: int, session_name: str, filled: str) -> None:
        """Send-keys the PRE-FILLED transition prompt into the live REPL (phase-25 §25.1).

        Ported from the PoC ``start_session`` interactive-delivery tail (launch.py:246-255): a bare
        ``claude`` was launched, then the prompt was typed INTO the REPL and submitted. The FILL now
        happens in :meth:`_fill_prompt` BEFORE the launch (minor (c)), so this only does delivery:

          1. POLL ``capture-pane`` for the trust dialog OR a ready REPL (:meth:`_poll_pane`,
             bounded, injected sleeper) → ``trust_seen``.
          2. SEND-KEYS the ordered :func:`~kanbanmate.core.launch_keys.build_sendkeys_sequence`
             steps via the sessions ``send_text`` primitive: a trust-dismiss Enter iff the dialog
             was seen, then the prompt LITERALLY, then a trailing space, then Enter to submit.

        Called ONLY when :attr:`prompt` is not ``None`` (a bare ``prompt=None`` launch delivers
        nothing).

        Args:
            deps: The adapter bundle (the sessions ``capture`` / ``send_text`` seams + the sleeper).
            issue: The ticket issue number (feeds the post-send undelivered-prompt verification).
            session_name: The tmux session name to poll + type into (``ticket-<n>``).
            filled: The PRE-FILLED prompt to send-keys into the REPL.
        """
        # 2. Bounded poll for the trust dialog / a ready REPL (the I/O loop; the pure per-snapshot
        # verdict is core.launch_keys.classify_pane). An injected sleeper lets tests drive it offline.
        # The poll + post-send verification live in app/prompt_delivery (#11, ceiling extraction).
        trust_seen = poll_pane(deps, session_name)
        # 3. Send the ordered steps into the live REPL via the sessions ``send_text`` primitive: a
        # trust-dismiss Enter iff seen, then the prompt LITERALLY + trailing space, then Enter.
        for step in build_sendkeys_sequence(filled, trust_prompt_seen=trust_seen):
            if step[0] == "enter":
                deps.sessions.send_text(session_name, "Enter", literal=False)
            else:
                deps.sessions.send_text(session_name, step[1], literal=True)
        # 4. SUBMIT-RELIABILITY (submit-retry fix). The single Enter above can be ABSORBED on claude
        # v2.1.x (the REPL renders ``❯`` / ``auto mode on`` a beat before it accepts input), leaving
        # the prompt sitting in the input box — fatal for AUTONOMOUS stages (no human to press Enter →
        # the agent never starts → parks WAITING forever, post-Approach-A). So poll the pane and
        # RE-SEND Enter while the prompt is still pending (bounded); a landed submit stops it with no
        # extra Enter, and an Enter at an emptied box is a harmless no-op. On exhaustion this falls
        # back to the prior WARN + advisory sticky (verify_prompt_delivered), so a genuinely stuck
        # prompt is still surfaced and a good launch is never hard-failed.
        submit_prompt_with_retries(deps, issue, session_name, filled, self.ticket.column_key)

    def _launch_context(self, deps: Deps, issue: int, worktree: Path) -> dict[str, object]:
        """Build the placeholder context the shipped ``/implement:*`` prompts reference.

        Sources what NEW HAS TODAY: ``code`` / ``title`` / ``ticket_body`` from the
        :class:`Ticket`, and ``branch`` from the per-ticket worktree (discovered via the
        workspace port). ``script_output`` (15.7) is sourced from
        :meth:`kanbanmate.ports.store.StateStore.load_script_output` — the last failing
        check's combined stdout+stderr persisted by the script-routing path, or ``""``
        when absent (non-fix-CI launches are unaffected). Staged enrichment:
        ``codename`` / ``design_path`` / ``plan_paths`` are parsed from the
        ticket body via :func:`~kanbanmate.core.ticket_fields.parse_ticket_fields`
        (PoC parity — the Design/Plan agents write ``**codename**:`` /
        ``**design**:`` / ``**plans**:`` markers into the issue). A first-contact
        ticket with no markers fills ``""`` for those keys (back-compat: the
        Design agent does not reference them). ``issue_body`` (the FIRST cross-
        referenced linked-issue body) and ``comments`` (the full comment history,
        joined by ``\n---\n``) are enriched from
        :meth:`kanbanmate.ports.board.BoardReader.issue_context` (PoC parity,
        18.2) — **fail-soft**: a GraphQL error degrades both to ``""`` and logs,
        never breaking the launch. The remaining enrichment keys NEW still cannot
        supply (``dev_repo_path`` / ``base_clone``) are defaulted to ``""`` so
        :func:`fill` does not fail loud on a referenced-but-unsuppliable key (no
        shipped prompt references them). The fail-loud contract still holds for a
        genuine typo: a template token that is NOT a known key (present or
        defaulted) raises ``KeyError``.

        Args:
            deps: The adapter bundle (the workspace port discovers the branch).
            issue: The ticket issue number (the ``{{code}}`` placeholder, as ``#<n>``).
            worktree: The per-ticket worktree path (unused beyond branch discovery here).

        Returns:
            The substitution context mapping for :func:`kanbanmate.core.placeholders.fill`.
        """
        # Discover the worktree's branch (idempotent read): the per-ticket WIP branch
        # ``kanban/ticket-<n>`` (pre create-branch) or ``feat/<codename>`` (post); a still-detached /
        # gone worktree reports ``None`` (mapped to ``""`` for the placeholder).
        branch = deps.workspace.discover_branch(issue) or ""
        fields = parse_ticket_fields(self.ticket.body or "")
        # 18.2: enrich the prompt with the FIRST cross-referenced issue body (``issue_body``, NOT
        # ``ticket_body``) + the ``\n---\n``-joined comment history (timeouts inherited).
        try:
            ctx = deps.board_reader.issue_context(issue)
            issue_body = ctx.linked_issue_body or ""
            # §29.3 direction fix (the #91 poisoning): a body declaring a dependency ON us
            # (``Depends on #<issue>``/``<CODE>``) is a DOWNSTREAM dependent — drop it (not our spec).
            if declares_dependency_on(issue_body, issue=issue, code=title_code(self.ticket.title)):
                issue_body = ""
            comments = "\n---\n".join(ctx.comments)  # PoC join (runner.py:663-704)
        except Exception:
            # A GraphQL hiccup must NOT break a launch — degrade to empty context (fail-soft).
            logger.exception(
                "issue_context enrichment failed for #%s; launching with empty issue_body/comments",
                issue,
            )
            issue_body = ""
            comments = ""
        return {
            # Fill ``{{code}}`` as the BARE issue number (defect 3): every shipped prompt pins
            # helper calls like ``kanban-move {{code}} 'PR/CI'`` to this placeholder, and the
            # kanban-* helpers parse ``int(argv[0])`` — a leading ``#`` makes ``#151`` a bash
            # comment (zero args → usage exit 2) and ``int('#151')`` raises. The helpers ALSO
            # strip a leading ``#`` defensively, but the contract value is the bare int.
            "code": str(issue),
            "title": self.ticket.title,
            "branch": branch,
            "ticket_body": self.ticket.body or "",
            # 15.7: fill from the LAST failing check's output (persisted by 15.6). Not cleared on
            # consume — a reaper relaunch re-reads the SAME failure context; 15.6 refreshes it.
            "script_output": deps.store.load_script_output(issue),
            # issue_body / comments: enriched from deps.board_reader.issue_context(issue)
            # above (PoC parity, 18.2) — the first cross-referenced linked-issue body and the
            # joined comment history; fail-soft to "" on a GraphQL error.
            "issue_body": issue_body,
            "comments": comments,
            # codename / design_path / plan_paths: parsed from the ticket body via
            # parse_ticket_fields (PoC parity, 18.1). The remaining enrichment keys
            # (dev_repo_path / base_clone) are still defaulted to "" — no shipped prompt
            # (e.g. _MERGE_PROMPT) references them, so the empty default is justified.
            "codename": fields["codename"],
            "design_path": fields["design_path"],
            "plan_paths": fields["plan_paths"],
            "base_clone": "",
            "dev_repo_path": "",
        }


@dataclass(frozen=True)
class TeardownAction:
    """Tear down a ticket's machine-side state (Cancel column / Done arrival, DESIGN §8.2).

    Ported from the PoC ``engine/teardown.py`` ``teardown_ticket`` to full parity — the seven
    local steps plus the remote PR close:

    1. kill the tmux session (guarded — ``Sessions.kill`` raises on an absent session);
    2. remove the worktree with ``--force`` (a cancelled worktree is almost always dirty);
    3. force-delete the local feature branch (``git branch -D`` via the workspace seam; skip
       ``""``/``"HEAD"`` AND the per-ticket WIP branch ``kanban/ticket-<n>``, PRESERVED so a
       cancelled ticket's committed design/plan survives — DESIGN §13) — subprocess in the adapter;
    4. release the concurrency slot (idempotent; the fs store also purges the persisted state);
    5. flip any OPEN stage stickies to their terminal status (❌ cancelled, or ✅ done for the
       Done-arrival flavour — DESIGN §8.2.c / phase 28.1);
    6. close the open PR for the branch (KEEP the remote branch — close ≠ delete-ref);
    7. post a final recap comment so the timeline records the teardown.

    Two FLAVOURS share this one path (:attr:`flavour`): ``"cancel"`` (default — ABANDONMENT: ❌
    ``cancelled`` stickies + a Backlog-re-arm recap; the historical behaviour, unchanged) and
    ``"done"`` (the phase-28.1 Done-arrival teardown — the card landed in Done while its agent was
    LIVE, so the work is complete: ✅ ``done`` stickies + a short "moved to Done — agent torn down"
    recap with NO Backlog re-arm; the card STAYS in Done, the tick does NOT move it).

    Every step is **fail-soft** (mirroring the PoC ``_soft`` helper): a single step's failure is
    logged and never aborts the remaining steps. The flow is also **replay-safe** — a second
    teardown destroys nothing and never raises. Replay-safety is ENFORCED at the source (phase
    28.1): the worktree-touching steps (branch discovery + worktree removal) are gated on
    :meth:`~kanbanmate.ports.workspace.Workspace.worktree_exists`, so an ALREADY-GONE worktree is
    SKIPPED rather than producing noisy ``git -C <gone>`` exit-128 ERROR logs. The guard is on the
    SHARED path, so BOTH flavours benefit (the Cancel flavour's earlier e2e finding is fixed too).

    Teardown runs in the dispatcher (no agent, no ``.claude/settings.json``), so the deny-list
    that bans ``git branch -D`` / merges for LAUNCHED AGENTS does not apply — this single
    mechanical transition is the only path that destroys, and it never deletes anything remote
    beyond CLOSING the PR (the remote branch is kept, DESIGN §8.2).

    Attributes:
        ticket: The ticket to tear down.
        keep_budgets: When ``True``, the purge PRESERVES the per-issue budgets
            (``moves/`` rate-limit history + ``retries/`` fix-CI counters) — used
            by the reaper's stale-agent teardown (13.8) so the durable §6
            rate-limit accumulates across reaps. The default ``False`` is the
            exhaustive teardown that the Cancel column uses (the ticket is
            abandoned, so its budgets are dropped too).
        flavour: ``"cancel"`` (default — abandonment wording + ❌ stickies), ``"done"``
            (phase-28.1 Done-arrival — ✅ stickies + a short "moved to Done" recap, NO Backlog
            re-arm), or ``"reap"`` (defect 5 — the reaper's stale-agent park-in-Blocked: kill the
            session + purge state + finalize ⛔ ONLY, NON-DESTRUCTIVE — NO worktree removal, NO
            branch delete, NO PR close, PoC ``reaper._move_to_blocked`` parity). The ``cancel`` and
            ``done`` flavours run every destructive step; ``reap`` SKIPS them so a twice-stalled
            agent never loses unpushed work and its open PR is never closed.
    """

    ticket: Ticket
    keep_budgets: bool = False
    flavour: Literal["cancel", "done", "reap"] = "cancel"

    def execute(self, deps: Deps) -> None:
        """Run the teardown flow against the injected dependencies.

        Each step is wrapped in its own try/except so one failure cannot block
        the remaining cleanup (fail-soft, DESIGN §8.2). The order is chosen so
        independent steps are not gated on prior-step success.

        Args:
            deps: The adapter bundle to act through.
        """
        issue = self.ticket.issue_number
        if issue is None:
            return

        session_name = f"ticket-{issue}"

        # Replay-safety gate (phase 28.1): probe the worktree REGISTRY (``git -C <clone> worktree
        # list``) — NEVER ``git -C <worktree>`` — so an already-removed worktree reports absent
        # WITHOUT the noisy exit-128 "not a working tree" failure. When absent, branch discovery
        # (step 0) + worktree removal (step 2) are SKIPPED (nothing to read/remove). Fail-CLOSED to
        # "exists" on a probe error so a listing hiccup never wrongly skips a real removal.
        try:
            worktree_present = deps.workspace.worktree_exists(issue)
        except Exception:
            logger.exception(
                "teardown step 'worktree_exists' probe failed for #%s; assuming present", issue
            )
            worktree_present = True

        # 0. DISCOVER the worktree branch FIRST — BEFORE the worktree is removed (phase-25 §25.3,
        #    bug D). ``discover_branch`` runs ``git -C <worktree> rev-parse``; reuse it for the
        #    branch delete (step 3) + PR close (step 6). ``None`` for a detached worktree (from
        #    "HEAD") or when skipped (worktree absent) — the later steps no-op on the falsy branch.
        branch: str | None = None
        if worktree_present:
            try:
                branch = deps.workspace.discover_branch(issue)
            except Exception:
                logger.exception(
                    "teardown step 'discover_branch' failed for #%s; continuing", issue
                )

        # 1. Kill the tmux session only if it is alive — ``Sessions.kill`` raises on an absent
        #    session (the adapter is check=True), so guard it (PoC teardown step 1).
        try:
            if deps.sessions.is_alive(session_name):
                deps.sessions.kill(session_name)
        except Exception:
            logger.exception("teardown step 'kill_session' failed for #%s; continuing", issue)

        # 2. Remove the worktree WITH --force — a cancelled worktree is almost always dirty (PoC
        #    teardown step 3). SKIPPED when the registry reports it already gone (replay-safe, phase
        #    28.1) so a replay never runs ``git worktree remove <gone>`` → exit-128 ERROR. The
        #    ``reap`` flavour (defect 5) ALSO skips it: a stale-agent park-in-Blocked is
        #    NON-DESTRUCTIVE (PoC ``reaper._move_to_blocked`` never touched the worktree), so a
        #    twice-stalled agent keeps any unpushed work for the operator to recover.
        if worktree_present and self.flavour != "reap":
            try:
                deps.workspace.remove_worktree(issue, force=True)
            except Exception:
                logger.exception(
                    "teardown step 'remove_worktree' failed for #%s; continuing", issue
                )

        # 3. Force-delete the local feature branch (PoC teardown step 4) using the branch discovered
        #    in step 0. The ``git branch -D`` subprocess lives in the workspace adapter (the L2 seam),
        #    so this action stays subprocess-free; ``delete_branch`` is itself fail-soft and no-ops on
        #    ""/"HEAD" — and on the falsy ``branch`` a worktree-absent replay leaves (step 0 skipped).
        # The ``reap`` flavour (defect 5) skips it — a non-destructive park keeps the local branch.
        # PRESERVE the per-ticket WIP branch ``kanban/ticket-<n>`` (DESIGN §13): it carries the
        # committed ``docs/features/<codename>/`` design/plan, so deleting it on Cancel would DESTROY
        # those artifacts — we keep it (the teardown's "remote branch kept" philosophy; close ≠
        # delete-ref). The ``feat/<codename>`` branch (post create-branch) is STILL deleted.
        try:
            is_wip = bool(branch) and branch == wip_branch(issue)
            if branch and branch != "HEAD" and self.flavour != "reap" and not is_wip:
                deps.workspace.delete_branch(issue, branch)
        except Exception:
            logger.exception("teardown step 'branch_delete' failed for #%s; continuing", issue)

        # 4. Teardown purge (idempotent): removes the state file, the slot marker, the advance
        #    breadcrumb, and the queue marker. The Cancel column tears the WHOLE runtime footprint
        #    down (``keep_budgets=False`` — the default), so this is the exhaustive ``purge_ticket``
        #    that ALSO drops the per-issue move/retry budgets — NOT the slot-only ``release_slot``
        #    (which the launch-failure / drain leak-safety uses to KEEP a queued ticket's marker).
        #    See the 13.7 PoC split. The reaper passes ``keep_budgets=True`` (13.8) so a reaped
        #    stale agent keeps its rate-limit/retry budgets; ``self.keep_budgets`` routes that.
        try:
            deps.store.purge_ticket(issue, keep_budgets=self.keep_budgets)
        except Exception:
            logger.exception("teardown step 'purge_ticket' failed for #%s; continuing", issue)

        # 5. Flip any OPEN stage stickies to their terminal status (PoC teardown step 6; DESIGN
        #    §8.2.c): Cancel → ❌ ``cancelled``, Done-arrival (phase 28.1) → ✅ ``done`` (the work is
        #    complete, NOT abandoned). Best-effort (the helper is itself fail-soft + header-keyed).
        #    The ``reap`` flavour (defect 5) SKIPS this: the reaper itself flips the stage sticky to
        #    ⛔ ``blocked`` from the stale state's own metadata AFTER this teardown, so stamping a ❌
        #    ``cancelled`` header here would be wrong (the ticket is parked, not abandoned).
        now = deps.clock.now()
        try:
            if self.flavour == "done":
                _done_open_stickys(deps.board_writer, issue, now=now)
            elif self.flavour == "cancel":
                _cancel_open_stickys(deps.board_writer, issue, now=now)
        except Exception:
            logger.exception("teardown step 'finalize_stickys' failed for #%s; continuing", issue)

        # 6. Close the open PR for the branch, KEEP the remote branch (PoC teardown remote step;
        #    DESIGN §8.2). No-op when there is no branch ("" / "HEAD") or no open PR. Closing is
        #    NOT a merge (the deny-list bans merge for agents; teardown is the dispatcher). The
        #    ``reap`` flavour (defect 5) SKIPS the PR close: a twice-stalled InProgress/PRCI/Review
        #    agent must keep its open PR (PoC ``reaper._move_to_blocked`` never touched the PR).
        try:
            if branch and branch != "HEAD" and self.flavour != "reap":
                deps.pull_requests.close_open_pr_for_branch(branch)
        except Exception:
            logger.exception("teardown step 'close_pr' failed for #%s; continuing", issue)

        # 7. Final recap comment so the timeline records the teardown (English; full-parity text).
        #    The Done flavour (phase 28.1) posts a SHORT "moved to Done" recap, NO Backlog re-arm.
        #    The ``reap`` flavour (defect 5) posts NO recap here: the reaper already posted its own
        #    stall-reason comment (its ``BlockAction``) AND flips the ⛔ sticky, so a second recap
        #    would be redundant — and crucially it must NOT claim "PR closed / branch removed" when
        #    the reap left all of that intact.
        if self.flavour == "reap":
            return
        if self.flavour == "done":
            recap = f"Ticket #{issue} moved to Done — agent torn down (worktree/session removed)."
        elif branch and branch == wip_branch(issue):
            # The WIP branch is PRESERVED (DESIGN §13) → the recap must NOT claim "local branch removed".
            recap = (
                f"Ticket #{issue} cancelled — worktree / session removed. The per-ticket WIP branch "
                f"`{branch}` (any committed design/plan) is KEPT, PR closed, remote branch kept. "
                f"Resume: move the card to Backlog."
            )
        else:
            recap = (
                f"Ticket #{issue} cancelled — worktree / local branch / session removed. "
                f"PR closed, remote branch kept. Resume: move the card to Backlog."
            )
        try:
            deps.board_writer.comment(issue, recap)
        except Exception:
            logger.exception("teardown step 'recap_comment' failed for #%s; continuing", issue)


@dataclass(frozen=True)
class ResetAction:
    """Re-arm a cancelled ticket for a clean restart (Cancel → Backlog, DESIGN §8.2).

    Ported from the PoC ``engine/teardown.py`` ``reset_ticket``. Clears the ticket's
    persisted runtime state (uuid / worktree path / session id) so the next move into an
    agent column starts from a clean slate with a fresh session and worktree. The GitHub
    issue metadata (title, body, labels) is untouched — only the machine-side runtime
    state is cleared. No agent is launched (Backlog is inert).

    After a teardown the persisted state is normally already gone; this action *guarantees*
    it by releasing the slot again (idempotent), so even a ticket that reached Cancel
    without a prior teardown (e.g. a legacy card) is fully purged.
    """

    ticket: Ticket

    def execute(self, deps: Deps) -> None:
        """Clear the ticket's persisted runtime state while preserving issue metadata.

        Args:
            deps: The adapter bundle to act through.
        """
        issue = self.ticket.issue_number
        if issue is None:
            return
        # Idempotent EXHAUSTIVE purge: clears uuid/worktree/session by removing the state record
        # AND every other per-ticket marker (slot, breadcrumb, queue, moves, retries). The Cancel→
        # Backlog reset re-arms a clean slate, so it uses ``purge_ticket`` (the exhaustive teardown),
        # NOT the slot-only ``release_slot`` (13.7 PoC split). The GitHub issue itself is untouched —
        # only the machine-side runtime state is cleared, so the next agent move re-launches fresh.
        deps.store.purge_ticket(issue)


@dataclass(frozen=True)
class BlockAction:
    """Record that a ticket is blocked and DO NOT relaunch (DESIGN §3.1).

    A :class:`BlockAction` is decided when the anti-loop guard trips or the kill-switch is set.
    It must never start an agent; its only effect is to surface the block on the ticket so an
    operator sees why nothing happened. The ``reason`` is supplied by the caller (the pure
    :func:`kanbanmate.core.decide.decide` verdict, or the reap step's stale-agent reason).

    **Block-as-comment, NOT a board park (#16 KEEP+DOC — DESIGN §6).** The PoC's runner parked a
    rate-limit-runaway item in the Blocked COLUMN (a visible board move + comment). NEW keeps the
    rate-limit / anti-loop trip as a BlockAction COMMENT and does NOT move the card. This is the
    correct polling-model behaviour: the daemon already reflects board state via the
    diff-against-persisted baseline (the PRIMARY idempotence net, DESIGN §6), and an autonomous
    board park would itself feed that diff. The anti-loop / rate-limit backstop is DESIGN-documented
    SECONDARY defense-in-depth, not the primary idempotence mechanism — so it surfaces the block on
    the timeline rather than mutating the board.
    """

    ticket: Ticket
    reason: str

    def execute(self, deps: Deps) -> None:
        """Post the block reason on the ticket without launching anything.

        Args:
            deps: The adapter bundle to act through.
        """
        issue = self.ticket.issue_number
        if issue is None:
            return
        # The comment is the only effect — emphatically no launch (DESIGN §3.1 BlockAction).
        deps.board_writer.comment(issue, f"KanbanMate: ticket #{issue} blocked — {self.reason}.")


# Re-export the two bounce-the-card-back actions under their HISTORICAL home (#3 ceiling split,
# phase 32). ``RollbackAction`` + ``DependencyBounceAction`` moved to ``app/bounce.py`` to keep
# ``actions.py`` under the 1000-LOC hard ceiling once the dependency-bounce action landed; every
# caller + test still imports them from ``kanbanmate.app.actions``, so keep the names resolvable
# here. The import is at the BOTTOM (after ``Deps`` is defined above) so ``bounce``'s top-level
# ``from kanbanmate.app.actions import Deps`` resolves against a fully-built module — no cycle.
# Explicit ``import ... as`` re-export so mypy treats the names as re-exported.
from kanbanmate.app.bounce import (  # noqa: E402  (bottom re-export, see above)
    DependencyBounceAction as DependencyBounceAction,
)
from kanbanmate.app.bounce import (  # noqa: E402
    RollbackAction as RollbackAction,
)

# Re-export the mechanical run-script action under its HISTORICAL home (ceiling-relief split for the
# trust-audit fixes — actions.py reached the 1000-LOC hard ceiling). ``RunScriptAction`` moved to
# ``app/run_script_action.py``; every caller + test still imports it from ``kanbanmate.app.actions``,
# so the name stays resolvable here. The import is at the BOTTOM (after ``Deps`` is defined above) so
# the module's top-level ``from kanbanmate.app.actions import Deps`` resolves against a fully-built
# module — no cycle. Explicit ``import ... as`` re-export so mypy treats the name as re-exported.
from kanbanmate.app.run_script_action import (  # noqa: E402
    RunScriptAction as RunScriptAction,
)
