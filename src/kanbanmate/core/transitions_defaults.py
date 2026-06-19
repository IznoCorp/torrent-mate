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

**The PoC display-name → NEW-key map (DESIGN §9).** The PoC's column display
names are mapped 1:1 onto NEW's stable keys::

    Design          -> Spec
    Plan            -> Planned
    Ready to dev    -> ReadyToDev
    Prepare feature -> PrepareFeature   (the create-branch stage NEW gained)
    Implement       -> InProgress
    PR Ready        -> PRCI
    (Backlog / Review / Merge / Done / Cancel / Blocked are identical)

**The brainstorming/design split (genesis phase 26, e2e-driven).** The front of
the flow gained two columns — ``Brainstorming`` (after Backlog) and ``Plan``
(after Spec) — and the single former ``Backlog -> Spec`` brainstorm+design step
was split so only ONE step is interactive (DESIGN §8/§9):

    Backlog       -> Brainstorming   INTERACTIVE /implement:brainstorm (human attaches)
    Brainstorming -> Spec            AUTONOMOUS design (write design.md, no questions)
    Spec          -> Plan            AUTONOMOUS /implement:plan (no questions)
    Plan          -> Planned         no-op (lands in Planned for human review)
    Planned       -> ReadyToDev      no-op (human gate)

EVERY agent prompt except ``Backlog -> Brainstorming`` carries an explicit
"run fully autonomously — do NOT ask the user any questions" instruction so an
unattended orchestrated session never hangs on a clarifying question (the reaper
would otherwise churn it). The interactive brainstorm is the one place a human
``tmux attach``es to answer.

**The HYBRID auto-advance flow (DESIGN §13, operator decision).** The doc + build
launch stages carry an ``advance:auto:<col>`` directive the ENGINE now honours (the
``bin/kanban_session_end`` backstop): when a launch stage ends with a clean
``kanban-done`` and the agent did NOT move its own card, the engine moves the card to
``<col>`` and the next tick's diff fires the next stage. This turns the front of the
flow AUTONOMOUS through Plan, then STOPS at the two HUMAN gates::

    Backlog       -> Brainstorming   advance:auto:Spec      (brainstorm → auto-advance)
    Brainstorming -> Spec            advance:auto:Plan       (design → auto-advance)
    Spec          -> Plan            advance:auto:Planned    (plan → auto-advance, then STOP)
    Plan          -> Planned         no-op                   *** HUMAN REVIEW GATE ***
    Planned       -> ReadyToDev      no-op                   *** HUMAN drags after review ***
    ReadyToDev    -> PrepareFeature  advance:auto:InProgress (create-branch → auto-advance)
    PrepareFeature-> InProgress      advance:auto:PRCI       (implement+PR → auto-advance)
    InProgress    -> PRCI (SCRIPT)   advance:auto:Review     (green CI → auto-advance, fires review)
    PRCI          -> Review          advance:stop            *** Review STOPS for human ***
    Review        -> Merge (AGENT)   advance:stop            autonomous merge agent (operator); it
                                                             self-routes Done|Review (see below)

``Plan -> Planned`` and ``Planned -> ReadyToDev`` MUST stay no-ops (no advance
directive) — auto-advancing them would bypass the single pre-build HUMAN review gate
(the core HYBRID property). ``PrepareFeature -> InProgress``'s ``auto:PRCI`` and the
``InProgress -> PRCI`` SCRIPT gate's ``auto:Review`` are consumed differently: the
launch-stage directives by the session-end backstop, the SCRIPT-gate directive by
``app/script_route._route_success`` (already wired).

**Early skip-to-Done (genesis phase 26).** A single list-expanded no-op entry
whitelists ``[Backlog, Brainstorming, Spec, Plan, Planned, ReadyToDev] -> Done``
(6 cartesian edges) so an agent/human can mark an ALREADY-DONE ticket Done
without a rollback. It is BOUNDED at ReadyToDev: from ``PrepareFeature`` onward a
worktree/branch exists, so retirement must go through Cancel (teardown). Done is
therefore NOT whitelisted from ``PrepareFeature``/``InProgress``/``PRCI``/
``Review``/``Merge`` (those → Cancel only); a direct ``PrepareFeature -> Done``
rolls back.

**Autonomous merge (operator decision).** ``Review -> Merge`` is now an AGENT stage driven by
``_MERGE_PROMPT`` under the dedicated ``merge`` permission profile — the SOLE profile whose
deny-list lifts ``gh pr merge`` (force-push, rebase, history rewrite, ref deletion, and the
api/graphql/github-curl merge paths stay banned even there). The merge agent brings the PR up to
date with main (merge-main-IN, intelligent conflict resolution — never rebase/force-push), waits
for CI to be fully green, then squash-merges via ``gh pr merge --squash``. ``advance:stop``: the
agent routes itself — success → ``Done``, any blocker (unresolvable conflict, red/stuck CI, not
mergeable) → back to ``Review`` for a human. ``bin/check-pr-ready.sh`` (the PR/CI gate) is
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


