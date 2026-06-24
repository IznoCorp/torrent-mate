# Fast-track lanes (skiff)

Not every ticket deserves the full brainstorm → design → plan → human-review ceremony. A one-line
config flag and a six-file mechanical refactor should not cost the same as a new cross-instance
locking protocol. The **skiff** fast-track system gives KanbanMate **three lanes** of decreasing
ceremony, and a cheap **Triage** classifier that picks the right one per ticket.

Every ticket now enters the board at **Backlog**, gets dragged (or auto-routed) into **Triage**, and
from there the engine routes it onto one of:

| Lane        | Entry column      | Design effort                                  | Pre-build human gate   | Use for                                           |
| ----------- | ----------------- | ---------------------------------------------- | ---------------------- | ------------------------------------------------- |
| **FULL**    | `Brainstorming`   | brainstorm + DESIGN.md + multi-phase plan      | **yes** (Ready to dev) | novel design, unknowns, irreversible/risky work   |
| **LITE**    | `Scope`           | one-pass `SCOPE.md` (design + plan compressed) | no                     | bounded, mechanical, multi-file changes           |
| **EXPRESS** | `Prepare feature` | none — rationale goes in the PR body           | no                     | trivial single edits (one line / flag / constant) |

**Merge is human-only in ALL THREE lanes.** The fast lanes shave off _design_ ceremony, never the
merge gate. A reviewed card always rests at **Ready to merge** until an operator drags it onward.

> Source of truth: `core/transitions_defaults.py` (the `DEFAULT_TRANSITIONS` table + `TRACK_ENTRY`),
> `core/transitions_prompts.py` (the stage prompts incl. `_TRIAGE_PROMPT`), the live
> `.claude/kanban/{transitions,columns,sensitive}.yml`, and `bin/kanban_session_end._routed_advance`
> (the engine routing backstop).

## The lane map

```
                                  ┌─────────┐
   you create a ticket  ─────────▶│ Backlog │   (manual entry point)
                                  └────┬────┘
                                       │  drag → Triage  (or auto)
                                       ▼
                                  ┌─────────┐
                                  │ Triage  │   CLASSIFIER agent (cheap, read-only)
                                  └────┬────┘   inspects SIZE × SENSITIVITY, records the lane,
                                       │         then the ENGINE routes to the lane entry column
            ┌──────────────────────────┼──────────────────────────────┐
            │ full                      │ lite                          │ express
            ▼                           ▼                               ▼
     ┌──────────────┐            ┌──────────────┐                      │
     │ Brainstorming│  (1 human  │    Scope     │  design+plan in      │
     │  (interactive│   Q&A pause)│  (one pass)  │  ONE pass, autonomous│
     └──────┬───────┘            └──────┬───────┘                      │
            │ auto:Spec                 │ auto:PrepareFeature           │
            ▼                           │                               │
     ┌──────────────┐                   │                               │
     │     Spec     │  (autonomous      │                               │
     │  (DESIGN.md) │   design)         │                               │
     └──────┬───────┘                   │                               │
            │ auto:Plan                 │                               │
            ▼                           │                               │
     ┌──────────────┐                   │                               │
     │     Plan     │  (autonomous      │                               │
     │ (plan files) │   plan)           │                               │
     └──────┬───────┘                   │                               │
            │ auto:ReadyToDev           │                               │
            ▼                           │                               │
     ┌──────────────┐                   │                               │
     │ Ready to dev │ ◀═══ HUMAN GATE   │                               │
     │ (review the  │   (FULL lane ONLY)│                               │
     │  design+plan)│                   │                               │
     └──────┬───────┘                   │                               │
            │ HUMAN drags →             │                               │
            ▼                           ▼                               ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │                      Prepare feature                                 │  create-branch
     │   (create branch · commit carried design/plan · init IMPLEMENTATION) │  (plan-adaptive)
     └───────────────────────────────┬────────────────────────────────────┘
                                      │ auto:InProgress
                                      ▼
                              ┌──────────────┐
                              │ In Progress  │  /implement:phase — implement + open PR,
                              │              │  STOP at PR creation (never merge)
                              └──────┬───────┘
                                     │ auto:PRCI
                                     ▼
                              ┌──────────────┐   bin/check-pr-ready.sh
                              │    PR/CI     │ ◀═ CI GATE (script):
                              └──────┬───────┘    green → auto:Review · red → bounce to In Progress
                                     │ auto:Review (green only)
                                     ▼
                              ┌──────────────┐
                              │    Review     │  /implement:pr-review — review rounds + fixes,
                              │               │  cycles scale by lane (full 5 / lite 2 / express 1)
                              └──────┬────────┘
                                     │ auto:ReadyToMerge
                                     ▼
                              ┌────────────────┐
                              │ Ready to merge │ ◀═══ HUMAN MERGE GATE  (ALL lanes)
                              └──────┬─────────┘
                                     │ HUMAN drags →
                                     ▼
                              ┌──────────────┐   bin/check-pr-ready.sh gate, then the
                              │    Merge     │   autonomous merge agent (merge profile):
                              └──────┬───────┘   bring up to date · wait CI green · squash-merge
                                     │ success → Done · blocker → back to Ready to merge
                                     ▼
                              ┌──────────────┐
                              │     Done     │
                              └──────────────┘
```

