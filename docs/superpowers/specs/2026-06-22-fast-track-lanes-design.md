# Fast-track lanes — triage-routed lifecycle for small/safe tickets

**Date:** 2026-06-22
**Status:** Design (brainstorm output, pending plan)
**Suggested codename:** `skiff` (small, fast, light craft — the express/lite lanes) — confirm at `/implement:feature`
**Related work:** `fix/reflex` (`2672bfe`) — collapses _inter-stage_ auto-advance latency (~120 s → seconds). This spec is orthogonal: it removes the _work_ a small ticket does per stage, not the dead time between stages. Both are needed.

---

## 1. Problem

Every ticket — a one-line typo fix and a new subsystem alike — traverses the identical HYBRID
lifecycle: `Backlog → Brainstorming → Spec → Plan → ReadyToDev (human gate) → PrepareFeature →
InProgress → PRCI → Review → Merge → Done`. Three heavy autonomous LLM stages (interactive-style
brainstorm, full `DESIGN.md`, multi-phase plan) plus a human gate run _before a single line of code_,
and review applies up to 5 fix cycles + the full pr-review-toolkit + per-finding filtering against
`DESIGN.md` regardless of ticket size.

The operator has a backlog of small, obvious fixes. For these the brainstorm should ask (almost) no
questions, obvious non-consequential decisions should be made by the agent, and the design/spec/plan
effort should be minimal — sometimes skipped entirely. Review should be lighter for a small bug. None
of this should degrade the path for complex **or sensitive** tickets.

### Root cause (from the codebase map)

The engine has **no notion of ticket size or risk**. The only "size" signal is the SemVer bump
(bugfix/minor/major), which is derived _during_ brainstorm (too late) and never re-read by the engine
to alter the flow. `wave:`/`prio:` labels exist but the daemon ignores them. The transitions-only
model launches at whitelisted `(from_col, to_col)` edges with **no conditional logic** in `decide()`;
profiles and prompts are per-transition, fixed, never per-ticket. So fast-tracking _requires_
introducing a signal the engine reads early — there is no existing knob to flip.

## 2. Goals / Non-goals

**Goals**

- Route small **and** safe tickets through a shorter path that skips or compresses the design stages
  and the pre-build human gate.
- Make fast-lane agents autonomous: no user questions; decide obvious, non-consequential matters per
  repo conventions.
- Scale review strictness to the lane.
- Keep the full lane and all safety invariants (`merge = human`, banned `gh pr merge`/force-push,
  non-root, kill-switch) **exactly** as they are.

**Non-goals**

- No auto-merge. Every lane stops at the human `Review → Merge` gate (the master safety backstop).
- No conditional logic inside `core/decide.py`. Routing is by **topology**, not by `if`.
- No change to the full lane's behaviour.
- Not solving inter-stage daemon latency — that is `reflex`.

## 3. Decisions (brainstorm, 2026-06-22)

| #   | Decision                                          | Choice                                                                                                           |
| --- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| 1   | Who classifies the lane                           | **Auto-triage agent + operator override** (explicit label always wins)                                           |
| 2   | How many lanes / what they skip                   | **3 lanes: full / lite / express**                                                                               |
| 3   | Human gates on fast lanes                         | **Merge stays human on all 3 lanes**; fast lanes drop only the pre-build `ReadyToDev` gate + design stages       |
| 4   | Classification signals                            | **Operator sensitive-paths config + labels (hard guard) + agent read of ticket & code (size)**; any doubt → full |
| 5   | Triage placement                                  | **Visible `Triage` column** every ticket transits                                                                |
| 6   | Autonomy on ambiguous-but-non-sensitive decisions | **Decide, post the question + decision as a ticket comment (async), continue** — never block                     |

## 4. Design principle

A **lane** is decided **once, early**, by a cheap triage agent. Because the transitions-only model
forbids conditional routing in the engine, we route **by topology**: the triage result makes the
engine _advance_ the card to the chosen lane's entry column, and the existing flow handles the rest
with zero `if` in `decide()`.

Two combined levers:

- **Topology** → _skip_ stages (express) or _compress_ them (lite).
- **Adaptive prompts** → _autonomy_: fast-lane prompts forbid questions and require deciding obvious
  matters per repo conventions, logging ambiguous calls as ticket comments.

