"""Shipped ``/implement:*`` prompt defaults + the default transition table.

This pure constants module is the NEW analog of the PoC
``cli/transitions_yaml.py:39-158`` (the source of truth per DESIGN §11). It holds:

* the six English launch-prompt templates the default ``transitions.yml`` ships
  (one per autonomous ``/implement:*`` stage); and
* :data:`DEFAULT_TRANSITIONS`, the full per-``(from, to)`` whitelist keyed to
  NEW's **unified column keys** (DESIGN §9).

It is **pure** — no I/O. The renderer/writer that serialises these into a
per-repo ``transitions.yml`` lives in the CLI/init layer (phase 12.7); this
module only declares the data, so ``core/`` keeps importing nothing with I/O
(the layering guard).

**The transitions-only board model (operator decision 2026-06-09, DESIGN §8.0.6/§9).**
The PoC shipped a single 12-column flow where the agent launches at the
``(from, to)`` transition, never at a column. NEW ships the **full** PoC transition
flow here (nothing left behind); a prompt-bearing whitelisted transition that passes
the BLOCK guards LAUNCHes unconditionally (:func:`kanbanmate.core.decide.decide`).
``columns.yml`` carries **no** launch configuration — it is a bare column SET — so
there is no per-column autonomy gate and no dormant stage.

**History (condensed; full detail in DESIGN §8/§9).** The PoC display names map 1:1 onto NEW's
stable keys (Design→Spec, Implement→InProgress, PR Ready→PRCI, …); the former ``Planned`` gate was
retired into ``ReadyToDev``. The front of the flow was split so only ``Backlog -> Brainstorming`` is
INTERACTIVE; EVERY other agent prompt carries an explicit "run fully autonomously — do NOT ask the
user any questions" instruction so an unattended session never hangs (the reaper would churn it). The
interactive brainstorm is the one place a human ``tmux attach``es to answer.

**The HYBRID auto-advance flow (DESIGN §13, operator decision).** The doc + build
launch stages carry an ``advance:auto:<col>`` directive the ENGINE now honours (the
``bin/kanban_session_end`` backstop): when a launch stage ends with a clean
``kanban-done`` and the agent did NOT move its own card, the engine moves the card to
``<col>`` and the next tick's diff fires the next stage. This turns the front of the
flow AUTONOMOUS through Plan, then STOPS at the two HUMAN gates::

    Backlog       -> Brainstorming   advance:auto:Spec       (brainstorm → auto-advance)
    Brainstorming -> Spec            advance:auto:Plan        (design → auto-advance)
    Spec          -> Plan            advance:auto:ReadyToDev  (plan → auto-advance, then STOP)
    Plan          -> ReadyToDev      no-op                    *** HUMAN REVIEW GATE ***
    ReadyToDev    -> PrepareFeature  advance:auto:InProgress  (HUMAN drags to build → create-branch)
    PrepareFeature-> InProgress      advance:auto:PRCI        (implement+PR → auto-advance)
    InProgress    -> PRCI (SCRIPT)   advance:auto:Review      (green CI → auto-advance, fires review)
    PRCI          -> Review          advance:auto:ReadyToMerge (review done → auto-advance)
    Review        -> ReadyToMerge    no-op                    *** HUMAN MERGE GATE ***
    ReadyToMerge  -> Merge (AGENT)   advance:stop             autonomous merge agent (operator); it
                                                              self-routes Done|ReadyToMerge (see below)

``Plan -> ReadyToDev`` MUST stay a no-op (no advance directive) — auto-advancing it
would bypass the single pre-build HUMAN review gate (the core HYBRID property). The
former separate ``Planned`` gate was RETIRED: ReadyToDev is now THE gate, and the build
starts only when the human drags ReadyToDev → PrepareFeature. ``PrepareFeature -> InProgress``'s ``auto:PRCI`` and the
``InProgress -> PRCI`` SCRIPT gate's ``auto:Review`` are consumed differently: the
launch-stage directives by the session-end backstop, the SCRIPT-gate directive by
``app/script_route._route_success`` (already wired).

**Early skip-to-Done (genesis phase 26; skiff added Triage/Scope).** A single
list-expanded no-op entry whitelists
``[Backlog, Triage, Brainstorming, Scope, Spec, Plan, ReadyToDev] -> Done``
(7 cartesian edges) so an agent/human can mark an ALREADY-DONE ticket Done
without a rollback. The skiff fast-track heads ``Triage`` and ``Scope`` join the
set for symmetry — they too write no worktree/branch. It is BOUNDED at
ReadyToDev/Scope: from ``PrepareFeature`` onward a worktree/branch exists, so
retirement must go through Cancel (teardown). Done is therefore NOT whitelisted
from ``PrepareFeature``/``InProgress``/``PRCI``/``Review``/``Merge`` (those →
Cancel only); a direct ``PrepareFeature -> Done`` rolls back.

**Autonomous merge (operator decision).** The review stage AUTO-ADVANCES to ``ReadyToMerge`` (the
human merge gate) on completion; the human then drags ``ReadyToMerge -> Merge``, an AGENT stage
driven by ``_MERGE_PROMPT`` under the dedicated ``merge`` permission profile — the SOLE profile whose
deny-list lifts ``gh pr merge`` (force-push, rebase, history rewrite, ref deletion, and the
api/graphql/github-curl merge paths stay banned even there). The merge agent brings the PR up to
date with main (merge-main-IN, intelligent conflict resolution — never rebase/force-push), waits
for CI to be fully green, then squash-merges via ``gh pr merge --squash``. ``advance:stop``: the
agent routes itself — success → ``Done``, any blocker (unresolvable conflict, red/stuck CI, not
mergeable) → back to ``Ready to merge`` for a human. ``bin/check-pr-ready.sh`` (the PR/CI gate) is
unchanged; ``bin/check-merge-ready.sh`` is retained as a helper but the launch transition no
longer gates on it (the agent owns the mergeability + CI checks).

**Language (operator decision, DESIGN §8.6 note).** The PoC prompt strings are
FRENCH. The launch prompt is an INTERNAL instruction typed into the launched
agent's own session (NOT a published GitHub artifact), so the English-only
artifact rule does not govern it — but the prose is translated to English for
codebase consistency. **Nothing is dropped**: every ``{{placeholder}}`` and every
``/implement:*`` slash-command is preserved verbatim (they are load-bearing).
"""