Notice the three lanes **converge at `Prepare feature`** — once a branch is created the build/CI/review/merge
tail is identical for every lane. The lanes differ only in the _front half_ (how the ticket reached
a branch) and in the **review strictness** that scales down on the faster lanes.

Two columns sit outside the forward flow: **Blocked** (any column ↔ Blocked — the daemon/agent parks
a stalled ticket here) and **Cancel** (any column → Cancel triggers a full teardown of the worktree
and runtime state; `Cancel → Backlog` is the resume reset).

## Where the gates are

There are exactly **two human gates** on the longest (full) path, and only one on the fast lanes:

| Gate          | Column           | Which lanes   | What you do                                                                                            |
| ------------- | ---------------- | ------------- | ------------------------------------------------------------------------------------------------------ |
| **Pre-build** | `Ready to dev`   | **FULL only** | review the auto-generated DESIGN + plan, then drag `Ready to dev → Prepare feature` to start the build |
| **Merge**     | `Ready to merge` | **ALL lanes** | review the open PR, then drag `Ready to merge → Merge` to fire the autonomous merge agent              |

The **CI gate** (`In Progress → PR/CI`) is a _script_ gate, not a human one: `bin/check-pr-ready.sh`
runs on the transition and auto-promotes the card to `Review` only when CI is green (`advance:auto:Review`);
a red gate bounces the card back to `In Progress` (`on_fail: move:InProgress`) where the fix-CI loop runs.

`Plan → Ready to dev` deliberately carries **no** `advance` directive — that no-op is what _makes_
`Ready to dev` a resting gate. Auto-advancing it would bypass the single pre-build human review, the
core property of the full lane.

### `advance:auto:<col>` vs a resting transition

Each transition row in `transitions.yml` may carry an `advance` directive. This is what turns the
front of the flow autonomous:

- **`advance: auto:<col>`** — when the stage's agent finishes cleanly (runs `kanban-done` and does
  _not_ move its own card), the engine's session-end backstop (`bin/kanban_session_end._auto_advance`)
  moves the card to `<col>`. The next poll tick diffs the move and fires the next stage. This is how
  brainstorm → Spec → Plan, and Prepare feature → In Progress, chain themselves.
- **`advance: route`** — only on `Backlog → Triage`. The backstop reads the lane breadcrumb the
  triage agent left and moves the card to the lane's entry column (`_routed_advance`).
- **`advance: stop`** — the agent routes itself (e.g. the merge agent: success → Done, blocker →
  Ready to merge). No engine auto-advance.
- **no `advance` key (a no-op edge)** — a _resting_ transition. The card lands and stays put for a
  human, e.g. `Plan → Ready to dev` and `Review → Ready to merge`.

## The Triage classifier

`Backlog → Triage` launches a cheap, read-only classifier agent under the `triage` permission profile.
It writes no code and opens no PR — it only inspects the ticket and records a lane. It is the cheapest
place in the whole flow to decide how much effort a ticket warrants.

### What it inspects: two axes

Triage classifies on **SIZE × SENSITIVITY**.

**SIZE** is explicitly _not_ files-touched, layers-crossed, or lines-changed. In a hexagonal codebase
every visible value crosses GraphQL → parser → domain → endpoint → component by construction, so
file-count would make the fast lanes dead on arrival. SIZE measures **novel design decisions /
unknowns / irreversible choices**. The classifier asks three sizing questions and the answer-count is
the size:

- **Q1 — NOVEL DECISION**: does the ticket force a genuine _open_ design question someone must answer
  (a new schema / algorithm / protocol / API shape / data flow, or a real trade-off) — versus
  mechanically _applying_ a change whose shape, data source, and contract are already determined?
- **Q2 — UNKNOWN**: is there a real unknown to investigate before you can even say what the change is
  (where a value comes from, whether the approach works, what it touches)?
- **Q3 — IRREVERSIBLE / RISKY**: does it make a hard-to-reverse or high-regression-risk choice (data
  migration, irreversible state change, public-contract break, concurrency/ownership protocol)? A
  small edit to a **concurrency / rate-limit / idempotency / persistence / HMAC-signature / board-write**
  surface is YES _regardless of edit size_ — the "breadth is not effort" rule never deflates a
  risk-bearing module.