**Master safety backstop:** all 3 lanes stop at the human `Review → Merge` gate. A mis-classified
express ticket is recoverable — worst case its design is too thin and the human catches it at merge.
This bounded blast radius is what makes aggressive fast-tracking acceptable.

## 5. Board topology (2 new columns: `Triage`, `Scope`)

```
                       ┌─► Brainstorming → Spec → Plan → ReadyToDev ─┐  (human gate #1, full only)
                       │     (full: current flow, unchanged)         │
Backlog → Triage ──────┼─► Scope ─────────────────────────────────────┤
        (classify +    │     (lite: 1 stage, mini-design+plan,       │
      routed-advance)  │      no questions, no gate)                  ▼
                       └─► ──────────────────────────────────► PrepareFeature
            (express: no design, straight to build)                  │  create-branch (adaptive)
                                                                     ▼
                                        InProgress (build, plan-adaptive prompt)
                                                                     ▼
                                        PRCI (CI gate) ─► Review (track-aware)
                                                                     ▼
                                            [human drag] ─► Merge → Done
```

- `ReadyToDev` (pre-build gate) exists **only on full**. Fast lanes bypass it by topology, not by a
  condition.
- `PrepareFeature → InProgress → PRCI → Review → Merge` is the **shared tail** for all 3 lanes. Lane
  adaptivity lives in the tail's prompts.
- `Triage` and `Scope` are `INERT` columns (no `action:teardown`); all launch config lives on their
  edges, per the transitions-only model.

## 6. Triage stage

`Backlog → Triage` launches a **lightweight** agent (cheap model; new read-only `triage` profile with
the route helper allowed). Algorithm:

1. **Override first.** Label `track:full|lite|express` → honour verbatim. Label `sensitive` (or any
   `area:*` listed as sensitive in config) → **full**, unconditionally.
2. **Sensitivity (hard guard).** Read `.claude/kanban/sensitive.yml` (versioned). If the ticket's
   probable scope intersects a sensitive path glob or keyword → **full**.
3. **Size.** Read the ticket body + take a **quick code peek** (grep/read the likely files) to
   estimate trivial / small / substantial.
4. **Conservative decision.** `express` = trivial **and** safe; `lite` = small **and** safe; otherwise
   **full**. **Any doubt → full.**
5. Write `**track**: <lane>` into the ticket body via the existing `--set-field` body-marker mechanism
   (`core/body_edit.py`), call the new `kanban-route <lane>` helper, then `kanban-done`.

### `sensitive.yml` (new, versioned, lives beside `transitions.yml`/`columns.yml`)

```yaml
# .claude/kanban/sensitive.yml — any match forces the full lane.
paths: # globs, matched against the ticket's probable scope
  - "**/auth/**"
  - "**/billing/**"
  - "src/kanbanmate/core/decide.py"
  - "src/kanbanmate/core/intent.py"
  - "src/kanbanmate/adapters/perms.py"
  - "src/kanbanmate/bin/kanban_session_end.py" # the merge/advance path
keywords: # case-insensitive substrings in the ticket text
  - security
  - credential
  - secret
  - migration
  - permission
labels: # GitHub labels that force full regardless of size
  - sensitive
  - security
```

Conservative-by-construction: an empty/missing `sensitive.yml` is **not** "nothing is sensitive" — the
triage prompt treats a missing config as a reason to lean toward full for anything non-obvious.

## 7. The one real engine change: routed-advance

**Constraint:** `core/intent.py` forbids an agent from moving a card into a prompt-bearing transition
(anti-loop / authority — `R1` own-ticket rule). All three lane entries are prompt-bearing, so the
triage agent **cannot** route the card itself. The **engine** must — exactly as the session-end
backstop already moves cards into launch edges (recording a `pending_launch` breadcrumb).

**Mechanism (surgical extension of the existing backstop):**

- The `Backlog → Triage` transition carries a new advance directive **`advance: route`**.
- A new helper **`kanban-route <lane>`** (sibling of `kanban-done` / `kanban-advance`) writes a
  **ROUTE breadcrumb** recording the chosen lane.