# ---------------------------------------------------------------------------
# Prompt templates (DESIGN §9 "Action" column, filled at dispatch time by
# kanbanmate.core.placeholders.fill). Ported from PoC cli/transitions_yaml.py:
# 39-87 — prose translated to English, every {{placeholder}} + /implement:*
# slash-command kept verbatim.
#
# AUTONOMY (genesis phase 26, e2e-driven). Only _BRAINSTORM_PROMPT is INTERACTIVE
# (the one place a human ``tmux attach``es to answer). EVERY other agent prompt
# carries an explicit "run fully autonomously — do NOT ask the user any questions"
# instruction so an unattended orchestrated session never hangs on a clarifying
# question (the reaper would otherwise churn it).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Shared hardening constants (§29.4). The #91 e2e showed prompt wording alone is
# load-bearing for agent discipline: a misattributed agent verified the WRONG
# feature's shipped-ness, agents improvised raw ``gh issue edit`` (unsanctioned
# writes), and a brainstorm OVERWROTE the seeded description. These constants
# encode the locked decisions (IDENTITY-THEN-STATE; late-stage shipped exit =
# Blocked, not Cancel; all body write-backs via kanban-update-body ONLY) so every
# prompt carries the same discipline. Filled at dispatch by ``placeholders.fill``.
# ---------------------------------------------------------------------------

# Scope guard: an agent acts on ITS OWN ticket and nothing else. The worktree pin
# (.claude/kanban-issue) mechanically enforces this for the kanban-* helpers, but
# the prompt states it too so the agent never reasons about another ticket.
_SCOPE_GUARD = (
    "SCOPE: you are working ticket {{code}} ({{title}}) and NOTHING else — never read, "
    "comment on, move, or write to another ticket. Every kanban-* helper is PINNED to "
    "{{code}} and will refuse a different issue.\n"
)

# IDENTITY-THEN-STATE (the verdict-mandated ordering): VERIFY identity BEFORE any
# state check or board move, so a misattributed agent can never act on the wrong
# feature. The identity triangle is title [CODE] vs the body **roadmap** line vs the
# repo roadmap entry (ROADMAP.md / docs/archive/features/). Absent **roadmap** →
# the title [CODE] is authoritative: self-backfill the marker on YOUR OWN ticket via
# kanban-update-body, then proceed. ALL board moves are gated on identity passing.
_IDENTITY_THEN_STATE = (
    "IDENTITY FIRST (before ANY state check or board move): confirm this ticket's identity "
    "by cross-checking THREE sources — the title [CODE] bracket of {{title}}, the **roadmap** "
    "line in the ticket description, and the matching roadmap entry in the repo (ROADMAP.md or "
    "docs/archive/features/). If the **roadmap** line is ABSENT, the title [CODE] is "
    "authoritative: add `**roadmap**: <CODE>` to YOUR OWN ticket via "
    "`kanban-update-body {{code}} --set-field roadmap <CODE>`, then proceed. If the three "
    "sources DISAGREE (a genuine desync), follow the DESYNC protocol below — do NOT guess. "
    "Only once identity is confirmed may you check state or move the card.\n"
)

# Early-stage shipped exit (pre-PrepareFeature stages): if the feature is ALREADY
# shipped, post the evidence FIRST, then kanban-move to Done. Evidence is REPO-LOCAL
# only (ROADMAP.md, docs/archive/features/, git log, the code) so the docs/prepare
# profiles need no extra gh scopes. This is a TERMINAL exit (ends in kanban-done), so it
# carries the same clean-stop discipline as the main path (§_CLEAN_STOP).
_STATE_CHECK_EARLY = (
    "STATE CHECK: if (and only if) identity is confirmed AND repo-local evidence "
    "(ROADMAP.md, docs/archive/features/, git log, the code) shows this feature is ALREADY "
    "shipped, do NOT redo the work: post an evidence comment via "
    '`kanban-comment {{code}} "already shipped: <evidence>"` FIRST, then '
    "`kanban-move {{code}} Done` — this move is MANDATORY: it OVERRIDES (replaces) the normal "
    "DONE checklist below, so the ALREADY_SHIPPED exit is NOT complete until the card is actually "
    "in Done. Then run `kanban-done {{code}}` and END your turn (do NOT type or run the next-stage "
    "slash command; no trailing-`&` background shells).\n"
)

# Late-stage shipped exit (PrepareFeature onward — a worktree/branch/PR exists): a
# false positive here must NEVER close a PR or destroy a worktree, so the exit is
# Blocked (operator triages), NOT Cancel. Cancel is operator-only. This is a TERMINAL
# exit (ends in kanban-done), so it carries the same clean-stop discipline (§_CLEAN_STOP).
_STATE_CHECK_LATE = (
    "STATE CHECK: if identity is confirmed AND repo-local evidence (ROADMAP.md, "
    "docs/archive/features/, git log, the code) shows this feature is ALREADY shipped, do NOT "
    'redo the work: post an evidence comment via `kanban-comment {{code}} "already shipped: '
    '<evidence>"` FIRST, then `kanban-move {{code}} Blocked` so the operator can triage. Do NOT '
    "move to Cancel (Cancel is operator-only — a false positive must never close a PR or destroy "
    "a worktree). Run `kanban-done {{code}}` and END your turn (do NOT type or run the next-stage "
    "slash command; no trailing-`&` background shells).\n"
)

# Desync protocol: on ANY identity/state ambiguity, STOP — never guess, never touch
# another ticket. Journal what you saw, post a DESYNC comment, then run `kanban-done`
# (the terminal step, #1) so a human can triage. This is a TERMINAL exit (ends in
# kanban-done), so it carries the same clean-stop discipline (§_CLEAN_STOP).
_DESYNC = (
    "DESYNC PROTOCOL: if identity is ambiguous or the sources disagree in a way you cannot "
    'safely reconcile, STOP. Journal what you observed via `kanban-progress {{code}} "…"`, post '
    'a `kanban-comment {{code}} "DESYNC: <what disagrees>"`, do NOT guess, do NOT move the card, '
    "do NOT touch another ticket, and run `kanban-done {{code}}` to end your session for a human to "
    "triage — then END your turn (do NOT type or run the next-stage slash command; no trailing-`&` "
    "background shells).\n"
)