from __future__ import annotations

from typing import Any

import yaml

from kanbanmate.core.transitions import TransitionConfig, load_transitions

from kanbanmate.core.transitions_prompts import (
    _SCOPE_GUARD as _SCOPE_GUARD,
    _IDENTITY_THEN_STATE as _IDENTITY_THEN_STATE,
    _STATE_CHECK_EARLY as _STATE_CHECK_EARLY,
    _STATE_CHECK_LATE as _STATE_CHECK_LATE,
    _DESYNC as _DESYNC,
    _AUTONOMY as _AUTONOMY,
    _GROUNDING_DISCIPLINE as _GROUNDING_DISCIPLINE,
    _WRITE_BACK as _WRITE_BACK,
    _CLEAN_STOP as _CLEAN_STOP,
    _BRAINSTORM_PROMPT as _BRAINSTORM_PROMPT,
    _TRIAGE_PROMPT as _TRIAGE_PROMPT,
    _SCOPE_PROMPT as _SCOPE_PROMPT,
    _DESIGN_PROMPT as _DESIGN_PROMPT,
    _PLAN_PROMPT as _PLAN_PROMPT,
    _PREPARE_PROMPT as _PREPARE_PROMPT,
    _IMPLEMENT_PROMPT as _IMPLEMENT_PROMPT,
    _FIXCI_PROMPT as _FIXCI_PROMPT,
    _REVIEW_PROMPT as _REVIEW_PROMPT,
    _REWORK_PROMPT as _REWORK_PROMPT,
    _MERGE_PROMPT as _MERGE_PROMPT,
)


# ---------------------------------------------------------------------------
# Default transition table (DESIGN §9), keyed to NEW's UNIFIED column keys.
# Each entry is one whitelisted (from, to) pair carrying its own action. This is
# a 1:1 map of the PoC table with the display-name → key map applied (see the
# module docstring).
# ---------------------------------------------------------------------------

