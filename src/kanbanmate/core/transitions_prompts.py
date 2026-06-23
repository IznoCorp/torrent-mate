"""Agent launch-prompt constants for the default transition table (extracted from
transitions_defaults to keep both modules under the 1000-LOC ceiling).

Pure string templates filled at dispatch by ``kanbanmate.core.placeholders.fill`` — no I/O, no
imports below ``core``. The shared hardening fragments (identity/state/autonomy/clean-stop) and
every per-stage prompt live here; ``transitions_defaults`` imports them to build
:data:`~kanbanmate.core.transitions_defaults.DEFAULT_TRANSITIONS`.
"""

from __future__ import annotations

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

# Triage -> Brainstorming: the ONLY interactive step. The agent gathers requirements
# (it MAY ask — the tmux session is resumable), derives the codename, and APPENDS the
# brainstorm OUTPUT under a `## Brainstorm` heading — it must NEVER overwrite the seeded
# description or the **roadmap** marker (§29.4: the brainstorm append, not overwrite).
# (skiff: this is now the FULL-lane head, wired on Triage → Brainstorming — TRIAGE is the
# first stage; the lite/express lanes never reach it.)
#
# Phase 39b (R2, live #146): brainstorming is the cheapest place to catch already-shipped
# work, so the prompt now carries a STATE CHECK FIRST block (the shared early-stage
# _STATE_CHECK_EARLY, set-codename instead of set-roadmap so the Done card still carries
# its marker) BEFORE the interactive Q&A. On #146 the agent
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
    "Otherwise (NOT already shipped) gather the requirements. BRAINSTORM INTERACTION DISCIPLINE "
    "(this is the full-lane brainstorm — the ONE sanctioned human-Q&A pause; this session is "
    "resumable, a human will `tmux attach` to answer). Your default posture is DECIDE, RECORD, and "
    "PROCEED. You MAY ask genuine clarifying questions, but you MUST NEVER ask the user to confirm, "
    "validate, approve, or rubber-stamp a choice you have already made — there is no 'does this look "
    "right?' gate. SORT every open point into exactly one bucket: "
    "ASK (genuine human decision) ONLY when ALL hold: it is a material PRODUCT/UX/taste choice with "
    "NO defensible default, OR an irreversible / expensive-to-undo / real-outward-effect action, OR a "
    "genuinely ambiguous / contradictory requirement where the ticket underdetermines scope so "
    "guessing risks building the WRONG thing, OR it crosses a sensitivity / safety / policy boundary; "
    "AND no repo convention, ticket text, linked issue, or existing code already settles it; AND "
    "guessing wrong is not cheaply reversible. Batch ALL ASK points into a SINGLE up-front "
    "AskUserQuestion round — one well-scoped multiple-choice question per fork, each with a "
    "recommended default — do NOT drip-feed one question per message. "
    "DECIDE (everything else — MOST of a brainstorm — never ask): codename, internal data-shape, "
    "which existing query / fragment / module to ride, back-compat strategy, default values, the test "
    "list, YAGNI deferrals, file/symbol naming, the SemVer bump. MAKE the call per repo conventions "
    "and RECORD it under ## Brainstorm as a settled decision — 'Decided: <X>; rationale: <evidence "
    "path:line>; alternative considered: <Y>' — never as a proposal awaiting approval, never gated. "
    "Derive the codename and SemVer bump YOURSELF and record them — do NOT pause to confirm or wait "
    "for an override (an operator override later still wins, but absence of a reply is NOT a gate). "
    "If you can reason a point to a clear answer from the code or conventions, it is a DECIDE, not an "
    "ASK. "
    "ONCE THE GENUINE QUESTIONS ARE ANSWERED (or there were none) THE DESIGN IS DETERMINED — "
    "FINALIZE, DO NOT RE-CONFIRM: the user's answers plus your recorded decisions ARE the brainstorm; "
    "there is nothing left to bless. A trailing 'Does this look right? Once you confirm I'll "
    "record it…' over content the human has already settled is FORBIDDEN — it converts a finished "
    "brainstorm into a hung stage (the #82 failure). A notification you continue PAST ('Recorded the "
    "design under ## Brainstorm; summary follows') is fine; a blocking 'confirm before I record' is "
    "not. GENUINE QUESTION STILL OPEN (surfaced late, or unanswered after the batched round)? Do NOT "
    "block: record it under a `### Open questions` sub-section of ## Brainstorm — the question, your "
    "provisional default, and why it is unresolved — and finalize anyway (the HYBRID flow's "
    "downstream ReadyToDev human gate is where lingering decisions get resolved). Never silently "
    "auto-decide a risky / irreversible / product-defining / sensitivity call: surface it live in the "
    "batched round, or record it under ### Open questions — never bury it. The brainstorm must ALWAYS "
    "reach kanban-done; never end your turn parked on a question with no kanban-done. "
    "Do NOT write the formal design.md yet (the next step does).\n"
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