# Shared autonomy instruction on every NON-interactive agent prompt (incl. prepare).
# Extended (§29.4): identity/state ambiguity follows the DESYNC protocol, not a guess.
_AUTONOMY = (
    "Run fully autonomously — do NOT ask the user any questions; make reasonable assumptions for "
    "ordinary gaps and proceed; do NOT invoke an interactive brainstorming Q&A. BUT for IDENTITY "
    "or STATE ambiguity, follow the DESYNC protocol instead of guessing.\n"
)

# Grounding + self-verification discipline (helm #5 review, 2026-06-17). The design/plan stages
# produced confident-but-WRONG artifacts: a false claim about how the layering guard works ("inspects
# top-level imports only" — it walks the whole AST), a call with a non-existent signature, and tests
# whose inputs resolved to None so they asserted nothing. The common root: the agent STATED/USED facts
# about the existing code WITHOUT reading the source, and wrote tests that did not exercise real
# values. This block forces verification AT THE SOURCE. (Carries no ``/implement:`` literal and no
# "end the session" prose, so it composes with the autonomy + clean-stop + no-French test guards.)
_GROUNDING_DISCIPLINE = (
    "GROUND EVERY CLAIM IN THE SOURCE (do NOT guess about the existing code). Before you state or rely "
    "on ANY fact about the current codebase — a function/method signature, a constant's value, how an "
    "existing test/guard/loader behaves, whether a column KEY or transition edge or config field "
    "exists — OPEN the actual source file, confirm it, and cite it as `path:line`. NEVER assert how an "
    "existing test or guard works from memory (e.g. do NOT claim an import/layering guard 'only "
    "inspects top-level imports' without reading it — read it; it may walk the whole AST, in which "
    "case a function-local import does NOT bypass it). "
    "MATCH REAL SIGNATURES: when your design or plan calls or references an existing symbol, match its "
    "actual signature / name / value EXACTLY — a call that does not match the real definition is a "
    "defect, not a stub. "
    "RESPECT THE LAYERING: `core/` MUST NOT import `app`/`adapters`/`cli`/`daemon`; if a value you need "
    "lives in a forbidden layer, relocate its source-of-truth to a permitted layer rather than "
    "inventing a workaround. "
    "DECLARE NEW DEPENDENCIES: if your code imports a third-party package NOT already in "
    "`pyproject.toml`, you MUST add it there — a core dependency, or an optional extra (mirror the "
    "existing `[ui]`/`[mcp]` extras, with the CLI entry import-guarded behind `try/except ImportError`) "
    "— AND add it to the CI install (`.github/workflows/pr.yml`). NEVER assume a package is present "
    "because it imports in your shell: CI installs from `pyproject.toml` on the PROJECT interpreter "
    "(the one `requires-python` targets), so verify it both IMPORTS there and is DECLARED — an import "
    "of an undeclared dep is a defect that passes locally and fails CI. "
    "TESTS MUST EXERCISE REAL VALUES: every assertion must compare a genuinely-produced, non-trivial "
    "result — confirm your test inputs resolve to real data BEFORE asserting (two None/empty sides "
    "prove nothing); use real column KEYS, not display labels, and edges that actually exist. A test "
    "that asserts on CLI / Rich-rendered output (e.g. `--help`) MUST be terminal-width/ANSI-INDEPENDENT "
    "— force a wide width + strip ANSI (or assert on the parsed result), NEVER a raw substring of "
    "styled/wrapped output (it passes in a wide interactive terminal but fails in CI's narrow non-TTY). "
    "Place new test files mirroring the repository's existing test-directory layout (e.g. tests/<layer>/), "
    "never a flat tests/ root. "
    "ENUMERATE THE COMPLETE SET: when you list a set drawn from the source (allowed values, "
    "placeholder/context keys, columns, options, validation rules), enumerate the FULL set verified "
    "against the source and cite the FULL line range — a partial/representative subset (e.g. listing "
    "10 of 12 keys) is a defect, and the design table and the plan MUST list the same set. "
    "SELF-REVIEW before finishing: re-read the artifact for internal consistency — API verbs/paths "
    "agree throughout, every signature used matches the one defined, the design and the plan agree on "
    "every signature/key-set/route (if the plan refines a design detail, fix the design to match), no "
    "section contradicts another, and no unverified 'should exist' assumption or placeholder step "
    "(e.g. a step with no real code) remains.\n"
)

# All body write-backs route through the pinned, marker-preserving helper ONLY (raw
# ``gh issue edit`` is denied). Stated in every stage that writes the body.
_WRITE_BACK = (
    "All ticket-body write-backs go through `kanban-update-body {{code}}` ONLY (it preserves the "
    "**roadmap**/**codename**/**design**/**plans** markers and validates body↔title coherence) — "
    "NEVER raw `gh issue edit` or a GraphQL mutation.\n"
)