The self-test: _"How many questions must I answer before I know exactly what to write?"_ Zero →
trivial/small; one or more genuine ones → substantial. A long but already-answered checklist (several
sub-requirements ≠ several novel decisions) is still small.

**SENSITIVITY** is read from `.claude/kanban/sensitive.yml` — see below. A hit forces FULL no matter
how small the change.

### The decision tree (stops at the first match)

The classifier runs this tree top-down — the safety checks come first, so a manual override can never
pull a sensitive or substantial ticket _down_ to a faster lane:

1. **SENSITIVE?** A `sensitive.yml` path/keyword match, a `sensitive`/listed sensitive label, OR
   multiple/conflicting `track:*` labels (ambiguous) → **full**. Checked first; never overridden down.
2. **CANNOT ASSESS?** The ticket is too vague to scope, or the `rg`/`grep` peek reveals hidden
   fan-out / an unresolvable unknown → **full** (the conservative default for a _real_ inability to
   assess — not for a change you understand that merely spans many files).
3. **SUBSTANTIAL?** YES to any sizing question (Q1/Q2/Q3, including any edit to a risk-bearing
   surface) → **full**.
4. **EXPLICIT OVERRIDE?** Exactly one `track:full|lite|express` label present AND none of steps 1–3
   forced full → honour it (with a comment noting the override). A `track:*` label can only route a
   non-sensitive, non-substantial ticket — it can **never** pull a step-1/2/3 `full` down.
5. **SMALL?** NO to all three sizing questions but a non-trivial mechanical surface (a UI/JSX edit,
   several files, one obvious choice) → **lite**. A purely mechanical change is lite no matter how
   many files it touches.
6. **TRIVIAL?** NO to all three sizing questions AND a single tiny edit (one line / one config flag /
   one constant) needing no design+plan artifact → **express**.

Summary: `express` = trivial AND safe; `lite` = small AND safe; `full` = substantial OR sensitive OR
un-assessable. A tie between trivial and small breaks **down** to the cheaper lane. _"Any doubt →
full"_ applies only to **design** doubt (a live Q1/Q2/Q3 maybe-yes, a sensitivity hit, an inability
to assess) — breadth, file count, and layers crossed are never "doubt" and never break a ticket up.

### What it records (and how the engine routes)

The classifier records its decision in this order, then ends:

1. `kanban-update-body {{code}} --set-field track <lane>` — the durable `**track**` field (read later
   by the lane-aware PR review).
2. `kanban-route {{code}} <lane>` — the routing breadcrumb the engine consumes.
3. `kanban-done {{code}}` — ends the session.

It does **not** move the card itself. The `Backlog → Triage` transition carries `advance: route`, so
the engine's session-end backstop (`_routed_advance`) reads the breadcrumb, resolves the lane → entry
column via `TRACK_ENTRY`, validates that `Triage → entry` is a real whitelisted launch edge (the
routing safety guard), and moves the card there. The lane → entry map (`core/transitions_defaults.py`):

```python
TRACK_ENTRY = {
    "full":    "Brainstorming",
    "lite":    "Scope",
    "express": "PrepareFeature",
}
```

An unknown or empty lane resolves to `None` → no move; the card stays in `Triage` for an operator
re-drag rather than the engine guessing a target.

## What each lane does

### FULL — `Brainstorming → Spec → Plan → [Ready to dev] → Prepare feature → …`

The original ceremony, unchanged. An **interactive brainstorm** (the one place a human `tmux attach`es
to answer clarifying questions) appends decisions under a `## Brainstorm` heading and sets the
codename; the autonomous **Spec** stage writes `docs/features/<codename>/DESIGN.md`; the autonomous
**Plan** stage writes the phase plan; the card then rests at **Ready to dev** for the human review
gate. Reserved for genuine open design questions, unknowns, and irreversible/risky work.

### LITE — `Scope → Prepare feature → …`

The **Scope** stage (launched on `Triage → Scope`, `docs` profile) produces a **compressed design +
plan in a single pass** — no separate brainstorm, no full DESIGN.md, no multi-phase plan. It first
derives and sets the codename (triage does not set it), then writes a few-line scope note plus a short
checklist plan to `docs/features/<codename>/SCOPE.md`, commits it to the per-ticket WIP branch (so the
build stage inherits it), and ends. The engine auto-advances to **Prepare feature** — **there is no
pre-build human gate**; lite goes straight to build.

Scope is autonomous: it is _here_ precisely because triage found no open question. It must not
re-litigate the size. But it has a built-in **self-escalation** safety valve — if it discovers a
genuine novel decision or a hidden unknown mid-scope, that is a mis-route: it posts a comment and runs
`kanban-route {{code}} full` rather than guessing, kicking the ticket up to the full lane.

### EXPRESS — `Prepare feature → …`