# ``permission_mode`` is the ``claude --permission-mode`` for the launched session.
# It is configurable PER TRANSITION; the default "auto" is headless-safe (never
# hangs on a permission prompt and STILL enforces ``permissions.deny``).
# ``bypassPermissions`` is NOT allowed (it would skip the deny layer). It is set
# only on LAUNCH transitions (those with a prompt) — no-op / script-only rows
# launch no agent, so they carry no mode.
DEFAULT_TRANSITIONS: list[dict[str, Any]] = [
    # ── Normal forward workflow ──────────────────────────────────────────────
    # Backlog → Triage: the skiff fast-track CLASSIFIER (cheap, read-only). It records the lane (the
    # durable **track** field + the kanban-route breadcrumb) and ends; the ENGINE then routes the card
    # to the lane's entry column (bin/kanban_session_end._routed_advance, advance: route). This
    # REPLACES the former direct Backlog → Brainstorming launch — every ticket now enters via triage.
    {
        "from": "Backlog",
        "to": "Triage",
        "profile": "triage",
        "prompt": _TRIAGE_PROMPT,
        # skiff routing (DESIGN): advance: route → the session-end backstop reads the kanban-route
        # breadcrumb and moves the card to the lane entry (TRACK_ENTRY). NOT an auto:<col> directive.
        "advance": "route",
        "permission_mode": "auto",
    },
    # Triage → Brainstorming: the FULL lane head (interactive brainstorm, unchanged). The one place a
    # human tmux-attaches to answer clarifying questions. Matches TRACK_ENTRY["full"].
    {
        "from": "Triage",
        "to": "Brainstorming",
        "profile": "docs",
        "prompt": _BRAINSTORM_PROMPT,
        # HYBRID flow (DESIGN §13): the brainstorm completes (kanban-done) → the engine backstop
        # (bin/kanban_session_end._auto_advance) moves the card to Spec, firing the design stage.
        "advance": "auto:Spec",
        "permission_mode": "auto",
    },
    # Triage → Scope: the LITE lane head (compressed design+plan in one pass; no human gate). Matches
    # TRACK_ENTRY["lite"]. Auto-advances into PrepareFeature (build) when the scope note is committed.
    {
        "from": "Triage",
        "to": "Scope",
        "profile": "docs",
        "prompt": _SCOPE_PROMPT,
        "advance": "auto:PrepareFeature",
        "permission_mode": "auto",
    },
    # Triage → PrepareFeature: the EXPRESS lane head (no design — straight to create-branch/build; the
    # design rationale lives in the PR body). Matches TRACK_ENTRY["express"]. create-branch runs on
    # arrival (the plan-adaptive _PREPARE_PROMPT handles the no-DESIGN.md case). Same profile + prompt
    # as the full-lane ReadyToDev → PrepareFeature human-drag row.
    {
        "from": "Triage",
        "to": "PrepareFeature",
        "profile": "prepare",
        "prompt": _PREPARE_PROMPT,
        "advance": "auto:InProgress",
        "permission_mode": "auto",
    },
    # Scope → PrepareFeature: the LITE lane continues into create-branch/build (engine auto-advance).
    # The SCOPE.md committed on the WIP branch is read by the plan-adaptive _PREPARE_PROMPT.
    {
        "from": "Scope",
        "to": "PrepareFeature",
        "profile": "prepare",
        "prompt": _PREPARE_PROMPT,
        "advance": "auto:InProgress",
        "permission_mode": "auto",
    },
    # Brainstorming → Spec: AUTONOMOUS design — writes design.md from the brainstorm
    # output already in the ticket body. No questions (the prompt carries _AUTONOMY).
    {
        "from": "Brainstorming",
        "to": "Spec",
        "profile": "docs",
        "prompt": _DESIGN_PROMPT,
        # HYBRID flow (DESIGN §13): the design completes → the engine backstop moves the card to
        # Plan, firing the plan stage.
        "advance": "auto:Plan",
        "permission_mode": "auto",
    },
    # Spec → Plan: AUTONOMOUS /implement:plan — writes the plan files. No questions.
    {
        "from": "Spec",
        "to": "Plan",
        "profile": "docs",
        "prompt": _PLAN_PROMPT,
        # HYBRID flow (DESIGN §13): the plan completes → the engine backstop moves the card to
        # ReadyToDev, where it STOPS (the SINGLE pre-build HUMAN review gate; Plan→ReadyToDev is a
        # no-op). The redundant "Planned" gate was removed — ReadyToDev is now THE gate.
        "advance": "auto:ReadyToDev",
        "permission_mode": "auto",
    },
    # Plan → ReadyToDev: no-op. Autonomous design+plans are done; the card lands in ReadyToDev
    # (the human review gate). The build does NOT start on arrival here — the human drags
    # ReadyToDev → PrepareFeature to launch create-branch.
    {"from": "Plan", "to": "ReadyToDev"},  # allowed no-op (human gate landing)
    # ReadyToDev → Spec: operator-recovery no-op (#12). A rejected plan can re-fire the
    # autonomous design via Spec → Plan (no agent launches on THIS edge — the human
    # moves the card back to Spec, then Spec → Plan re-runs /implement:plan).
    {"from": "ReadyToDev", "to": "Spec"},  # allowed no-op (recovery: re-plan)
    {
        "from": "ReadyToDev",
        "to": "PrepareFeature",
        "profile": "prepare",
        "prompt": _PREPARE_PROMPT,
        # HYBRID flow (DESIGN §13): create-branch completes → the engine backstop moves the card to
        # InProgress, firing the implement stage. The human already gated at ReadyToDev — the build
        # starts ONLY on this human-initiated ReadyToDev → PrepareFeature move.
        "advance": "auto:InProgress",
        "permission_mode": "auto",
    },
    # Human moves PrepareFeature→InProgress; the agent then auto-advances to PRCI
    # when /implement:phase finishes.
    {
        "from": "PrepareFeature",
        "to": "InProgress",
        "profile": "dev",
        "prompt": _IMPLEMENT_PROMPT,
        "advance": "auto:PRCI",
        "permission_mode": "auto",
    },
    # Bot script transition: PR created + CI green? HYBRID flow (DESIGN §13): on a GREEN gate the
    # SCRIPT-route auto-advance (app/script_route._route_success, already wired) moves the card to
    # Review, firing the pr-review stage; a red gate bounces back to InProgress (the fix-CI loop).
    {
        "from": "InProgress",
        "to": "PRCI",
        "profile": "check",
        "script": "bin/check-pr-ready.sh",
        "on_fail": "move:InProgress",
        "advance": "auto:Review",
    },
    # Bot fix-CI loop (capped, DESIGN §8.4). SAME destination as PrepareFeature→
    # InProgress but a DIFFERENT prompt — the per-(from,to) discriminator the
    # per-column model could not express.
    {
        "from": "PRCI",
        "to": "InProgress",
        "profile": "dev",
        "prompt": _FIXCI_PROMPT,
        "advance": "auto:PRCI",
        "permission_mode": "auto",
    },
    # Human: review rounds. On clean completion the review agent AUTO-ADVANCES to ReadyToMerge (the
    # human merge gate) — the review no longer STOPS at Review; the human decision moves to
    # ReadyToMerge. A red CI gate still bounces back to InProgress (the fix-CI loop, above).
    {
        "from": "PRCI",
        "to": "Review",
        "profile": "dev",
        "prompt": _REVIEW_PROMPT,
        "advance": "auto:ReadyToMerge",
        "permission_mode": "auto",
    },
    # Review → ReadyToMerge: the no-op whitelist edge that LANDS the review's auto-advance (the engine
    # backstop moves the card here when the review agent ends cleanly; whitelisting it prevents a
    # rollback of that move). ReadyToMerge is inert — the human merge gate.
    {"from": "Review", "to": "ReadyToMerge"},
    # Review → InProgress: operator-requested REWORK (#12). A human drags the card back
    # from Review to InProgress to ask for changes — mirrors the PRCI → InProgress fix-CI
    # pattern (profile dev, advance auto:PRCI re-runs the CI gate after the rework push),
    # but driven by review feedback rather than a red CI gate. Closes the rework dead-end
    # (previously rework meant destructive Cancel or undiscoverable Blocked-laundering).
    {
        "from": "Review",
        "to": "InProgress",
        "profile": "dev",
        "prompt": _REWORK_PROMPT,
        "advance": "auto:PRCI",
        "permission_mode": "auto",
    },
    # AUTONOMOUS MERGE (operator decision): the human drags a reviewed card from ReadyToMerge → Merge,
    # firing a claude agent under the dedicated ``merge`` profile (the SOLE profile whose deny lifts
    # ``gh pr merge``) that brings the PR up to date with main (merge-main-IN, intelligent conflict
    # resolution — never rebase/force-push), waits for CI to be fully green, then squash-merges via
    # ``gh pr merge --squash``. ``advance:stop`` — the agent routes itself: success → Done, any blocker
    # → back to Ready to merge (the agent's explicit kanban-move).
    #
    # PRE-LAUNCH CI GATE (audit §6 defense-in-depth): ``bin/check-pr-ready.sh`` runs BEFORE the agent
    # launches — a red/pending CI fails the gate and ``on_fail:move:ReadyToMerge`` bounces the card back
    # to Ready to merge WITHOUT starting the merge agent (don't even attempt a merge on a red PR). NOTE
    # this checks the PRE-merge-IN CI; the agent's own CI-wait after merging main in is the second
    # layer, and a server-side ``required_status_checks`` branch ruleset on the default branch is the
    # AUTHORITATIVE third layer (recommended — without it ``gh pr merge`` is not server-gated on CI).
    {
        "from": "ReadyToMerge",
        "to": "Merge",
        "profile": "merge",
        "prompt": _MERGE_PROMPT,
        "script": "bin/check-pr-ready.sh",
        "on_fail": "move:ReadyToMerge",
        "advance": "stop",
        "permission_mode": "auto",
    },
    {
        "from": "Merge",
        "to": "Done",
    },  # success route (the merge agent moves here after squash-merge)
    # Failure route: the merge agent moves the card BACK to Ready to merge (a plain no-op edge — it
    # does NOT re-fire ReadyToMerge→Merge, which only triggers on a move INTO Merge) so a human can
    # triage a blocked merge (unresolvable conflict / red CI / not mergeable).
    {"from": "Merge", "to": "ReadyToMerge"},
    # ReadyToMerge → InProgress: operator-requested REWORK from the merge gate (mirror of
    # Review→InProgress) — if the human, at the merge gate, wants changes instead of a merge, dragging
    # the card here fires the rework stage (profile dev, advance auto:PRCI re-runs the CI gate after
    # the rework push). Keeps the gate's rework path whitelisted so the drag is not rolled back.
    {
        "from": "ReadyToMerge",
        "to": "InProgress",
        "profile": "dev",
        "prompt": _REWORK_PROMPT,
        "advance": "auto:PRCI",
        "permission_mode": "auto",
    },
    # Done → Backlog: operator-recovery reopen (#12). A PLAIN no-op whitelist edge — NOT a
    # RESET (the whitelist schema carries no `action:` field, and decide() hard-wires RESET to
    # the reactive Cancel column; a Done-as-RESET would touch the whitelist model). So this is a
    # no-op: it makes Done → Backlog a KNOWN transition (no rollback) but does NOT wipe stale
    # persisted state. Per the rank-7 verdict that is acceptable — after teardown-on-Done (#9)
    # reclaims live agents' worktrees and session-end purges state, residual state on a Done
    # ticket is already rare, so the no-op variant loses little. Re-seed-fresh-board stays the
    # primary recovery doctrine; this is a convenience reopen.
    {"from": "Done", "to": "Backlog"},  # allowed no-op (recovery: reopen)
    # Early skip-to-Done (genesis phase 26, e2e-driven; skiff added Triage/Scope). A single
    # list-expanded no-op entry whitelists the seven PRE-PrepareFeature columns → Done so an
    # agent/human can mark an ALREADY-DONE ticket Done without a rollback. It cartesian-expands to
    # seven explicit no-op edges (no prompt/script). The skiff fast-track heads ``Triage`` and
    # ``Scope`` are included for symmetry with the other pre-PrepareFeature columns (they too write
    # no worktree/branch). BOUNDED at ReadyToDev/Scope: from PrepareFeature onward a worktree/branch
    # exists, so retirement must go through Cancel (teardown) — Done is deliberately NOT whitelisted
    # from PrepareFeature/InProgress/PRCI/Review/Merge (a direct → Done there rolls back).
    {
        "from": ["Backlog", "Triage", "Brainstorming", "Scope", "Spec", "Plan", "ReadyToDev"],
        "to": "Done",
    },
    # Parking wildcards (any column ↔ Blocked).
    {"from": "*", "to": "Blocked"},
    {"from": "Blocked", "to": "*"},
    # Cancel teardown + resume (DESIGN §8.2). NO agent: these are routed
    # mechanically by the reactive routing in decide() (destination Cancel is a
    # REACTIVE column → TEARDOWN; Cancel → Backlog → RESET), BEFORE the whitelist
    # verdict. The (*, Cancel) row makes any source → Cancel a KNOWN transition so
    # it is not rolled back; (Cancel, Backlog) is the only resume path. No prompt /
    # script / permission_mode: nothing is launched.
    {"from": "*", "to": "Cancel"},
    {"from": "Cancel", "to": "Backlog"},
]