# Clean-stop discipline (firm-exit): after kanban-done the agent must END its turn so the reaper's
# end_session lands on an EMPTY idle prompt with NO background shells (the helm #5 condition: a
# leftover next-stage slash-command in the box + "N shells still running" blocked the C-c/C-d exit).
# The engine's robust end_session + kill-escalation is the guarantee; this reduces the condition at
# the source. NB: the wording stays GENERIC ("the next-stage slash command") — it must NOT embed a
# literal ``/implement:…`` example (ironic in a "don't type the next command" instruction, and it
# would inject a spurious /implement: substring into prompts that legitimately carry none).
_CLEAN_STOP = (
    "AFTER running `kanban-done {{code}}`, END your turn IMMEDIATELY: do NOT type, suggest, or run "
    "the next-stage slash command, and do NOT leave background shells running (no trailing `&` on "
    "any command). Leave the prompt EMPTY and idle.\n"
)

# Backlog -> Brainstorming: the ONLY interactive step. The agent gathers requirements
# (it MAY ask — the tmux session is resumable), derives the codename, and APPENDS the
# brainstorm OUTPUT under a `## Brainstorm` heading — it must NEVER overwrite the seeded
# description or the **roadmap** marker (§29.4: the brainstorm append, not overwrite).
#
# Phase 39b (R2, live #146): brainstorming is the FIRST stage — the cheapest place to
# catch already-shipped work, so the prompt now carries a STATE CHECK FIRST block (the
# shared early-stage _STATE_CHECK_EARLY, set-codename instead of set-roadmap so the
# Done card still carries its marker) BEFORE the interactive Q&A. On #146 the agent
# self-checked out of pure judgment, found ALREADY_SHIPPED, then stopped WITHOUT moving
# the card (no INSTRUCTED exit). The state-check now mandates the Done move (it OVERRIDES
# the normal DONE checklist) and the agent only enters the interactive brainstorm when
# the feature is NOT already shipped. There is no IDENTITY block here (the brainstorm
# self-derives the codename), so the state check leads.
_BRAINSTORM_PROMPT = (
    "/implement:brainstorm Brainstorm the ticket {{code}} — {{title}}.\n"
    + _SCOPE_GUARD
    + "STATE CHECK FIRST (before the interactive brainstorm below): if repo-local evidence "
    "(ROADMAP.md, docs/archive/features/, git log, the code) shows this feature is ALREADY "
    "shipped, do NOT brainstorm or redo the work: post an evidence comment via "
    '`kanban-comment {{code}} "already shipped: <evidence>"` FIRST, then set the **codename** '
    "marker via `kanban-update-body {{code}} --set-field codename <the-shipped-codename>`, then "
    "`kanban-move {{code}} Done` — this move is MANDATORY: it OVERRIDES (replaces) the normal DONE "
    "checklist below, so the ALREADY_SHIPPED exit is NOT complete until the card is actually in "
    "Done. Then run `kanban-done {{code}}` WITHOUT starting the interactive brainstorm, and END "
    "your turn (do NOT type or run the next-stage slash command; no trailing-`&` background "
    "shells).\n" + "Sources (related context only — NOT your feature spec; your spec is the ticket "
    "description + what you gather): ticket description:\n{{ticket_body}}\nlinked issue:\n"
    "{{issue_body}}\ncomments:\n{{comments}}\n"
    "Otherwise (NOT already shipped) gather the requirements INTERACTIVELY: you MAY ask the user "
    "clarifying questions (this session is resumable — a human will `tmux attach` to answer). "
    "Derive a codename. Do NOT write the formal design.md yet (the next step does).\n"
    'Record your milestones via `kanban-progress {{code}} "…"` as you go.\n'
    + _WRITE_BACK
    + "IMPORTANT: APPEND the brainstorm OUTPUT (requirements, decisions, open questions) UNDER a "
    "`## Brainstorm` heading via "
    "`kanban-update-body {{code}} --append-section '## Brainstorm'` (read the text from stdin) — "
    "NEVER overwrite the seeded description or the **roadmap** line. Then record the codename via "
    "`kanban-update-body {{code}} --set-field codename <the-chosen-codename>`.\n"
    "DONE = brainstorm appended under ## Brainstorm + **codename** marker set. Write those durable "
    "outputs BEFORE ending. (ALREADY_SHIPPED case: DONE = evidence comment + **codename** marker + "
    "card moved to Done — see STATE CHECK FIRST above, which OVERRIDES this checklist.) If they "
    "already exist (re-entry), VERIFY and finalize — do NOT redo.\n"
    "Run `kanban-done {{code}}` once the brainstorm output + codename are recorded.\n" + _CLEAN_STOP
)

