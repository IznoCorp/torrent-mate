# genesis — Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan phase-by-phase. Each phase file contains
> numbered sub-phases with checkbox (`- [ ]`) syntax for tracking.

**Feature**: genesis — KanbanMate Extraction & Hardening (minor)
**Design**: docs/features/genesis/DESIGN.md
**Branch**: feat/genesis
**Version bump**: 0.0.0 → 0.1.0

---

## Phases

| #   | Phase                                | File                                    | Status |
| --- | ------------------------------------ | --------------------------------------- | ------ |
| 1   | Bootstrap engine + polling core      | phase-01-bootstrap-engine.md            | [ ]    |
| 2   | Installer + plugin marketplace       | phase-02-installer-plugin.md            | [ ]    |
| 3   | Hardening H3–H5                      | phase-03-hardening.md                   | [ ]    |
| 4   | Integration CI + fixtures            | phase-04-integration-ci.md              | [ ]    |
| 5   | Features + cutover                   | phase-05-features-cutover.md            | [ ]    |
| 6   | PR fixes cycle 1                     | phase-06-pr-fixes-cycle-1.md            | [ ]    |
| 7   | PR fixes cycle 1 (minors)            | phase-07-pr-fixes-cycle-1-minors.md     | [ ]    |
| 8   | PoC parity port (sticky + Cancel)    | phase-08-poc-parity-port.md             | [ ]    |
| 9   | Permission mode `auto`               | phase-09-permission-mode-auto.md        | [ ]    |
| 10  | Interpreter bump to Python 3.12      | phase-10-interpreter-3.12.md            | [ ]    |
| 11  | Install · init · run cutover         | phase-11-install-init-run-cutover.md    | [ ]    |
| 12  | Transition model + prompt routing    | phase-12-transition-model.md            | [ ]    |
| 13  | Concurrency cap + queue + rate-limit | phase-13-concurrency-ratelimit.md       | [ ]    |
| 14  | Clone + worktree provisioning        | phase-14-clone-worktree-provisioning.md | [ ]    |
| 15  | Reaper retry + audit + script gates  | phase-15-reaper-audit-gates.md          | [ ]    |
| 16  | GitHub adapter + CLI parity          | phase-16-github-cli-parity.md           | [ ]    |
| 17  | Behaviour reconciliation             | phase-17-behaviour-reconciliation.md    | [ ]    |

---

## Phase Gate Checklist (before every phase gate commit)

Per CLAUDE.md:

1. `make lint` (ruff + mypy) — zero errors
2. `make test` — all pass (ERROR = collection crash → fix imports first)
3. `make check` — lint + test + module-size guards
4. Residual-import grep for any deleted module in `src/` AND `tests/` — zero matches
5. `python -c "import kanbanmate"` smoke test

---

## Architecture Invariants (enforce in every phase)

- **Hexagonal layering** (DESIGN §3.2): `core/` → zero I/O; `ports/` → Protocols only;
  `adapters/` implement `ports/`; `app/` = composition root; import direction downward only.
- **Network safety**: every `urllib` request sets `connect_timeout` + `read_timeout` — daemon must
  never hang on I/O.
- **Search safety**: every `rg` call includes a type/glob filter (`--type py`, `-g '*.py'`, etc.).
- **Commit convention**: `<type>(genesis): <description>` — Conventional Commits, no AI attribution.
- **Module size**: soft warning ~800 LOC, hard ceiling 1000 LOC.

---

## Pre-implementation Gate (blocking — Phase 1, sub-phase 1.1)