Straight to build. `Triage → Prepare feature` (`prepare` profile) runs the same plan-adaptive
create-branch stage the other lanes reach, but with **no DESIGN.md and no plan** — the create-branch
agent derives the codename from the issue title (slug), uses a `patch` bump, and the design rationale
lives in the PR body. An empty design/plan marker is _expected_ for this lane, not a desync. Reserved
for trivial single edits.

The build stages downstream are all **plan-adaptive**: `/implement:phase` runs the full plan phase by
phase if one exists, implements the `SCOPE.md` checklist directly if only that exists, or scopes the
minimal fix from the ticket if neither exists.

## The `track:*` manual override

You can override triage's automatic decision by stamping a single GitHub label on the issue:

| Label           | Forces lane |
| --------------- | ----------- |
| `track:full`    | FULL        |
| `track:lite`    | LITE        |
| `track:express` | EXPRESS     |

The override is honoured **only at step 4 of the decision tree** — after the sensitivity, can't-assess,
and substantial checks have run. So `track:lite` on a ticket that touches `core/decide.py` (a
`sensitive.yml` path) still goes FULL: the safety checks run first and a down-override cannot bypass
them. Multiple/conflicting `track:*` labels are treated as ambiguous → FULL.

### Setting it from KanbanMateUI

In the **Monitoring** tab, each ticket has a **Voie** (lane) selector alongside its Status: **Auto** /
**Full** / **Lite** / **Express**. Auto clears the override (lets triage decide). Picking a lane POSTs
to `POST /api/monitor/ticket/{number}/track` (`{"track": "full"|"lite"|"express"|null}`), which calls
`set_issue_track_label` to stamp the label idempotently. The board view overlays which cards carry a
manual lane via `GET /api/monitor/board/tracks`.

### Setting it from the CLI / gh

There is no dedicated CLI verb — stamp the label directly on the issue:

```bash
gh issue edit <number> --repo <owner/repo> --add-label track:lite
# clear it (let triage decide again):
gh issue edit <number> --repo <owner/repo> --remove-label track:lite
```

(Setting it via the UI also clears any _other_ `track:*` label, so only one lane is ever stamped at a
time; doing it by hand, remove the stale one yourself.)

## Review strictness scales by lane

The faster lanes also relax the _review_ round, not just the design round. `/implement:pr-review`
reads the ticket's `**track**` field and scales three things:

| Track     | Max review-fix cycles | Filter artifact                                 | Norms agents                              |
| --------- | --------------------- | ----------------------------------------------- | ----------------------------------------- |
| `full`    | 5                     | `docs/features/<codename>/DESIGN.md`            | all 8                                     |
| `lite`    | 2                     | `docs/features/<codename>/SCOPE.md`             | correctness / security / test-coverage    |
| `express` | 1                     | the ticket's acceptance criteria (no DESIGN.md) | `code-reviewer` + `silent-failure-hunter` |

A missing or unreadable track resolves to `full` — a faster lane is never assumed. Merge stays
human-only on every lane.

## Gotcha: re-import the board after a column change

The lane columns (`Triage`, `Scope`, plus the standard flow columns) must exist on the GitHub board
_and_ in the native `board.json` mirror. The native one-way board keeps a local `board.json` whose
column set does **not** update through a GitHub sync. After adding or renaming a board column, run:

```bash
kanban board import --root ~/.kanban-km --project <owner/repo>
```

to re-sync `board.json` from GitHub. Native placement cannot reconcile a column it does not know about,
so the engine cannot route a card into a column missing from `board.json` (e.g. the route into the
lane entry would be refused by the routing safety guard).

## Customising the lanes

The lane columns, transitions, and entry mapping are all configurable, but they are _coupled_ — change
one, change the others:

- **`columns.yml`** — the column SET. The skiff heads `Triage` and `Scope` are inert columns here;
  the launches live on the transitions.
- **`transitions.yml`** — the `(from, to)` whitelist carrying each stage's prompt, profile,
  `advance`, `script`, and `on_fail`. The `Backlog → Triage` (route), `Triage → {Brainstorming,
Scope, PrepareFeature}` (the three lane heads), and `Scope → PrepareFeature` rows define the lane
  topology. Regenerate the shipped defaults with `render_transitions_yaml` in
  `core/transitions_defaults.py`.
- **`sensitive.yml`** — the paths / keywords / labels that force the FULL lane at triage. A
  missing/empty file is **not** "nothing is sensitive" — triage leans to `full` for anything it cannot
  confidently classify as safe.
- **`TRACK_ENTRY`** (`core/transitions_defaults.py`) — the lane → entry-column map. A board that
  renames `Brainstorming` / `Scope` / `PrepareFeature` must update this map too, or routing breaks.

See also: `docs/columns.md` (the `columns.yml` reference) and `docs/how-it-works.md` (the poll loop +
the autonomous lifecycle).