# Brainstorming -> Spec: AUTONOMOUS design. Reads the brainstorm output already in the
# ticket body and writes the design into docs/features/{{codename}}/ — no questions.
_DESIGN_PROMPT = (
    "Write the design for {{code}} ({{codename}}) FROM the brainstorm output already in the ticket "
    "description:\n{{ticket_body}}\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + _STATE_CHECK_EARLY
    + _DESYNC
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + "Write the design into `docs/features/{{codename}}/` (DESIGN.md), and record your milestones "
    'via `kanban-progress {{code}} "…"` as you go.\n'
    + _WRITE_BACK
    + "COMMIT (durable cross-stage carry, DESIGN §13): after writing DESIGN.md, commit it to this "
    "worktree's per-ticket branch so the NEXT stage's worktree sees it. ONLY once "
    "docs/features/{{codename}}/ exists with the codename set (you set **codename** earlier — do "
    "NOT commit with an empty codename, which would stage the whole docs/features/ tree), run the "
    "stage and the commit as TWO SEPARATE commands, each on its own line (the docs profile allows "
    "`git add` and `git commit` as SEPARATE allow-patterns — running them joined on ONE line with "
    "`&&` may NOT match either pattern and would be DENIED headlessly, so keep them apart):\n"
    "  1. `git add docs/features/{{codename}}/`\n"
    '  2. `git commit -m "docs({{codename}}): design"`\n'
    "Both are LOCAL commits, no push. The worktrees share one .git, so "
    "the committed design is visible to the plan/create-branch stages WITHOUT any push.\n"
    + "IMPORTANT: record the design path as a REPO-RELATIVE path (NOT an absolute worktree path — "
    "the next stage gets a different worktree) via "
    "`kanban-update-body {{code}} --set-field design docs/features/{{codename}}/DESIGN.md`.\n"
    "DONE = DESIGN.md written under docs/features/{{codename}}/ + COMMITTED to the per-ticket branch "
    "+ **design** marker set to the repo-relative path (durable outputs BEFORE any kanban-move). "
    "(ALREADY_SHIPPED case: DONE = evidence comment + card moved to Done — see STATE CHECK above, "
    "which OVERRIDES this checklist.) If the design already exists (re-entry), VERIFY and finalize "
    "— do NOT redo. Run `kanban-done {{code}}` once the design is written + committed.\n"
    + _CLEAN_STOP
)

# Spec -> Plan: AUTONOMOUS /implement:plan. Precondition: {{design_path}} MUST be
# non-empty (the prior stage recorded it); an empty design path is a desync, not a
# cue to guess.
_PLAN_PROMPT = (
    "/implement:plan Prepare the plan for {{code}} ({{codename}}) from the design {{design_path}} "
    "and main. Write the plan files into `docs/features/{{codename}}/plan/`.\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + _STATE_CHECK_EARLY
    + _DESYNC
    + "PRECONDITION: {{design_path}} must be a real, non-empty design path. The Design stage "
    "recorded it as a REPO-RELATIVE path (e.g. docs/features/{{codename}}/DESIGN.md) and COMMITTED "
    "the file to this worktree's per-ticket branch, so you can `cat {{design_path}}` directly. If "
    "it is empty (the Design stage did not record **design**), that is a DESYNC — follow the DESYNC "
    "protocol, do NOT guess a path.\n"
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + _WRITE_BACK
    + "COMMIT (durable cross-stage carry, DESIGN §13): after writing the plan files, commit them to "
    "this worktree's per-ticket branch so create-branch's worktree inherits them. ONLY once "
    "docs/features/{{codename}}/ exists with the codename set (do NOT commit with an empty codename "
    "— that would stage the whole docs/features/ tree), run the stage and the commit as TWO "
    "SEPARATE commands, each on its own line (the docs profile allows `git add` and `git commit` as "
    "SEPARATE allow-patterns — running them joined on ONE line with `&&` may NOT match either "
    "pattern and would be DENIED headlessly, so keep them apart):\n"
    "  1. `git add docs/features/{{codename}}/`\n"
    '  2. `git commit -m "docs({{codename}}): plan"`\n'
    "Both are LOCAL commits, no push. The shared .git makes the committed plan visible to the "
    "create-branch stage WITHOUT any push.\n"
    + "IMPORTANT: record the plan paths as REPO-RELATIVE paths via "
    "`kanban-update-body {{code}} --set-field plans docs/features/{{codename}}/plan/<plan1>.md, "
    "docs/features/{{codename}}/plan/<plan2>.md, ...`.\n"
    'Record your milestones (paths, phase/sub-phase todos) via `kanban-progress {{code}} "…"` as '
    "you go.\n"
    "DONE = plan files written under docs/features/{{codename}}/plan/ + COMMITTED to the per-ticket "
    "branch + **plans** marker set to the repo-relative paths (durable outputs BEFORE any "
    "kanban-move). (ALREADY_SHIPPED case: DONE = evidence comment + card moved to Done — see STATE "
    "CHECK above, which OVERRIDES this checklist.) If the plans already exist (re-entry), VERIFY and "
    "finalize — do NOT redo. Run `kanban-done {{code}}` to end your session.\n" + _CLEAN_STOP
)

# ReadyToDev -> PrepareFeature: the create-branch stage. Gains autonomy + identity +
# empty-{{design_path}}/{{plan_paths}} preconditions. The card now sits in
# PrepareFeature and a worktree EXISTS (LaunchAction provisions one for every launch),
# so this is past the skip-to-Done boundary: a shipped exit is Blocked, not Done
# (Done is NOT whitelisted from PrepareFeature — it would roll back).
_PREPARE_PROMPT = (
    "/implement:create-branch Prepare the implementation of {{code}} ({{codename}}): create the "
    "branch, commit the design+plan, initialize IMPLEMENTATION.md.\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + _STATE_CHECK_LATE
    + _DESYNC
    + "PRECONDITION: {{design_path}} AND {{plan_paths}} must both be non-empty (the Design + Plan "
    "stages recorded them). If either is empty, that is a DESYNC — follow the DESYNC protocol, do "
    "NOT guess.\n"
    + _AUTONOMY
    + "DONE = branch created + design/plan committed + IMPLEMENTATION.md initialized (durable "
    "outputs BEFORE any kanban-move). If the branch already exists (re-entry), VERIFY and finalize "
    "— do NOT redo. Then run `kanban-done {{code}}` to end your session.\n" + _CLEAN_STOP
)