# Backlog -> Triage: the skiff fast-track CLASSIFIER (cheap, read-only). It classifies the ticket on
# two axes (SIZE × SENSITIVITY), records the lane (durable **track** field + the kanban-route
# breadcrumb the engine consumes), and ends. The ENGINE then routes the card to the lane's entry
# column (bin/kanban_session_end._routed_advance, advance: route). Conservative-by-construction: any
# doubt / any sensitivity / any self-failure → ``full``. It writes no code and opens no PR, so it is
# the cheapest place to gate effort. There is no IDENTITY/STATE block here (it precedes the lane
# heads which carry their own); it leads with the routing instruction.
_TRIAGE_PROMPT = (
    "/kanban Triage ticket {{code}} ({{codename}}) onto a fast-track lane.\n"
    + _IDENTITY_THEN_STATE
    + "You are the skiff TRIAGE stage. Classify this ticket on TWO axes and route it:\n"
    "- SIZE measures NOVEL DESIGN DECISIONS / UNKNOWNS / IRREVERSIBLE CHOICES — NOT files-touched, "
    "layers-crossed, or lines changed. Threading one already-determined value (a field, a flag, a "
    "rename) through N existing layers along a path the code already walks is mechanical for ANY N; "
    "breadth is not effort. In a hexagonal codebase EVERY visible value crosses GraphQL → parser → "
    "domain → endpoint → component by construction, so if file-count drove size NO display-a-field "
    "ticket could ever be small and the fast lanes would be dead on arrival. The `rg`/`grep` peek is "
    "to CONFIRM a change is mechanical and bounded (no hidden fan-out, no missing call-site) — NOT to "
    "count files to inflate the bucket. Do NOT start implementing.\n"
    "  SIZING QUESTIONS — ask all three; the answer-count is the size:\n"
    "  - Q1 NOVEL DECISION: Does it force a genuine OPEN design question someone must ANSWER (a new "
    "schema/algorithm/protocol/API shape/data flow, or a real-trade-off choice) — vs mechanically "
    "APPLYING a change whose shape, data source, and contract existing code or the ticket already "
    "determine?\n"
    "  - Q2 UNKNOWN: Is there a real unknown to investigate before you can say what the change is "
    "(where the value comes from, whether the approach works, what it touches)?\n"
    "  - Q3 IRREVERSIBLE / RISKY: Does it make a hard-to-reverse or high-regression-risk choice (data "
    "migration, irreversible state change, public-contract break, concurrency/ownership protocol)? A "
    "small/mechanical edit to a CONCURRENCY, RATE-LIMIT, IDEMPOTENCY, PERSISTENCE, HMAC/SIGNATURE, or "
    "BOARD-WRITE surface is YES regardless of edit size — the breadth-is-not-effort rule does NOT "
    "deflate a risk-bearing module; when unsure whether a touched module is risk-bearing, treat it as "
    "YES.\n"
    '  SELF-TEST when unsure: "How many questions must I ANSWER before I know exactly what to '
    'write?" Zero → trivial/small. One or more genuine ones → substantial. A long but '
    "already-answered checklist (several sub-requirements ≠ several novel decisions) is still small.\n"
    "  - trivial = NO to Q1/Q2/Q3 AND a single tiny edit (one line / one config flag / one constant) "
    "on a surface needing no design+plan artifact.\n"
    "  - small = NO to Q1/Q2/Q3 but a non-trivial-yet-mechanical surface — a bounded UI/component "
    "change, a list filter/scroll/overflow fix in one panel, a rename across N call-sites, a flag "
    "added at N sites, or one already-determined value propagated through existing layers. ANY number "
    "of files is still small as long as every touch is mechanical and nothing is undecided. (e.g. "
    "#82 per-card CLOSED badge: add `state` to the existing board GraphQL fragment, one optional "
    "`closed: bool = False` on the frozen Ticket, thread through two card builders, render one token "
    "in two panels — data source/field-shape/GraphQL-cost all already determined, diff() keys only "
    "item_id/column_key so no invariant moves → ~6 files, 0 novel decisions → small.)\n"
    "  - substantial = YES to at least one of Q1/Q2/Q3 — a real open design question, a true unknown, "
    "or an irreversible/risky choice. This is the ONLY bucket that signifies genuine effort; "
    "multi-file mechanical work is NOT substantial. (e.g. #79 round-trip rich-text editor with "
    "protected-region invariants + golden-file serializer contract; #91 cross-instance "
    "locking/ownership protocol on shared state.)\n"
    "- SENSITIVITY: read `.claude/kanban/sensitive.yml`. If the ticket's probable scope matches any "
    "sensitive path glob or keyword, OR the ticket carries a `sensitive`/listed `area:*` label → it "
    "is SENSITIVE.\n"
    "DECIDE by running this DECISION TREE in order — STOP at the first match:\n"
    "  1. SENSITIVE? A `.claude/kanban/sensitive.yml` path/keyword match, a `sensitive`/listed "
    "sensitive label, OR multiple/conflicting `track:*` labels (ambiguous) → `full`. This hard guard "
    "is checked FIRST and is NEVER overridden down.\n"
    "  2. CANNOT ASSESS? If you genuinely cannot determine size — the ticket is too vague to scope, or "
    "the `rg`/`grep` peek reveals hidden fan-out / an unknown you can't resolve in this read-only pass "
    "→ `full`. (The conservative default for a REAL inability to assess — NOT for a change you "
    "understand that merely spans many files or you haven't finished reading.)\n"
    "  3. SUBSTANTIAL? YES to any SIZING QUESTION (Q1 novel design decision / Q2 unknown to "
    "investigate / Q3 irreversible-or-risky choice, INCLUDING any edit — however small — to a "
    "risk-bearing concurrency / rate-limit / idempotency / persistence / HMAC-signature / board-write "
    "surface) → `full`.\n"
    "  4. EXPLICIT OVERRIDE? If exactly ONE explicit `track:full|lite|express` label is present AND "
    "none of steps 1–3 forced `full`, honour it (post a kanban-comment noting the override). A "
    "`track:*` label routes only a NON-sensitive, NON-substantial ticket — it can NEVER pull a "
    "step-1/2/3 `full` DOWN, because the safety + size checks run FIRST and a down-override cannot "
    "bypass them.\n"
    "  5. SMALL? NO to all three SIZING QUESTIONS but a non-trivial mechanical surface (a UI/JSX edit, "
    "several files, or one obvious choice) → `lite`. A purely mechanical change is `lite` no matter "
    "how many files it touches.\n"
    "  6. TRIVIAL? NO to all three SIZING QUESTIONS AND a single tiny edit (one line / one config "
    "flag / one constant) needing no design+plan artifact → `express`.\n"
    "  SAFE means: no step-1 sensitivity hit. `express` = trivial AND safe; `lite` = small AND safe; "
    "`full` = substantial OR sensitive OR un-assessable.\n"
    "  TIE-BREAK DIRECTION: a tie between trivial and small breaks DOWN to the cheaper lane "
    '(express↔lite). "Any doubt → full" applies ONLY to DESIGN doubt — a live Q1/Q2/Q3 maybe-yes, a '
    "step-1 sensitivity hit, or step-2 inability-to-assess. Breadth, file count, or layers crossed is "
    "NOT doubt and NEVER breaks up; many mechanical files is small → lite.\n"
    "RECORD your decision, in this order:\n"
    "1. `kanban-update-body {{code}} --set-field track <lane>` (durable; read later by the review).\n"
    "2. `kanban-route {{code}} <lane>` (the routing breadcrumb the engine consumes).\n"
    "3. `kanban-done {{code}}` (end the session; the engine moves the card to the lane entry).\n"
    "Do NOT move the card yourself, do NOT write code, do NOT open a PR.\n" + _CLEAN_STOP
)