- `bin/kanban_session_end.py::_auto_advance` gains a branch: on directive `route`, read the ROUTE
  breadcrumb, resolve `lane → entry column` via a declarative config map, **validate that
  `Triage → <entry>` is a whitelisted transition** (reuses the transitions whitelist as the guard —
  the engine only ever moves along a real, prompt-bearing edge it would have launched anyway), then
  `client.move_card` + `record_move_for_item`, reusing the existing rate-limit, idempotency,
  `pending_launch`-breadcrumb, and (post-reflex) daemon-nudge machinery verbatim.
- `bin/_clone_config.py::auto_advance_target` is extended to recognise `route` (returns a sentinel so
  the caller reads the breadcrumb) alongside the existing `auto:<col>` parsing.

**Lane→entry map** (declarative, in `transitions_defaults.py`; not hardcoded in pure core):

```yaml
track_entry:
  full: Brainstorming
  lite: Scope
  express: PrepareFeature
```

**Rejected alternative:** a `track:` label + conditional transition resolution in `transitions.py`.
Rejected — it injects conditional logic into the transitions-only core (an explicit DESIGN
anti-pattern) and makes the lane invisible on the board. Routed-advance keeps "card moves = the
trigger" and renders the lane visible (you watch the card pass through `Triage`).

## 8. Lane heads

- **full** — unchanged. `Triage → Brainstorming → Spec → Plan → ReadyToDev` (human gate) → drag →
  `PrepareFeature`.
- **lite** — `Triage → Scope`. ONE agent produces a **mini-design + mini-plan** (a few lines each,
  committed to the WIP branch `kanban/ticket-<n>`), **decides every obvious matter itself**, asks **no**
  questions, derives codename + bump (usually patch/minor), then `advance: auto:PrepareFeature`. No
  gate.
- **express** — `Triage → PrepareFeature` directly. **No design file**; the rationale is a few lines in
  the **PR body**. codename = slug of the issue title, bump = patch by default.

## 9. Shared tail + adaptive prompts

Because all lanes merge into one tail, the tail prompts **self-adapt to the artifacts carried on the
WIP branch** (the hybrid-flow cross-stage carry is the channel):

- **create-branch** (edges _into_ `PrepareFeature`): codename/bump already decided (full/lite) → reuse;
  otherwise (express) → derive trivially (slug + patch).
- **build** (`PrepareFeature → InProgress`): _full plan present_ → execute phase by phase (full);
  _mini-plan present_ → implement directly (lite); _neither_ → scope the fix from the ticket, then
  implement (express). One prompt, three behaviours driven by what is on the branch.

## 10. Track-aware review

`PRCI → Review` (`/implement:pr-review`) reads `**track**` from the ticket body and scales itself:

| Lane    | Max cycles | Norms agents                                                            | Filter against                              | Merge |
| ------- | ---------- | ----------------------------------------------------------------------- | ------------------------------------------- | ----- |
| full    | 5          | all 8                                                                   | `DESIGN.md`                                 | human |
| lite    | 2          | subset (correctness / security / test-coverage)                         | mini-scope note                             | human |
| express | 1          | correctness + security only (`code-reviewer` + `silent-failure-hunter`) | ticket acceptance criteria (no `DESIGN.md`) | human |

A finding that contradicts the design still escalates immediately on **full**; on lite/express there
is no `DESIGN.md` to contradict, so the filter is against the scope note / ticket acceptance.

## 11. Autonomy & decision logging

On lite/express, when a decision is ambiguous but **non-sensitive**, the agent: (a) decides per repo
conventions, (b) posts a ticket comment recording the question + the decision taken + the alternative,
(c) continues without waiting. Sensitive ambiguity never reaches a fast lane (triage routed it to
full). This gives an async audit trail on the ticket and zero blocking pauses.

## 12. Safety properties / invariants (must hold)

- **Merge = human** on all 3 lanes. `gh pr merge`, force-push, history-rewrite stay banned in every
  profile. The new `triage` profile is read-only + route, never merge.
- **Conservative routing.** Sensitivity is a hard, config-driven veto; any uncertainty → full. The
  fast lanes are opt-in by _evidence of smallness AND safety_, not opt-out.
- **No conditional core.** `decide()` is untouched; routing is a topological move via the backstop.
- **Engine only moves along whitelisted edges.** `kanban-route` validation rejects any target that is
  not a real `Triage → X` transition.