# PrepareFeature -> InProgress: implement all phases. Late-stage (a worktree/branch
# exists), so the shipped exit is Blocked, not Done.
#
# STOP-AT-PR-CREATION (hybrid flow, DESIGN §13). /implement:phase auto-chains to feature-pr →
# pr-review, whose terminal step is `gh pr merge` (DENIED by the universal deny-list). Left
# unguarded the agent stalls mid-chain on the denied merge and NEVER reaches kanban-move/kanban-done
# → the session parks WAITING with no done breadcrumb, and the Change-1 backstop never fires either.
# So this prompt makes the stop explicit (mirroring _REVIEW_PROMPT's merge-skip block) PLUS a
# CI-not-green TERMINAL branch (do NOT idle waiting on CI — an idling session drops no done
# breadcrumb and parks WAITING forever).
_IMPLEMENT_PROMPT = (
    "/implement:phase Implement all remaining phases of {{code}} ({{codename}}).\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + _STATE_CHECK_LATE
    + _DESYNC
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + "STOP AT PR CREATION: /implement:phase auto-chains to feature-pr → pr-review, which ends in "
    "`gh pr merge` (DENIED). STOP as soon as the PR is created and CI is pushed. NEVER run "
    "`gh pr merge` (or any merge command) under any circumstance — merge is HUMAN-ONLY.\n"
    + "DO NOT MOVE THE CARD: never run `kanban-move` into PR/CI (or any column) — InProgress→PR/CI "
    "is a SCRIPT-gated transition the ENGINE owns. The engine auto-advances the card to PR/CI for "
    "you when you end cleanly; if you moved it yourself the PR/CI gate (`check-pr-ready.sh`), the "
    "auto-promote to Review, and the stage finalize would all be skipped.\n"
    + "CI-NOT-GREEN TERMINAL BRANCH: do NOT idle waiting on CI inside this session (an idling "
    "session never ends → it parks WAITING forever). Once the PR is created and the branch is "
    "pushed, you are DONE even if CI is still running or red — comment any known-failing checks via "
    '`kanban-comment {{code}} "CI red: <failing checks>"`, then end. The PR/CI gate + the fix-CI '
    "loop own the retry, not this session.\n"
    + "DONE = all phases implemented + the PR created (CI pushed — the durable outputs are the "
    "pushed branch + the open PR). If the PR already exists (re-entry), VERIFY and finalize — do "
    "NOT redo. Do NOT move the card.\n"
    "Finally, run `kanban-done {{code}}` to end your session — the engine then advances the card to "
    "PR/CI.\n" + _CLEAN_STOP
)

# PRCI -> InProgress: the bot fix-CI loop. {{script_output}} may be STALE — re-check
# the LIVE CI before acting, with a green-already fast path, bounded to the failing
# checks only.
_FIXCI_PROMPT = (
    "The CI of {{code}} ({{codename}})'s PR was reported red. The captured output below MAY BE "
    "STALE:\n{{script_output}}\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + _STATE_CHECK_LATE
    + _DESYNC
    + "FIRST re-check the LIVE CI status of the PR. If CI is ALREADY GREEN (the captured output "
    "was stale), do NOT change code — just `kanban-done` and end. Otherwise fix ONLY the checks "
    "that are actually failing (do not refactor beyond the failure), then re-push.\n"
    + "DO NOT MOVE THE CARD: never run `kanban-move` into PR/CI (or any column) — InProgress→PR/CI "
    "is a SCRIPT-gated transition the ENGINE owns (advance:auto:PRCI). After you `kanban-done`, the "
    "engine advances the card to PR/CI and re-runs the gate; the gate + this fix-CI loop own the "
    "retry, not this session.\n"
    + "NEVER run `gh pr merge` (or any merge command) — merge is HUMAN-ONLY. Do NOT idle waiting "
    "on CI inside this session (an idling session never ends → it parks WAITING forever): after "
    "re-pushing your fix, `kanban-done {{code}}` immediately even if CI is still running or still "
    "red — the engine advances + re-gates; this session must not babysit CI.\n"
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + "DONE = the failing checks are addressed + re-pushed (or confirmed already green) THEN "
    "`kanban-done`. If already handled (re-entry), VERIFY and finalize — do NOT redo.\n"
    "Finally, run `kanban-done {{code}}` to end your session.\n" + _CLEAN_STOP
)

# PRCI -> Review: the review rounds. The pr-review skill ends in a terminal squash-
# merge step — that step is SKIPPED here (merge is human-only, DESIGN §10), plus a
# verbatim gh-pr-merge ban.
_REVIEW_PROMPT = (
    "/implement:pr-review Run the review rounds of {{code}} ({{codename}}) WITHOUT merging.\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + _STATE_CHECK_LATE
    + _DESYNC
    + "The /implement:pr-review skill ends with a terminal squash-merge step — that final merge "
    "step is SKIPPED (merge is HUMAN-ONLY): run every review + fix round but STOP before it. NEVER "
    "run `gh pr merge` (or any merge command) under any circumstance.\n"
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + "DONE = all review rounds run + fixes pushed, the PR left OPEN for a human to merge (durable "
    "outputs BEFORE any move). If review already completed (re-entry), VERIFY and finalize — do "
    "NOT redo.\n"
    "Finally, run `kanban-done {{code}}` to end your session.\n" + _CLEAN_STOP
)