# Triage -> Scope: the skiff LITE lane head (a small, safe ticket). It produces a COMPRESSED
# design+plan in ONE pass — no separate brainstorm, no full DESIGN.md, no multi-phase plan. It first
# DERIVES + SETS the codename + SemVer bump (triage did not set the codename, so the SCOPE.md path
# depends on it being set first), THEN commits a SCOPE.md under docs/features/<codename>/ onto the
# per-ticket WIP branch so the build stage inherits it, and ends; the engine auto-advances the card
# to Prepare feature (build). It carries the autonomy + grounding discipline (it writes durable
# artifacts) but no human gate.
_SCOPE_PROMPT = (
    "/kanban Scope ticket {{code}} ({{codename}}) — the LITE fast-track design+plan in one pass.\n"
    + _SCOPE_GUARD
    + _IDENTITY_THEN_STATE
    + "You are the skiff LITE SCOPE stage (a small, safe ticket). You are HERE because triage found "
    "NO open design question, NO unknown, and NO irreversible/risky choice — only a bounded mechanical "
    "surface. Do NOT re-litigate the size or re-open a design question: APPLY the already-determined "
    "change. If you discover a GENUINE novel decision or a hidden unknown mid-scope, that is a "
    "mis-route — post a kanban-comment and `kanban-route {{code}} full` rather than guessing. Produce "
    "a COMPRESSED design+plan in a SINGLE pass — no separate brainstorm, no full DESIGN.md, no "
    "multi-phase plan:\n"
    "- DERIVE + SET THE CODENAME FIRST (triage did NOT set it, so `{{codename}}` is empty until you "
    "do — and the SCOPE.md path below DERIVES FROM it). Derive a codename + SemVer bump (usually "
    "patch/minor) and set the codename: "
    "`kanban-update-body {{code}} --set-field codename <codename>`.\n"
    "- THEN write a few-line scope note + a short checklist plan to "
    "`docs/features/<codename>/SCOPE.md` (under the codename you just set) and `git add` + "
    "`git commit` it (the WIP branch carries it to the build stage). Run `git add` and `git commit` "
    "as TWO SEPARATE commands, each on its own line (the docs profile allows them as SEPARATE "
    "allow-patterns — joining them with `&&` may match NEITHER and be DENIED headlessly):\n"
    "  1. `git add docs/features/<codename>/SCOPE.md`\n"
    '  2. `git commit -m "docs(<codename>): scope"`\n'
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + "DONE = SCOPE.md committed to the per-ticket branch + **codename** marker set. If they already "
    "exist (re-entry), VERIFY and finalize — do NOT redo. Then `kanban-done {{code}}` — the engine "
    "advances the card to Prepare feature (build).\n" + _CLEAN_STOP
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
    + "ADAPTIVE INPUTS (skiff): a prior stage may have left artifacts on the per-ticket WIP branch — "
    "inspect what is actually present, then proceed accordingly:\n"
    "- If `docs/features/{{codename}}/DESIGN.md` AND a plan dir exist (FULL lane) → use the codename "
    "+ bump already set; the {{design_path}}/{{plan_paths}} PRECONDITION below applies.\n"
    "- If only `docs/features/{{codename}}/SCOPE.md` exists (LITE lane) → use the codename already "
    "set; bump = the scope note's bump. There is no full DESIGN.md/plan dir — that is EXPECTED, not "
    "a DESYNC.\n"
    "- If NEITHER exists (EXPRESS lane) → derive the codename from the issue title (slug) and bump = "
    "patch; there is no DESIGN.md — the design rationale goes in the PR body. An empty "
    "{{design_path}}/{{plan_paths}} is EXPECTED for this lane, not a DESYNC.\n"
    + "PRECONDITION (FULL lane only): when a DESIGN.md + plan dir are present, {{design_path}} AND "
    "{{plan_paths}} must both be non-empty (the Design + Plan stages recorded them). If a full-lane "
    "design/plan exists on disk but its marker is empty, that is a DESYNC — follow the DESYNC "
    "protocol, do NOT guess. (For the LITE/EXPRESS lanes the markers are legitimately empty — see "
    "ADAPTIVE INPUTS above.)\n"
    + _AUTONOMY
    + "DONE = branch created + any carried design/plan committed + IMPLEMENTATION.md initialized "
    "(durable outputs BEFORE any kanban-move). If the branch already exists (re-entry), VERIFY and "
    "finalize — do NOT redo. Then run `kanban-done {{code}}` to end your session.\n" + _CLEAN_STOP
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
    + "PLAN-ADAPTIVE (skiff): execute whatever the per-ticket WIP branch actually carries —\n"
    "- a full plan (`docs/features/{{codename}}/plan/`) → run it phase by phase (the full lane);\n"
    "- a `docs/features/{{codename}}/SCOPE.md` only → implement the checklist directly, no phase "
    "orchestration (the lite lane);\n"
    "- neither (the express lane) → scope the fix from the ticket, implement the MINIMAL change, and "
    "write the design rationale (a few lines) into the PR body.\n"
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
    + "Do these steps IN ORDER; on ANY blocker, STOP and route to Ready to merge (below) — never "
    "force it:\n"
    "1. RESOLVE + BIND THE PR (ticket binding — never merge an unrelated PR): take this worktree's "
    "branch from `git branch --show-current` and run `gh pr list --head <branch> --state open`. If "
    "that finds no PR (the worktree may be on the WIP branch `kanban/ticket-{{code}}` rather than the "
    "PR's `feat/<codename>` head), fall back to resolving by ticket: `gh pr list --search "
    '"{{code}} in:title" --state open` (or the issue→PR link). EITHER way you MUST end with EXACTLY '
    "ONE open PR whose base is ``main`` AND whose title/linked work is ticket {{code}}; record its "
    "head branch and PR number. If zero match, more than one matches, the base is not main, or it is "
    "not ticket {{code}}'s PR — do NOT guess or merge a PR number from anywhere else: route to Ready "
    "to merge (step below) with a comment. You may ONLY ever merge ticket {{code}}'s own PR.\n"
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
    "not-ready and route to Ready to merge.\n"
    "4. CONFIRM MERGEABILITY: `gh pr view <pr> --json mergeable,mergeStateStatus` must be "
    "MERGEABLE / CLEAN.\n"
    "5. SQUASH-MERGE: `gh pr merge <pr> --squash` — this is the ONLY merge command you may run (it "
    "merges through the GitHub API). You must NEVER `git push` to ``main``, NEVER `gh api …/merge`, "
    "NEVER a GraphQL merge mutation, NEVER rebase/force-push/rewrite history.\n"
    "ON SUCCESS (the squash-merge landed): `kanban-move {{code}} Done`.\n"
    "ON ANY BLOCKER (unresolvable conflict, CI red or stuck, not mergeable, the merge command "
    'refused): do NOT retry blindly — `kanban-comment {{code}} "merge blocked: <grounded reason>"` '
    "then `kanban-move {{code}} ReadyToMerge` so a human can triage. NEVER leave a half-merged or "
    "broken state on the branch.\n"
    + _AUTONOMY
    + _GROUNDING_DISCIPLINE
    + "DONE = EITHER the PR is squash-merged AND the card moved to Done, OR the card is moved back "
    "to Ready to merge with a grounded blocker comment. If re-entered after a partial run, VERIFY the "
    "current PR/branch state FIRST and finalize — do NOT redo a merge that already landed.\n"
    "Finally, run `kanban-done {{code}}` to end your session (AFTER the kanban-move).\n"
    + _CLEAN_STOP
)