# Defaults block shipped in the rendered transitions.yml (DESIGN §9): the
# concurrency cap is 3 (the loader fallback is ALSO 3 as of #4 — aligned, one
# surface), and the per-item AUTO/bot move rate limit is 10 per hour.
DEFAULT_CONCURRENCY_CAP = 3
DEFAULT_MOVE_RATE_LIMIT_PER_HOUR = 10

# skiff fast-track: the lane vocabulary + each lane's entry column KEY. The triage stage routes a
# ticket onto a lane by having the ENGINE move the card to this column (a whitelisted Triage→entry
# edge), so the launch on that edge fires the lane's head stage. Pairs with the columns shipped in
# columns.yml.tmpl + the Triage→{entry} transitions below; a custom board that renames these columns
# must update this map too.
TRACK_VALUES: tuple[str, ...] = ("full", "lite", "express")
TRACK_ENTRY: dict[str, str] = {
    "full": "Brainstorming",
    "lite": "Scope",
    "express": "PrepareFeature",
}


def render_transitions_yaml(project: str) -> str:
    """Render the ``transitions.yml`` document for *project* as a YAML string.

    Pure: takes a project slug, returns a string — no I/O. The caller (the
    CLI/init layer) writes the result to the clone.

    **Divergence from the columns.yml pattern.** ``columns.yml`` ships as a
    static, project-agnostic ``.tmpl`` asset (read via ``importlib.resources``
    and copied verbatim). ``transitions.yml`` is RENDERED — it carries the
    ``project`` slug — so there is no static ``assets/transitions.yml.tmpl``.
    This renderer is the source of truth for the shipped ``transitions.yml``.

    The template default ``concurrency_cap`` is **3**, matching the loader
    fallback (aligned as of #4 — one authoritative default, no asymmetry).

    Args:
        project: The GitHub project slug (e.g. ``"owner/repo"``).

    Returns:
        A YAML string ready to be written to
        ``.claude/kanban/transitions.yml``.
    """
    doc = {
        "project": project,
        "defaults": {
            "concurrency_cap": DEFAULT_CONCURRENCY_CAP,
            "move_rate_limit_per_hour": DEFAULT_MOVE_RATE_LIMIT_PER_HOUR,
        },
        "transitions": [dict(t) for t in DEFAULT_TRANSITIONS],
    }
    body = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120)
    header = (
        "# permission_mode (per launch transition): claude --permission-mode for the session.\n"
        "# Configurable per transition; default 'auto' (headless-safe; STILL enforces deny).\n"
        "# Allowed: default | acceptEdits | auto | dontAsk | plan. bypassPermissions is NOT allowed.\n"
    )
    return header + body


def default_transition_config() -> TransitionConfig:
    """Build the built-in :class:`TransitionConfig` from :data:`DEFAULT_TRANSITIONS`.

    This is the **no-``transitions.yml`` fallback** (DESIGN §8.0.6): when a clone
    ships no ``transitions.yml``, the daemon must still tick with the full PoC
    flow — a whitelist is ALWAYS supplied, NEVER a column model. It renders the
    shipped table (an empty project slug, since the whitelist itself is
    project-agnostic) and parses it back through :func:`load_transitions`, so the
    fallback config goes through the SAME validation path an explicit file does
    (no second, divergent construction of the whitelist).

    Pure: ``core`` → ``core`` only, no I/O — both the renderer and the loader are
    string-in/value-out, so the layering guard stays satisfied.

    Returns:
        A fully populated :class:`TransitionConfig` carrying the shipped PoC flow.
    """
    return load_transitions(render_transitions_yaml(""))