# Review -> InProgress: operator-requested REWORK (#12). A human moved the card back from Review
# to InProgress to request changes — mirrors the PRCI->InProgress fix-CI pattern (profile dev,
# advance auto:PRCI), but the trigger is human review feedback, not a red CI gate.
_REWORK_PROMPT = (
    "{{code}} ({{codename}}) was moved back from Review to InProgress — the human reviewer wants "
    "REWORK on the open PR.\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + _STATE_CHECK_LATE
    + _DESYNC
    + "FIRST read the PR's review threads / comments to find what the reviewer asked for. Address "
    "ONLY the requested changes (do not refactor beyond the review feedback), then re-push.\n"
    + "DO NOT MOVE THE CARD: never run `kanban-move` into PR/CI — Review→InProgress→PR/CI is "
    "engine-owned (advance:auto:PRCI). After you `kanban-done`, the engine advances the card to "
    "PR/CI and re-runs the CI gate.\n"
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + "DONE = the review feedback is addressed + re-pushed THEN `kanban-done`. If the rework was "
    "already applied (re-entry), VERIFY and finalize — do NOT redo.\n"
    "Finally, run `kanban-done {{code}}` to end your session.\n" + _CLEAN_STOP
)

# Review -> Merge: the AUTONOMOUS merge stage (operator decision — supersedes the historical
# merge=human-only floor for THIS transition only). A claude agent under the dedicated ``merge``
# permission profile (the SOLE profile whose deny-list lifts ``gh pr merge`` — force-push / rebase /
# history-rewrite / direct-main-push stay banned even here) brings the PR up to date with main
# (merge-main-IN, never rebase/force-push — intelligent conflict resolution), waits for CI to be
# fully green, then SQUASH-MERGES via ``gh pr merge --squash``. Success → it moves the card to Done;
# any blocker (unresolvable conflict, CI red/stuck, not mergeable) → it comments + moves the card
# back to Review for a human, never leaving a half-merged state. ``advance:stop`` — the agent routes
# explicitly (Done|Review), there is no engine auto-advance.
_MERGE_PROMPT = (
    "You are the AUTONOMOUS MERGE stage for ticket {{code}} ({{codename}}). Goal: bring its pull "
    "request up to date with ``main``, confirm CI is fully green, then SQUASH-MERGE it to main.\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + _STATE_CHECK_LATE
    + _DESYNC
    + "Do these steps IN ORDER; on ANY blocker, STOP and route to Review (below) — never force it:\n"
    "1. RESOLVE + BIND THE PR (ticket binding — never merge an unrelated PR): take this worktree's "
    "branch from `git branch --show-current` and run `gh pr list --head <branch> --state open`. If "
    "that finds no PR (the worktree may be on the WIP branch `kanban/ticket-{{code}}` rather than the "
    "PR's `feat/<codename>` head), fall back to resolving by ticket: `gh pr list --search "
    '"{{code}} in:title" --state open` (or the issue→PR link). EITHER way you MUST end with EXACTLY '
    "ONE open PR whose base is ``main`` AND whose title/linked work is ticket {{code}}; record its "
    "head branch and PR number. If zero match, more than one matches, the base is not main, or it is "
    "not ticket {{code}}'s PR — do NOT guess or merge a PR number from anywhere else: route to Review "
    "(step below) with a comment. You may ONLY ever merge ticket {{code}}'s own PR.\n"
    "2. UP TO DATE WITH MAIN — merge main INTO the PR branch (NEVER rebase, NEVER force-push): "
    "`git fetch origin main` then `git merge origin/main`. On CONFLICTS, resolve INTELLIGENTLY: for "
    "version files (VERSION, pyproject.toml, src/kanbanmate/__init__.py, the two .claude-plugin "
    "manifests) keep the HIGHER / most coherent SemVer; for code, integrate BOTH sides preserving "
    "each change's intent — READ the surrounding source to understand it (grounding discipline "
    "below), never blind-pick a side. Then run `make check` to PROVE the merged tree is sound, and "
    "`git push` the merge commit to the PR branch (a NORMAL push — NEVER `--force`/`-f`, NEVER push "
    "to ``main`` directly).\n"
    "3. WAIT FOR CI: poll `gh pr checks <pr>` until EVERY check is conclusively GREEN. Do NOT merge "
    "while any check is pending or failing. Do NOT idle-spin forever: poll a BOUNDED number of times "
    "with short sleeps; if CI is still pending/failing after a reasonable wait, treat it as "
    "not-ready and route to Review.\n"
    "4. CONFIRM MERGEABILITY: `gh pr view <pr> --json mergeable,mergeStateStatus` must be "
    "MERGEABLE / CLEAN.\n"
    "5. SQUASH-MERGE: `gh pr merge <pr> --squash` — this is the ONLY merge command you may run (it "
    "merges through the GitHub API). You must NEVER `git push` to ``main``, NEVER `gh api …/merge`, "
    "NEVER a GraphQL merge mutation, NEVER rebase/force-push/rewrite history.\n"
    "ON SUCCESS (the squash-merge landed): `kanban-move {{code}} Done`.\n"
    "ON ANY BLOCKER (unresolvable conflict, CI red or stuck, not mergeable, the merge command "
    'refused): do NOT retry blindly — `kanban-comment {{code}} "merge blocked: <grounded reason>"` '
    "then `kanban-move {{code}} Review` so a human can triage. NEVER leave a half-merged or broken "
    "state on the branch.\n"
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + "DONE = EITHER the PR is squash-merged AND the card moved to Done, OR the card is moved back "
    "to Review with a grounded blocker comment. If re-entered after a partial run, VERIFY the "
    "current PR/branch state FIRST and finalize — do NOT redo a merge that already landed.\n"
    "Finally, run `kanban-done {{code}}` to end your session (AFTER the kanban-move).\n"
    + _CLEAN_STOP
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
    # Backlog → Brainstorming: the ONLY interactive step (a human tmux-attaches to
    # answer the agent's clarifying questions). Writes the brainstorm output +
    # codename to the ticket body — NOT the formal design.
    {
        "from": "Backlog",
        "to": "Brainstorming",
        "profile": "docs",
        "prompt": _BRAINSTORM_PROMPT,
        # HYBRID flow (DESIGN §13): the brainstorm completes (kanban-done) → the engine backstop
        # (bin/kanban_session_end._auto_advance) moves the card to Spec, firing the design stage.
        "advance": "auto:Spec",
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
        # Planned, where it STOPS (the only pre-build HUMAN review gate; Plan→Planned is a no-op).
        "advance": "auto:Planned",
        "permission_mode": "auto",
    },
    # Plan → Planned: no-op. Autonomous design+plans are done; the card lands in
    # Planned for human review.
    {"from": "Plan", "to": "Planned"},  # allowed no-op
    {"from": "Planned", "to": "ReadyToDev"},  # allowed no-op (human gate)
    # Planned → Spec: operator-recovery no-op (#12). A rejected plan can re-fire the
    # autonomous design via Spec → Plan (no agent launches on THIS edge — the human
    # moves the card back to Spec, then Spec → Plan re-runs /implement:plan).
    {"from": "Planned", "to": "Spec"},  # allowed no-op (recovery: re-plan)
    {
        "from": "ReadyToDev",
        "to": "PrepareFeature",
        "profile": "prepare",
        "prompt": _PREPARE_PROMPT,
        # HYBRID flow (DESIGN §13): create-branch completes → the engine backstop moves the card to
        # InProgress, firing the implement stage (the human already gated at Planned→ReadyToDev).
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
    # Human: review rounds.
    {
        "from": "PRCI",
        "to": "Review",
        "profile": "dev",
        "prompt": _REVIEW_PROMPT,
        "advance": "stop",
        "permission_mode": "auto",
    },
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
    # AUTONOMOUS MERGE (operator decision): a claude agent under the dedicated ``merge`` profile
    # (the SOLE profile whose deny lifts ``gh pr merge``) brings the PR up to date with main
    # (merge-main-IN, intelligent conflict resolution — never rebase/force-push), waits for CI to be
    # fully green, then squash-merges via ``gh pr merge --squash``. ``advance:stop`` — the agent
    # routes itself: success → Done, any blocker → back to Review (the agent's explicit kanban-move).
    #
    # PRE-LAUNCH CI GATE (audit §6 defense-in-depth): ``bin/check-pr-ready.sh`` runs BEFORE the agent
    # launches — a red/pending CI fails the gate and ``on_fail:move:Review`` bounces the card back to
    # Review WITHOUT starting the merge agent (don't even attempt a merge on a red PR). NOTE this
    # checks the PRE-merge-IN CI; the agent's own CI-wait after merging main in is the second layer,
    # and a server-side ``required_status_checks`` branch ruleset on the default branch is the
    # AUTHORITATIVE third layer (recommended — without it ``gh pr merge`` is not server-gated on CI).
    {
        "from": "Review",
        "to": "Merge",
        "profile": "merge",
        "prompt": _MERGE_PROMPT,
        "script": "bin/check-pr-ready.sh",
        "on_fail": "move:Review",
        "advance": "stop",
        "permission_mode": "auto",
    },
    {
        "from": "Merge",
        "to": "Done",
    },  # success route (the merge agent moves here after squash-merge)
    # Failure route: the merge agent moves the card BACK to Review (a plain no-op edge — it does NOT
    # re-fire Review→Merge, which only triggers on a move INTO Merge) so a human can triage a blocked
    # merge (unresolvable conflict / red CI / not mergeable).
    {"from": "Merge", "to": "Review"},
    # Done → Backlog: operator-recovery reopen (#12). A PLAIN no-op whitelist edge — NOT a
    # RESET (the whitelist schema carries no `action:` field, and decide() hard-wires RESET to
    # the reactive Cancel column; a Done-as-RESET would touch the whitelist model). So this is a
    # no-op: it makes Done → Backlog a KNOWN transition (no rollback) but does NOT wipe stale
    # persisted state. Per the rank-7 verdict that is acceptable — after teardown-on-Done (#9)
    # reclaims live agents' worktrees and session-end purges state, residual state on a Done
    # ticket is already rare, so the no-op variant loses little. Re-seed-fresh-board stays the
    # primary recovery doctrine; this is a convenience reopen.
    {"from": "Done", "to": "Backlog"},  # allowed no-op (recovery: reopen)
    # Early skip-to-Done (genesis phase 26, e2e-driven). A single list-expanded
    # no-op entry whitelists the six PRE-PrepareFeature columns → Done so an
    # agent/human can mark an ALREADY-DONE ticket Done without a rollback. It
    # cartesian-expands to six explicit no-op edges (no prompt/script). BOUNDED at
    # ReadyToDev: from PrepareFeature onward a worktree/branch exists, so retirement
    # must go through Cancel (teardown) — Done is deliberately NOT whitelisted from
    # PrepareFeature/InProgress/PRCI/Review/Merge (a direct → Done there rolls back).
    {
        "from": ["Backlog", "Brainstorming", "Spec", "Plan", "Planned", "ReadyToDev"],
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