- **Bounded blast radius.** The human merge gate is the final catch for any mis-classification.
- **Rate-limit + anti-loop** apply to the routed-advance move identically to existing auto-advances.

## 13. Scope of changes

**Config only**

- `columns.yml`: `+Triage`, `+Scope`.
- `transitions_defaults.py` / `transitions.yml`: replace `Backlog → Brainstorming` with
  `Backlog → Triage` (`advance: route`); add `Triage → Brainstorming`, `Triage → Scope`,
  `Triage → PrepareFeature`, `Scope → PrepareFeature`; add `track_entry` map.
- New `sensitive.yml`.

**Engine (code)**

- `advance: route` directive + ROUTE breadcrumb + `kanban-route` helper.
- `kanban_session_end._auto_advance` route branch; `_clone_config.auto_advance_target` extension.
- New `triage` profile in `adapters/perms.py` (read + grep + `--set-field` + `kanban-route`; no write
  to source, no push, no merge).

**Prompts (skills / transition prompt text)**

- Triage prompt (classify size+sensitivity; honour override; write `**track**`; `kanban-route`).
- Scope prompt (lite: mini-design + mini-plan, no questions, derive codename/bump).
- create-branch prompt: adaptive (reuse vs derive).
- build prompt (`PrepareFeature → InProgress`): plan-adaptive (full plan / mini-plan / none).
- pr-review prompt: track-aware leniency table above.
- Fast-lane prompts encode the autonomy + comment-and-continue policy.

**Unchanged**

- The entire full lane, `merge = human`, the bans, existing profiles, the WIP-branch carry, the
  rate-limiting, `reflex`'s nudge/fast-poll behaviour (the route move reuses it).

## 14. Edge cases & failure modes

- **Malformed/empty ROUTE breadcrumb** → fail-soft: no move, card stays in `Triage`, daemon re-fires
  triage next tick (idempotent — triage re-reads, re-decides). Mirror the existing
  `auto_advance_target` "malformed → None → stop" behaviour.
- **Route target not whitelisted** → fail-soft warning to stderr, no move (same as backstop "unknown
  target").
- **Override label + sensitive conflict** (e.g. `track:express` on a card touching a sensitive path):
  **sensitivity wins → full.** A `sensitive` label cannot be over-ridden down by `track:express`. The
  triage prompt documents this precedence and posts a comment when it overrides an explicit
  `track:express` down to full.
- **express with no derivable codename** (empty/garbage title) → fail-soft to a deterministic slug
  (`ticket-<n>`), bump patch.
- **Rate-limit hit on the route move** → card parked in `Blocked` with a comment, exactly as the
  existing backstop rate-limit path.
- **Re-entry into `Triage`** (card dragged back) → triage re-runs, re-routes; idempotent.

## 15. Testing strategy

- **Pure parser:** `auto_advance_target("route")` sentinel; lane→entry resolution; precedence
  (sensitive beats `track:express`).
- **Backstop:** ROUTE breadcrumb present + `route` directive → move to resolved entry once +
  `record_move_for_item`; malformed → no move; non-whitelisted target → fail-soft; rate-limit → park.
- **Triage classification:** table-driven cases (trivial+safe→express, small+safe→lite,
  sensitive-path→full, override label honoured, override-down-on-sensitive).
- **Topology:** `Triage` edges round-trip through `load_transitions`; human gates still carry no
  auto-advance; `track_entry` columns all exist in `columns.yml`.
- **Review track scaling:** prompt selects the right cycle cap / norms subset / filter target per
  `**track**` value.
- **Profile:** `triage` profile denies merge/push/source-write; allows route + read + set-field.

## 16. Open questions / future

- Should a _substantial-but-safe_ ticket ever get a partial fast-track (e.g. full design but a
  2-cycle review)? Out of scope now — keep the binary safe/sensitive × size matrix simple.
- Telemetry: record per-lane wall-clock + mis-classification rate (lite/express tickets the human
  bounced at merge) to tune `sensitive.yml` and the triage prompt over time.
- Self-hosting: this feature is itself a candidate ticket on the kanban-mate board (recursive
  dogfooding) once shipped.