Before ANY code is written, re-sync the latest PoC from
`/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/` (the ABSOLUTE OLD root; the engine to port
lives under `.../skills/kanban/kanbanmate/`) — both features are now shipped (sticky comments,
Cancel column, heartbeat #67). The PoC code is the source of truth for behaviours referenced
in DESIGN §8.1, §8.2, §8.3, §11.

---

## Migration phases 8–11 (PoC parity → auto mode → py3.12 → cutover)

Phases 8–11 finish the extraction: port the last PoC features that the first snapshot missed,
switch the unattended-safety knobs (permission mode + interpreter), then activate NEW and disable
OLD. Mandatory sequencing:

**8 (PoC parity port) → 9 (permission mode `auto`) → 10 (interpreter 3.12) → §11.0 OLD-disable
runbook → 11 (NEW activation) → decommission OLD source (IMPLEMENTATION.md §11, separate repo,
post-merge).**

- **Phase 8** — rich two-zone stage-comment subsystem (replaces NEW's one-line sticky writer) with
  the FULL signaling lifecycle 🟡→✅/⚠️/⛔→❌ (operator decision — all FIVE producers wired:
  launch 🟡 `in progress` · forward-advance ✅ `done` · session-end ⚠️ `interrupted` · reaper ⛔
  `blocked` · teardown ❌ `cancelled`; ENGLISH badge labels on the GitHub stickies, per NEW's
  English-only artifact rule) + full Cancel teardown parity (`--force` worktree, local `branch -D`,
  close the open PR but KEEP the remote branch, flip open stickies to ❌, recap). Sub-phases:
  8.1.a pure `core/` render/split/compose · 8.1.b adapter/app upsert via a widened GitHub port ·
  **8.1.d re-thread NEW's dropped context — WIDEN `TicketState` (launch stage + the
  `header_from_state` metadata: profile/mode/started/worktree) + add the fs-store advance breadcrumb
  (RE-KEYED from OLD's content-node-id to NEW's issue number)** · 8.1.c producers (launch 🟡 /
  reaper ⛔ — the reaper's stage comes from the widened `TicketState`; **8.1.d sequenced BEFORE
  8.1.c**) · **8.1.e daemon finalizes the LEFT
  stage ✅ on a forward advance (port of `_finalize_left_stage`; the tick PRE-READS the LEFT
  `TicketState` before `LaunchAction` overwrites the slot) + the synchronous agent breadcrumb** ·
  **8.1.f session-end finalizes ⚠️ when no advance breadcrumb exists (port of `finalize_session`,
  in `bin/kanban_session_end.py`)** · 8.2.a–d Cancel teardown. The breadcrumb is the ✅/⚠️
  discriminator, written synchronously before the agent exits and keyed by ISSUE number (OLD's
  race-closing design, re-keyed). With the widened `TicketState`, NEW's ✅/⚠️/⛔ stickies reproduce
  OLD's metadata bullets (full parity). Teardown is dispatcher-mechanical (deny-list does not apply).
  Code phase (`make check` gate per sub-phase).
- **Phase 9** — flip the pinned `defaultMode` from `acceptEdits` to **`auto`** (headless-safe; the
  PoC's unattended-hang fix). Verify `auto` lands in every worktree settings file; deny + bypass-ban
  - heartbeat hook unchanged. Code phase.
- **Phase 10** — bump `requires-python`/ruff/mypy to 3.12, re-install editable under pyenv 3.12.4,
  bump the CI workflows off 3.11, prove `make check` green under 3.12. Build/CI phase.
- **Phase 11** — `§11.A` (the one code commit, TDD, `make check` gate) adds a first-class
  `kanban install --kanban-command <abs>` flag so the install command bakes the operator-supplied
  absolute pyenv-3.12 `kanban` into the generated `ecosystem.config.js` `script:` line (generic — no
  hardcoded host path, no hand-rolled `_write_ecosystem(...)` call); then the operational runbook:
  `§11.0` disables OLD (launchd reaper, n8n, org webhook, `~/.kanban`) BEFORE NEW starts (no
  double-dispatch); then install via `--kanban-command` (so PM2 points at the absolute pyenv-3.12
  `kanban`) / init a FRESH Project v2 / paste the PAT / re-seed / `kanban run` under PM2 / verify
  (doctor, real card-move launch, no-hang under `auto`, in-daemon reaper). The PAT is the one
  carry-over; the board is fresh. Decommission of OLD source is referenced (IMPLEMENTATION.md §11),
  not duplicated.
