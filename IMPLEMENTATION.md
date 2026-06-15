# Implementation Progress — genesis

> For Claude: read this file at session start. Current feature tracker.

**Feature**: genesis — KanbanMate Extraction & Hardening (minor)
**Version bump**: 0.0.0 → 0.1.0
**Branch**: feat/genesis
**PR merge**: manual
**PR**: https://github.com/IznoCorp/kanban-mate/pull/1
**Design**: docs/features/genesis/DESIGN.md
**Master plan**: docs/features/genesis/plan/INDEX.md

## Phases

| #   | Phase                                  | File                                        | Status |
| --- | -------------------------------------- | ------------------------------------------- | ------ |
| 1   | Bootstrap engine + polling core        | phase-01-bootstrap-engine.md                | [x]    |
| 2   | Installer + plugin marketplace         | phase-02-installer-plugin.md                | [x]    |
| 3   | Hardening H3–H5                        | phase-03-hardening.md                       | [x]    |
| 4   | Integration CI + fixtures              | phase-04-integration-ci.md                  | [x]    |
| 5   | Features + cutover                     | phase-05-features-cutover.md                | [x]    |
| 6   | PR fixes cycle 1                       | phase-06-pr-fixes-cycle-1.md                | [x]    |
| 7   | PR fixes cycle 1 (minors)              | phase-07-pr-fixes-cycle-1-minors.md         | [x]    |
| 8   | PoC parity port (sticky+Cancel)        | phase-08-poc-parity-port.md                 | [x]    |
| 9   | Permission mode `auto`                 | phase-09-permission-mode-auto.md            | [x]    |
| 10  | Interpreter bump to Python 3.12        | phase-10-interpreter-3.12.md                | [x]    |
| 11  | Install · init · run cutover           | phase-11-install-init-run-cutover.md        | [x]    |
| 12  | Transition model + prompt routing      | phase-12-transition-model.md                | [x]    |
| 13  | Concurrency cap + queue + rate-limit   | phase-13-concurrency-ratelimit.md           | [x]    |
| 14  | Clone + worktree provisioning          | phase-14-clone-worktree-provisioning.md     | [x]    |
| 15  | Reaper retry + audit + script gates    | phase-15-reaper-audit-gates.md              | [x]    |
| 16  | GitHub adapter + CLI parity            | phase-16-github-cli-parity.md               | [x]    |
| 17  | Behaviour reconciliation               | phase-17-behaviour-reconciliation.md        | [x]    |
| 18  | PR-review fixes (cycle 2)              | phase-18-pr-fixes-cycle-2.md                | [x]    |
| 19  | PR-review fixes (cycle 3)              | phase-19-pr-fixes-cycle-3.md                | [x]    |
| 20  | Transitions-only engine                | phase-20-transitions-only-engine.md         | [x]    |
| 21  | Live board migration                   | phase-21-board-migration.md                 | [x]    |
| 22  | Perms profile regression fix           | phase-22-perms-profile-fix.md               | [x]    |
| 23  | Fixed poll interval (no backoff)       | phase-23-fixed-poll-interval.md             | [x]    |
| 24  | Project status updates (dashboard)     | phase-24-project-status-updates.md          | [x]    |
| 25  | Launch/relaunch/teardown fixes (e2e)   | phase-25-launch-relaunch-teardown-fixes.md  | [x]    |
| 26  | Brainstorming split + skip-to-Done     | phase-26-brainstorming-split-done-skip.md   | [x]    |
| 27  | Idempotent launch + waiting state      | phase-27-idempotent-launch-waiting-state.md | [x]    |
| 28  | Teardown on Done                       | phase-28-teardown-on-done.md                | [x]    |
| 29  | Prompt hardening + roadmap binding     | phase-29-prompt-hardening-binding.md        | [x]    |
| 30  | Coherence hardening (audit S-batch)    | phase-30-coherence-hardening.md             | [x]    |
| 31  | Operator UX (status pane + WAITING)    | phase-31-operator-ux.md                     | [x]    |
| 32  | Dep-gate bounce-back                   | phase-32-depgate-bounce.md                  | [x]    |
| 33  | Dashboard rebind + init short-desc     | phase-33-dashboard-rebind-init-desc.md      | [x]    |
| 34  | Watchdog FP fix + README statuses      | phase-34-watchdog-fp-readme-statuses.md     | [x]    |
| 35  | E2E findings (probe/markers/doctor)    | phase-35-e2e-findings-fixes.md              | [x]    |
| 36  | Health window + orphan status updates  | phase-36-health-window-orphan-updates.md    | [x]    |
| 37  | Trust-audit fixes (14 defects)         | phase-37-trust-audit-fixes.md               | [x]    |
| 38  | Worktree helper PATH (pyenv-proof)     | phase-38-worktree-helper-path.md            | [x]    |
| 39  | Prompt shipped-exit mandates Done move | phase-39-prompt-shipped-exit.md             | [x]    |

## Review cycles

### Cycle 1

- Findings received: 39 (5 dimensions: code, errors, types, tests, comments — adversarially verified)
- Confirmed real + in-scope: 33 — **1 critical, 6 major, 7 medium, ~19 minor**
- Refuted (intentional design choices): 6
- Critical: `types-3`/`errors-6` — `column_key` carries the GitHub Status option NAME but `decide()` looks up the
  columns.yml KEY; default template uses key≠name for agent columns → **no agent launches on the default board** (masked
  by unit tests using the key). Fix approach (operator-chosen): **resolve at the columns layer**.
- Retained for fix this cycle: 1 critical + 6 major + 7 medium → 11 sub-phases (6.1–6.11)
- Minor (18): 7 folded into 6.x; the remaining 11 deferred minors were ALL corrected in **phase 7** (operator directive
  "correct everything") — corrupt-state robustness, `TicketStatus` enum, 4 test gaps, 4 doc nits, + the daemon JSONL log writer.
- Fix phases: `phase-06-pr-fixes-cycle-1.md` (crit/major/medium) + `phase-07-pr-fixes-cycle-1-minors.md` (all minors).

### Cycle 2 (2026-06-08 — post-implementation full-feature review, PoC-conformance objective)

- Run on the COMPLETE feature (PR #1, CI green). 6-dimension multi-agent workflow: 3 PoC-conformance batches
  (44 feature_losses + 26 behaviour_changes) + correctness + silent-failures + layering. Operator's added
  objective: the engine must do AT LEAST what the PoC did; every deviation must be a non-removing
  architectural improvement or a non-distorting addition.
- **Verdict: strong.** The 26 behaviour changes are ALL conformant (0 findings); the bulk of feature-losses
  faithfully restored + tested. The PoC-conformance lens caught gaps the per-sub-phase verification missed
  (they are _missing wiring_ no single sub-phase owned).
- **Retained real findings: 5** (after Opus filter; duplicates merged, justified-deviations confirmed):
  - **M1 (MAJOR, feature_DROPPED)** — agent prompts are HOLLOW: `{{issue_body}}`/`{{comments}}`/`{{codename}}`/
    `{{design_path}}`/`{{plan_paths}}` hardcoded `""`; `issue_context` ported in 16.1 but DEAD (no consumer,
    not on a port); no `parse_ticket_fields`. The PoC enriched every prompt. Deferred in 16.1 as "separate
    loss, out of scope" — never rescheduled.
  - **M2 (MAJOR)** — launch-gate script runs BEFORE the worktree exists → gated launch can never start (PoC
    bug #1 reintroduced; a MagicMock test masked it). Shipped board unaffected.
  - **M3 (MAJOR)** — schema-corrupt state silently dropped by `list_running` (the #17 breadcrumb only covered
    JSON corruption) → a stale agent can escape the reaper unseen.
  - **Md1 (MEDIUM)** — the durable move-rate-limit counter is write-only (nobody parks on `>= cap`); the #16
    justification went stale after phase 15 added auto/on_fail moves.
  - **Md2 (MEDIUM)** — `_drain_queue` already-running guard releases a LIVE ticket's slot + wipes its fix-CI
    budgets (cap undercount).
- **Minors/info (10)**: decision-time rate-limit uses hardcoded 10 not the configured value · `interactive_only`
  per-column dropped · seed no Backlog guard · `load` schema-corrupt silent · dead `quote_command` · daemon
  heartbeat write no-log · `move_count` corrupt→0 no breadcrumb · stale `agent_command`/`GithubClient`
  docstrings · `domain.py` Optional vs `X | None`.
- **Operator decision (2026-06-08): FIX ALL** (majors + mediums + minors) — "rien ne doit être laissé derrière".
- Fix phase: `phase-18-pr-fixes-cycle-2.md` (7 planned sub-phases, 18.1–18.7). Adversarial-verify 18.1+18.2 (prompt
  enrichment), 18.5 (park gate), 18.6 (drain guard). Merge stays HUMAN-ONLY after the gate.
- **Phase 18 COMPLETE (2026-06-09)** — all 5 majors/mediums + 10 minors fixed, gated per sub-phase:
  - `89db3ad` 18.1 M1a parse_ticket_fields → codename/design_path/plan_paths · `f8b8ee6` 18.2 M1b wire
    `issue_context` → {{issue_body}}/{{comments}} (dead adapter now a real consumer) · `71168eb` 18.3 M2
    worktree-before-launch-gate (PoC bug #1) · `481f261` 18.4 M3 schema-corrupt breadcrumb (3 readers × 2 branches) ·
    `2a3aae5` 18.5 Md1 cross-loop move-rate-limit PARK gate · `c26d8ca` 18.6 Md2 drain live-slot guard
    (+ `_drain_queue` extracted to `app/drain.py` for LOC headroom; tick.py 1009→891) · `52f526a` 18.7 the 10-minor
    long-tail (rate-limit config wiring, seed Backlog guard, `interactive_only` wired, dead `quote_command` removed,
    heartbeat + move_count breadcrumbs, docstrings, Optional→X|None).
  - **Adversarial verification (ultracode): 9 independent skeptics × 3 lenses on the 3 keystones → 9/9 CLEAN**
    (0 real defects, confidence 0.85–0.97). One benign counter-hygiene NOTE on 18.5 closed by `d2a9671` 18.8
    (rate-park resets the fix-CI loop budget, PoC parity with the cap-park).
  - `make check` GREEN throughout (1057 passed, 8 skipped; ruff + mypy src+tests; layering 4/4; LOC all ≤ 1000,
    client.py at the 1000 ceiling). Next: milestone commit → re-push → CI → cycle-2 re-review (max 5).

### Cycle 3 (2026-06-09 — re-review of the phase-18 fixes, PoC-conformance objective)

- Run after the phase-18 milestone (`2224113`), re-pushed (`5616af4..2224113`), CI GREEN. Focused 4-agent
  workflow over the phase-18 delta (`89db3ad..2224113`): completeness vs the 15 cycle-2 items · non-keystone
  correctness/no-regression · new-defect hunt · final PoC-conformance.
- **Verdict: 3/4 areas CLEAN.** Completeness = all 15 cycle-2 items genuinely closed; non-keystone correctness
  = no regression; final PoC-conformance = the engine now does at least what the PoC did across every
  phase-18-touched area. (The 3 keystones were already 9/9 adversarial-clean before the milestone.)
- **Retained findings: 1 MEDIUM (+ 1 coupled MINOR)** (after Opus filter):
  - **MEDIUM (deviation_UNJUSTIFIED)** — `kanban seed`'s Backlog-landing guard is SKIPPED on the explicit
    `--project-id` path: `GithubClient` has no `status_options`, so the `_known_status_options` probe misses and
    the pre-check can't fire → a board without a `Backlog` option half-seeds (orphaned issue 1, then
    `move_card` raises). The PoC had no `--project-id` override and ALWAYS guarded via the registry option_map;
    NEW's additive override introduced the unguarded path.
  - **MINOR (coupled)** — `client.py` at exactly 1000 LOC: the fix (add `status_options`) can't land without
    first restoring headroom.
- Fix phase: `phase-19-pr-fixes-cycle-3.md` (2 sub-phases): 19.1 extract `UrllibTransport` → `_transport.py`
  (headroom), 19.2 add `GithubClient.status_options` + the `--project-id` guard test. Merge stays HUMAN-ONLY.
- **Phase 19 COMPLETE (2026-06-09)** — both sub-phases gated:
  - `5214995` 19.1 extract `UrllibTransport`+`Timeouts`+`_is_transient` → `adapters/github/_transport.py`
    (client.py 1000→702, `_transport.py` 343; `__all__` re-export keeps `test_pagination` import working;
    behaviour-preserving) · `61b6c3b` 19.2 add `GithubClient.status_options` (reuses
    `_queries.status_option_map`+`_parsers.parse_status_option_map`; seed.py unchanged — its getattr probe now
    resolves) → the `--project-id` seed path is guarded (test proves no half-seed; PoC parity restored).
  - `make check` GREEN (1060 passed, 8 skipped; ruff+mypy src+tests; layering 4/4; all modules ≤ 1000,
    client.py back to 726 with headroom). Next: milestone → re-push → CI → cycle-4 re-review (max 5).

### Cycle 4 (2026-06-09 — re-review of the phase-19 fixes, last gate before human merge)

- Run after the phase-19 milestone (`b947973`), re-pushed (`2224113..b947973`), CI GREEN. Focused 3-agent
  workflow over the phase-19 delta (`ede4702..b947973`): cycle-3 finding closure + new-defect hunt ·
  `UrllibTransport` extraction soundness · final completeness/PoC-conformance.
- **Verdict: 3/3 CLEAN — zero findings.** The `--project-id` half-seed (cycle-3 MEDIUM) is closed and the test
  exercises the real probe path; the `UrllibTransport` extraction is behaviour-preserving (timeouts + retry
  intact, re-export + monkeypatch retargets correct, no circular import, layering green); no new PoC-conformance
  regression and nothing glaring left behind.
- **Decision: Case A (no critical/major/medium retained findings) → review loop EXITS clean.** merge*mode=manual,
  so the loop hands off to the human for the squash-merge of PR #1 (merge is HUMAN-ONLY; the daemon/agents
  never merge — DESIGN §autonomy). The branch is merge-ready and CI-green at `b947973` (+ the cycle-4 doc commit).
  *(Superseded: genesis was then REOPENED for the transitions-only re-architecture — phases 20-21 — so the
  merge-handoff moved to cycle 5.)\_

### Cycle 5 (2026-06-09 — re-review of the transitions-only re-architecture, phases 20-21)

- Run after phases 20-21 (`7550c49`), re-pushed (`34760d4..7550c49`), CI GREEN. Focused 3-agent workflow over
  the delta (`34760d4..7550c49`): broader-engine no-regression · final PoC-conformance · completeness/new-defect.
  (The phase-20 keystones were already adversarially 5/5 clean before this.)
- **Verdict: broader-engine no-regression CLEAN; 5 findings — ALL MINOR, all doc/comment/spec-consistency, ZERO
  behavioural defects.** (1) DESIGN §9 `Review→Merge on_fail` said `move:Review` but the code correctly ships
  `rollback` (the phase-15.6 fix `be5fe2f` — a gate-fail must not re-fire) → DESIGN was stale, corrected to
  `rollback` (code untouched). (2) §3.3 module map listed `ColumnClass{agent|...}` (AGENT removed). (3) §14 P5
  "column-class/action model" prose. (4) stale "legacy column-class path" comments in tick.py/loop.py (that path
  now hard-errors; wiring always supplies DEFAULT_TRANSITIONS). (5) columns.yml.tmpl Merge comment "the bot
  cannot reach it" (an agent CAN move into Merge — it is not a launch target; the boundary is branch protection +
  the `gh pr merge` ban).
- **All 5 reconciled in `09c6612`** (doc/comment-only; `make check` green 1060 passed; `transitions_defaults.py`
  untouched). **Decision: Case A — review loop EXITS CLEAN.** merge_mode=manual → hand off to the human for the
  squash-merge of PR #1. Cycle 5 is the max; the loop is done.

## Notes

- **Migration phases 8–11 (planned)** — finish the extraction + cut over from the OLD PoC. Mandatory
  order: **8 → 9 → 10 → §11.0 OLD-disable runbook → 11 → decommission (§11 below)**.
  - **8** — PoC parity port: rich two-zone stage-comment subsystem (replaces the one-line sticky
    writer) with the FULL signaling lifecycle 🟡→✅/⚠️/⛔→❌ (operator decision — all FIVE producers:
    launch 🟡 `in progress` · forward-advance ✅ `done` · session-end ⚠️ `interrupted` · reaper ⛔
    `blocked` · teardown ❌ `cancelled`; ENGLISH badge labels on the GitHub stickies) + full Cancel
    teardown (`--force` worktree, local `branch -D`, close PR + KEEP remote branch, flip open
    stickies ❌, recap). Sub-phases: 8.1.a pure core · 8.1.b app-upsert via widened port · **8.1.d WIDEN
    `TicketState` (launch stage + header metadata: profile/mode/started/worktree) + fs-store advance
    breadcrumb RE-KEYED to NEW's issue number (re-thread the column+breadcrumb+metadata context NEW
    dropped)** · 8.1.c producers (launch 🟡 / reaper ⛔ — **8.1.d sequenced BEFORE 8.1.c** so the
    reaper's stage/header exist) · **8.1.e daemon
    ✅-on-forward-advance (`_finalize_left_stage`; tick PRE-READS the LEFT `TicketState` before
    `LaunchAction` overwrites the slot) + synchronous agent breadcrumb** · **8.1.f session-end
    ⚠️-when-no-breadcrumb (`finalize_session` ported into `bin/kanban_session_end.py`)** · 8.2.a–d
    Cancel teardown. The breadcrumb is the ✅/⚠️ discriminator, keyed by issue number, written
    synchronously before the agent exits (OLD's race-closing design). The widened `TicketState`
    gives NEW's ✅/⚠️/⛔ stickies OLD's full metadata bullets (full parity). Code phase (`make check`
    gate per sub-phase).
  - **9** — permission `defaultMode` `acceptEdits` → **`auto`** (headless-safe; PoC unattended-hang
    fix). Code phase.
  - **10** — interpreter bump to **pyenv 3.12.4** (pyproject + CI), editable re-install. Build/CI.
  - **11** — `§11.A` (the one code commit, TDD) adds a first-class `kanban install --kanban-command
<abs>` flag so the install command bakes the operator-supplied absolute pyenv-3.12 `kanban` into
    the generated `ecosystem.config.js` `script:` line (no hardcoded host path, no hand-rolled
    `_write_ecosystem(...)`); then operational: `§11.0` disables OLD (launchd reaper, n8n entirely,
    org webhook, `~/.kanban`) BEFORE NEW starts; then install (using `--kanban-command`) / PM2 points
    at the absolute pyenv-3.12 `kanban` via that flag / `init` a FRESH Project v2 / paste PAT /
    `seed` / `run` / verify. PAT is the one carry-over; board is fresh.
- **Ingress = unified polling** (no n8n/webhooks). Hardening items H1/H2 are erased by the polling
  pivot (DESIGN §6).
- **Pre-implementation gate**: re-sync the latest PoC code (sticky comments, Cancel, heartbeat #67)
  from `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/` (the ABSOLUTE OLD root; engine under
  `.../skills/kanban/kanbanmate/`) before porting (DESIGN §11).
- Default poll interval 10 s + cheap-probe + adaptive idle back-off.
- GitHub token scope: `project` + `repo` only (no `admin:org_hook`).

## Next action

Phases 1-11 complete — **cutover done LIVE 2026-06-05** (OLD disabled, NEW installed under pyenv 3.12.4,
fresh Project v2 linked to `IznoCorp/personal-scraper`, 50 issues seeded to Backlog, daemon online,
`doctor` green; §11.7 OLD-source decommission deferred post-merge). The live cutover surfaced **6 real
bugs** (all fixed + committed: interpreter:none, config.yml↔registry wiring, cheap_probe, seed→Backlog,
doctor scope-check, init project-link) AND a **PoC-parity audit** (`POC_PARITY_AUDIT.md`): **44 confirmed
feature losses** the genesis extraction silently dropped (headline: the per-(from,to) transition-whitelist
model → replaced by a column-class simplification; plus cap/queue, rate-limit, clone/worktree provisioning,
prompt routing).

**Restoration phases 12-17** (plan files written; `DESIGN_RESTORE_DELTA.md` applied to DESIGN.md at
commit `10f4148`): 12 transition model + prompt routing · 13 cap/queue/rate-limit · 14 clone + worktree
provisioning · 15 reaper retry + audit + script gates · 16 GitHub/CLI parity · 17 behaviour reconciliation.

**Phase 12 COMPLETE (2026-06-06)** — 9 sub-phases, all gated green (699 tests). Headline: the per-`(from,to)`
transition whitelist + `placeholders.fill` + the filled `/implement:*` launch prompt + ROLLBACK/RUN_SCRIPT
verdicts + the renderer/writer/init-emit + tick wiring + WiringConfig load. **Operator decision 2026-06-06
— HYBRID board**: `transitions.yml` ships the FULL PoC 7-stage flow; `columns.yml` `triggers_agent` gates
per-column autonomy (`decide()` agent-class launch gate: a prompt into an inert column = dormant NOOP);
default classes unchanged (early stages interactive); unified column set = NEW keys + added `PrepareFeature`;
merge stays human (no autonomous merge prompt). **Deferred live-board op (post-merge): add the `PrepareFeature`
column to the `IznoCorp/personal-scraper` Project v2** (one column; the running daemon still ticks the legacy
column-class path until the live clone is re-init'd with a `transitions.yml`).

**Phase 13 COMPLETE (2026-06-06)** — 6 base sub-phases (13.1–13.6) + 2 adversarial-verification correctives
(13.7, 13.8), all gated green (770 tests). Restored: durable per-issue move rate-limit history + fix-CI retry
counter + queue persistence (fs-store); board-level `concurrency_cap`/`move_rate_limit_per_hour` defaults;
the launch-path **concurrency cap gate + real queue drain** (the audit's "reserve*slot never called" + the
`_drain_queue` stub, both closed); the durable rate-limit gate feeding the §6 park-in-Blocked backstop.
**Multi-agent adversarial verification (ultracode) earned its keep**: a 4-lens skeptic pass on the 13.5
keystone found a **CRITICAL** bug — the drain's failed-launch path called the exhaustive `release_slot`,
**deleting the queue marker it meant to keep** (silently dropping a transiently-failing ticket forever),
masked by a MagicMock test. Fixed in **13.7** by restoring the PoC two-function split (`release_slot`
slot-only vs `purge_ticket` exhaustive) + closing 5 minor marker bugs; the keep-marker test now runs on a
REAL `FsStateStore`. A re-verification then found the reaper/session-end `purge_ticket` wiped the durable
budgets, making 13.6's rate-limit inert (tests stubbed `purge_ticket` to pass) — fixed in **13.8**
(`keep_budgets=True` on reaper + session-end; Cancel/Reset keep the full purge). **Operator decisions
2026-06-06**: (1) **rich queue payload** — the drain rebuilds a launch byte-identical to a direct one so the
filled `/implement:*`prompt survives a queue divert (nothing left behind); (2) **Option A** — the reaper
preserves`moves/`+`retries/`so the durable rate-limit actually accumulates.
**Documented residual** (deferred, out of phase-13 scope): a DIRECT-launch watchdog \_timeout* can transiently
run an agent without a slot (cap+1) until the reaper reconciles — a full fix needs a tri-state`\_run_with_watchdog`. **Tech-debt**: `tick.py`is 915 LOC (soft warning 800, hard ceiling 1000) — a candidate
to extract`\_drain_queue`/`\_reap_stale_agents` into a sibling module in a later phase (plan said
note-don't-refactor-blindly; not done to avoid regressing the just-corrected concurrency code).

**Phase 14 COMPLETE (2026-06-07)** — 6 sub-phases (14.1–14.6), all gated green (816 tests). Restored the
LOCAL CLONE bootstrap + WORKTREE SKILL PROVISIONING the first extraction dropped wholesale (POC*PARITY_AUDIT
§engine/§CLI, 5 confirmed losses): **14.1** `ensure_clone` on the `Workspace` port/adapter (git init IN PLACE,
idempotent self-healing origin probe-then-add-or-set-url, fetch) · **14.2** credential-helper **token isolation**
(tokenless `origin` + a fetch-time `cat`-the-token shell helper so the PAT NEVER lands in `<clone>/.git/config`;
`--replace-all ""` then `--add` clears the inherited helper chain) · **14.3** per-repo **flock** `resource_lock`
serialising clone mutations (self-contained adapter copy of `engine/locks.py`, `repo\_\_<owner>*<name>.lock`) ·
**14.4** `provision_worktree_skills`(COPY — never symlink — skills/commands/agents into`<worktree>/.claude/`)

- `ensure_manual_merge_mode` (pin `**PR merge**: manual`, defense-in-depth alongside the deny-list) · **14.5**
  the **launch argv builder** (`claude --session-id <uuid> --permission-mode <mode> --add-dir <worktree>` wrapped
  `; kanban-session-end <issue>` with `;` not `&&` so the wrapper ALWAYS fires; the UUID is the single source of
  truth, persisted as `session_id` — restoring `claude --resume <uuid>`, DESIGN §8.3) · **14.6** wired it all live:
  registry `config_dir`/`dev_repo_path` (OLD-shaped `projects.json` still loads via `.get()`), `kanban init
--dev-repo-path`, `ensure_clone` at init (BEFORE the columns.yml write, tokenless URL + `<root>/token`), and
  `LaunchAction` provisioning (settings → provision → pin merge → launch). **Plan-vs-reality seam (14.5)**: phase 12
  already moved the launch path to a per-transition prompt-fill (`_agent_command`) with explicit `# phase 14:
build_claude_argv` markers — so 14.5 INTEGRATED (the filled `/implement:*` prompt is preserved as claude's
  positional first message, shlex-quoted by the wrapper) rather than regressing it; `--permission-mode` uses the
  per-transition `self.permission_mode` (not the plan's pre-phase-12 `pinned_mode(deps.profile)`), kept consistent
  with the persisted `TicketState.mode`. The legacy `Deps.agent_command` is now a vestigial knob (the PoC-faithful
  `build_claude_argv` drives BOTH paths). **Adversarial verification (ultracode, 3 lenses × 3 keystones)**: the
  security-critical **14.2** token isolation, the **14.5** launch keystone, and the **14.6** wiring keystone each
  passed a 3-lens skeptic sweep with ZERO real defects (token never in any git argv; UUID == `--session-id` value
  == persisted `session_id`; `;`-wrapper always fires; shlex-quoting defeats prompt-injection; provisioning runs
  before launch and skips cleanly on empty config_dir; OLD-registry backward-compat). **Drift carried (minor)**:
  `quote_command` (phase-12 helper) is now unused after the 14.5 integration — left in place (no dead-code linter;
  out of 14.5 scope), a candidate for a later cleanup. **Tech-debt unchanged**: `tick.py` 915 LOC.

**Phase 15 COMPLETE (2026-06-08)** — reaper retry + dispatch audit log + mechanical script gates; all gated
green (877 tests, +61). Three genuine PoC-parity losses restored — but a mid-phase discovery RE-SCOPED half
the plan. **15.1** widened `TicketState(retries)` + the fs-store per-(issue,key) retry ledger (`bump_retry`/
`reset_retry`, purge on `release_slot`) · **15.2** the reaper now **relaunches a stale session ONCE**
(`RETRY_LIMIT=1`: kill the dead tmux + bump retries + REFRESH the heartbeat + relaunch the same stage under the
watchdog; relaunch-raises / `stage==""` → Blocked; `relaunched` counted separately from `reaped`) · **15.3**
the per-dispatch append-only audit log (`<root>/log/dispatch.jsonl`, port `append_dispatch`, fail-soft LAST
step of `LaunchAction`). **RE-SCOPE (operator-approved, 2026-06-08)**: §15.4-15.7 were authored against a
stale view — they assumed NO script infra and proposed a per-**Column** model, but phases 12-13 already shipped
the whole script-transition family on the per-`(from,to)` **Transition** model (Transition.script/advance/on_fail,
decide emits RUN_SCRIPT/ROLLBACK, RunScriptAction/RollbackAction, the board wires both check scripts). So **15.4**
was REVERTED (it had created a duplicate `ScriptRunner`; `Workspace.run_transition_script` is the seam) · **15.5**
was already shipped (no-op) · **15.6** wired the genuine gap — the routing **EXECUTION** in the tick + a new
`app/script_route.py`: success → reset fix-CI ledger + `advance:auto` triggering move (baseline stays at the
script col to re-fire) + finalize LEFT ✅; failure → `on_fail:move` (bump the 15.1 ledger; `>_FIXCI_CAP=2` → park
Blocked) / `on_fail:rollback` → `from_col`; plus the **launch-gate veto** (run `script` first, exit≠0 → no agent

- route on_fail) and `save_script_output` persistence. The reaper was extracted to `app/reaper.py` for LOC
  headroom (tick.py 988→905) · **15.7** filled `{{script_output}}` from the persisted check output (the fix-CI
  agent now gets the real failure) · **15.8** env-guard tests for the two check scripts (no `gh`) + dual-role
  headers. **Adversarial verification (ultracode)**: 15.2 (3 lenses) found 1 high-sev state-coherence defect
  (a fresh-heartbeat RUNNING zombie if `purge_ticket` fails on the relaunch fall-through) → FIXED `b32ea56` (write
  `status=IDLE` before teardown, port of the PoC `_move_to_blocked` ordering). 15.6 (4 lenses) found 1 **critical**
  defect — the merge gate's `on_fail:move:Review` stranded a failed card in the **Merge** column (a false
  "ready-to-merge" signal: `(Merge→Review)` isn't whitelisted → rollback-bounce) → FIXED `be5fe2f` (`on_fail:rollback`,
  the correct bookkeeping return; `check-pr-ready`'s `move:InProgress` stays — `(PRCI→InProgress)` IS the whitelisted
  fix-CI loop). All other lenses (fix-CI cap, launch-gate veto, reaper-extraction fidelity, audit log) clean.
  **Tech-debt**: `tick.py` 905 LOC + `fs_store.py` 833 LOC (both soft-warn, under the 1000 ceiling). Commit trail:
  15.1 `28ac368` · 15.2 `b4712e5`+`b32ea56` · 15.3 `a1725e9` · 15.4-revert `a23a15a` · re-scope `62ac687` ·
  15.6 `513e129`+`be5fe2f` · 15.7 `c6a8ee3` · 15.8 `802f7a8`.

**Phase 16 COMPLETE (2026-06-08)** — GitHub-adapter + CLI/doctor parity; all gated green (929 tests, +52).
Six CONFIRMED non-pivot losses restored — and (per the phase-15 lesson) every "X is absent" premise was
VERIFIED against `src/` before dispatching; all six held (genuine gaps, no duplication). **16.1** ported
`issue_context` (GraphQL body + ≤50 comments + first linked-Issue body → frozen `IssueContext`; faithful
adapter port, documented no-in-tree-consumer-yet) · **16.2** REST issue-comments **Link rel=next pagination**:
the root cause was that `UrllibTransport._request` captured only the body, so `Link` was structurally
inaccessible → a sticky on page 2+ was invisible → a DUPLICATE sticky each tick. Added the headers-bearing
transport seam (`_request_with_headers` is now the SINGLE timed read impl; `_request` is a thin body-only
wrapper — connect+read timeout discipline preserved, CLAUDE.md-MANDATORY) + a new `_rest.py` (`next_link_path`

- the per_page=100 builders) + the pager · **16.3** `find_open_pr` onto `_rest` (per_page=100, owner-qualified
  head) reusing the 16.2 pager · **16.4** the LIVE branch-protection doctor probe (pure `core/probes.py` parser
- fail-soft `branch_protection_on` 404→False + `_resolve_branch_check` wired from `projects.json` into the
  production `doctor()` — was always the hollow advisory placeholder; stays advisory/WARNING-only) · **16.5** the
  `sessions` report restores the PoC TSV `#N\t<tmux>\t<live|DEAD|stopped>\t<status>` + the third `stopped` bucket
  via a new `StateStore.list_all` (all-states, distinct from the RUNNING-only `list_running`) · **16.6** ported
  `issue_state` (GraphQL open/closed) + `parse_issue_closed`, declared on the `BoardReader` READ port — the HARD
  PREREQUISITE for the phase-17 #13 dependency-gate fallback. **Adversarial verification (ultracode)**: 16.2 (2
  lenses) — timeout-safety CLEAN (single timed read path confirmed); the pagination lens found 1 high-sev
  **infinite-loop** risk (a self-referential `Link rel=next` would re-fetch the same page forever, a tick-blocking
  spin) → FIXED `d2ff091` (a `seen`-set non-advancing-link guard, mirroring NEW's existing GraphQL-pager
  `end_cursor==after` break; 16.3 reuses the guarded pager). **Tech-debt**: `client.py` 911 LOC, `fs_store.py`
  863, `tick.py` 905 — all soft-warn, under the 1000 ceiling (client.py is the one to watch). Commit trail:
  16.1 `21c265e` · 16.2 `bcb01c5`+`d2ff091` · 16.3 `e3b7d86` · 16.4 `ad7db89` · 16.5 `f06975f` · 16.6 `04ee7c7`.

**Phase 17 COMPLETE (2026-06-08)** — behaviour reconciliation (the long-tail faithfulness pass); all gated
green (1005 tests, +43). The 26 confirmed BEHAVIOUR CHANGES are resolved — each PORT restored, each KEEP+DOC
documented + asserted. Per the phase-15 lesson, all 26 premises were VERIFIED against `src/` before
dispatching: 15 held as genuine work; **#21 was a CONTRADICTION** (the 2026-06-05 "remove dead
`TicketStatus.IDLE`" decision predated phase 15.2 making it load-bearing) → operator re-scoped to KEEP+DOC
(`161b03b`). **17.1** agent-helper parity (kanban-comment bare-positional→free-form default, kanban-progress
auto-stage from `TicketState.stage` §8.1.d; kanban-move Merge-inert + breadcrumb KEEP+DOC) · **17.2**
CLI-surface (doctor scope **required-floor**: missing→FAIL / over-scope→WARN / fine-grained→advisory; status
per-ticket column+uuid; seed registry auto-resolve; gh-removed/tmux-ownership/cancel-destructive/logs-daemon-jsonl
KEEP+DOC) · **17.3** github transport **transient 502/secondary-rate retry** (timeouts on every attempt, bounded
~3s) + dead GraphQL comment path deleted + the **#13 HYBRID dependency gate** (pure tri-state
`DependencyVerdict` MET/UNMET/UNKNOWN; `app/tick` live `issue_state` fallback for off-board deps — fail-soft,
zero-query common case) · **17.4** corrupt-state stderr diagnostic + teardown rate-limit `forget` (Cancel-only —
the reaper keeps budgets, a PoC-faithful drift) + rollback-aware `bookkeeping` flag + IDLE-load-bearing doc ·
**17.5** WIRE per-column `permission_profile` (two-tier transition→column→**FAIL-LOUD**, no silent global, bypass
ban intact end-to-end) + the rate-limit counter audit (#16 already correct from 15.6 — KEEP+DOC) + the 9→5
ActionKind mapping doc · **17.6** reaper **dead-session trigger** (reap on heartbeat-stale OR dead tmux, fail-closed
probe, composes with 15.2) + heartbeat hook bakes the **resolved absolute shim path** (fail-soft). **Adversarial
verification (ultracode)**: 17.3 (3 lenses — transport timeout-safety / hybrid-gate fail-soft+perf / dead-code) and
17.5 (3 security lenses — no-silent-global / bypass-ban / relaunch-resolution) BOTH returned ZERO real defects.
**LOC management**: extracted `app/depgate.py` (17.4) + `core/columns.column_profile_for_stage` (17.5) to keep
`tick.py` < 1000 (now 989). **Tech-debt**: `client.py` 994, `tick.py` 989, `fs_store.py` 913 — all soft-warn, under
the ceiling. Commit trail: re-scope `161b03b` · 17.1 `c913f59` · 17.2 `33d34c5` · 17.3 `b3efc62` · 17.4 `4177150`
· 17.5 `51ed1af` · 17.6 `bddf37b`.

**Phases 1–17 COMPLETE; PR #1 pushed + CI GREEN.** Cycle-2 PoC-conformance review found 5 real gaps (1 MAJOR
= hollow agent prompts, a dropped PoC feature) + 10 minors → operator: FIX ALL (`phase-18-pr-fixes-cycle-2.md`).
A post-milestone CI fix already landed: `5616af4` (check scripts read CI JSON from env not stdin — a latent
PoC bug that always failed the CI parse).

**genesis REOPENED (2026-06-09) — transitions-only re-architecture (phases 20-21).** While starting a live
test, the operator found the live `personal-scraper` board was running the **legacy column-class fallback**
(no `transitions.yml`). The investigation established: the engine HAS the PoC per-`(from,to)` transition
model + `init` ships it, but (a) the phase-12.6 **HYBRID** (a per-column `triggers_agent` autonomy gate) was
a genesis bolt-on that diverged from the PoC, and (b) a missing `transitions.yml` silently degraded to a
column model. **Operator decision: remove the column-class model entirely — transitions-only, the agent
launches AT THE TRANSITION (not the column), ALL launch config (`prompt`/`profile`/`permission_mode`/
`script`/`advance`/`on_fail`) on the transition; `from`/`to` accept single | list | `*` (cartesian).** This
is fully PoC-faithful (PoC columns = a bare name list; all behaviour on transitions). DESIGN §8.0.1/§8.0.2/
§8.0.6/§9 rewritten accordingly. The cycle-4 "merge-ready" state is **suspended** until phases 20-21 + a
cycle-5 re-review land.

**Phase 20 COMPLETE (2026-06-09) — transitions-only engine.** 6 sub-phases, each gated:
`0bbd5ed` 20.1 from/to list expansion (cartesian + dup-reject) · `b9e13e5` 20.2 no-transitions.yml →
DEFAULT*TRANSITIONS fallback · `357f49d` 20.3 decide transitions-only (no column-class gate; None →
hard-error; unattended gate removed — PoC has none, confirmed) · `a678905` 20.4 profile resolves from the
transition only (drop the column-default tier; reaper relaunch reuses persisted profile) · `1ae0c2a` 20.5
kanban-move anti-loop guard keys on launch-transition targets (DESIGN §8.0.5; an agent blocked on the
gap — the guard still keyed on `ColumnClass.AGENT` — so a 20.5 was inserted before the field removal) ·
`984ac36` 20.6 remove the dead column launch fields + `ColumnClass.AGENT` + `column_profile_for_stage`;
`columns.yml.tmpl` ships a bare 12-col set. `make check` green (1060 passed); `ColumnClass` = {REACTIVE,
INERT}; no live reader of any column-launch field. **Adversarial verification: 5 skeptics (20.1/20.3/20.4/
20.5 + end-to-end) → 5/5 CLEAN** (one documented non-defect: a `to:'*'` \_prompt\* transition — pathological,
unused by the shipped flow — is not enumerable as a concrete launch-target; the guard is complete for the
shipped flow). DESIGN §8.0.1/§8.0.2/§8.0.6/§9/§10 reconciled to transitions-only.

**Phase 21 COMPLETE (2026-06-09) — live board migrated.** Idempotent re-`kanban init` on
`IznoCorp/personal-scraper` (reused project PVT_kwDOB3abh84BZ1fU — no duplicate): added the `Prepare
feature` Status option (board now 12 columns), wrote `<clone>/.claude/kanban/transitions.yml` (the PoC
flow, 14 entries) + a bare `columns.yml`, refreshed the registry option_map. Daemon stopped → re-init →
restarted (PM2, now on the phase-20 code) → loads the whitelist; `kanban doctor` all PASS; no
`unknown column` warnings since restart. The **transitions-only PoC flow is LIVE** on the board.

**Phase 22 COMPLETE (2026-06-10) — perms profile regression fix.** An adversarial review run during the
`helm` config-interface prep found, grounded against `src/`, that genesis collapsed the PoC's 5 permission
profiles (`docs/prepare/dev/check/merge`) to `safe/trusted` in `adapters/perms.py` while `DEFAULT_TRANSITIONS`
still ship `docs/prepare/dev/check` → every agent silently materialised the `safe` allow-list (no
push/PR/make) and `trusted` was dead code. Functional bug + PoC-conformance regression, undetected because
the live test never ran. Fix `9b5125b` (Opus dispatch, sub-phase 22.1): restored the 4 PoC profiles verbatim
(`merge` stays REMOVED = human-only; universal deny intact; `allow_list` fallback → `docs`, degrade-safe).
Reconciled the kill-switch floor (`DEFAULT_PROFILE safe→docs`, confirmed dead post-phase-20),
`decide.py`/`transitions.py`/`launch_argv.py` docstrings, DESIGN §8/§10/H4/H5, and 12 test files.
`rm -rf .mypy_cache && make check` GREEN (1097 passed, 8 skipped; mypy/ruff clean; 2 pre-existing LOC
soft-warnings). Memory: `genesis-perms-profile-regression`.

**FINAL STATE (2026-06-11): all 35 phases `[x]` — the ONLY remaining act is the HUMAN squash-merge of
PR #1.** Phases 30-35 (operator-directed, deployed live on the v2 board): the coherence-hardening audit
batch (12 items), operator UX (status pane + pause/resume + WAITING hardening), dep-gate bounce-back,
dashboard project rebind + init short-description, watchdog false-positive fix + README status table,
and the e2e-findings fixes (unpushed-work pin filter, claude v2.1.170 REPL markers, doctor shim check).
Live validation: ticket #151 ran the FULL hardened autonomous flow (state-check-first → ALREADY_SHIPPED
evidence → append + codename → self-classified Done) with zero human intervention. Final gate `1397
passed`; CI green at `90f6d96`; PR #1 MERGEABLE. After the merge: `/implement:archive`.

**Post-readiness live-bug fix (2026-06-13) — status-update PILL stuck + delete mutation broken (§8.7).**
Operator reported the v2 board pill stuck `OFF_TRACK` for days while the API record read `ON_TRACK`.
Root cause (two bugs): (1) GitHub refreshes a Project's denormalised status pill **only on create**,
never on an in-place `update`; the reporter edited ONE rolling record in place forever, so the pill
stayed frozen at its creation enum. Fix: `report_status` now **re-creates** the rolling update when the
health enum changes (tracking `status/last_status`), keeping in-place `update` for body-only changes.
(2) `delete_status_update` selected `statusUpdate { id }`, a field absent on
`DeleteProjectV2StatusUpdatePayload`, so **every** orphan delete silently failed (52 stacked on the
retired board #3); fix: select `deletedStatusUpdateId`. Gate `1449 passed`; daemon restarted (editable);
v2 unblocked (single fresh `ON_TRACK` record); orphans purged. New tests: re-create-on-enum-change,
update-in-place-same-enum, `last_status` round-trip, and a delete-selection lock.

_(superseded narrative below retained for trail:)_
**Superseded — Next: HUMAN squash-merge of PR #1** — the review loop EXITED CLEAN at cycle 5 (Case A; the 5 minors
reconciled in `09c6612`). Phases 22–25 were added post-readiness (operator-directed, all deployed live):
`9b5125b` restored the PoC permission profiles (perms regression), `d139aa8` fixed the 10s poll cadence
(removed the idle backoff), and `07979de`/`54ef895`/`27e2c33` added the rolling Project status-update
dashboard (§8.7); phase 25 fixed four launch-path bugs the FIRST live e2e surfaced — send-keys prompt
delivery (`89728b3`, the agent now actually receives its prompt), promptless reaper relaunch (`9ce33f0`),
cancel reset + teardown order (`ad97a86`), dashboard title (`d364b61`). Phase 26 (e2e-driven) split the
interactive brainstorm from the autonomous design — added `Brainstorming` + `Plan` columns
(`dd58b61` code, `6284004` DESIGN), made every non-brainstorm prompt autonomous (fixes the unattended-hang),
and whitelisted an early skip-to-Done from the 6 pre-PrepareFeature columns (lets an agent mark an
already-shipped ticket Done); the live `personal-scraper` board was migrated to the 14-column flow + daemon
restarted. Phase 27 (e2e-driven) made `TmuxSessions.launch` idempotent (`eb3bfe0` — kills a stale
same-named session first, fixing the #91 Spec→Plan collision) and added a `WAITING` agent state
(`2b54e16` — the reaper no longer kills an agent that is waiting for human input; it marks WAITING +
signals via the ⏳ sticky header + the dashboard AT_RISK pill; only hung/idle agents are reaped). All 27
phases `[x]`; the transitions-only re-architecture is done + adversarial-clean

- the live board is migrated to the PoC flow. CI green at `09c6612` (after the push below). The daemon/agents
  never merge (HUMAN-ONLY). After the merge: `/implement:archive`. Still open (thread B): the LIVE TEST — move a
  Backlog card → `Spec` to watch `/implement:brainstorm` launch, then `kanban cancel`. _(superseded lines below retained for trail:)_
  **Superseded — two threads (code finalize + live test); code finalized via cycle 5.**
  **Superseded — HUMAN squash-merge of PR #1 (cycle-4 clean; reopened for the transitions-only re-architecture).**
  **Superseded — `/implement:feature-pr` (re-push the phase-19 fixes → CI poll) → `/implement:pr-review` (cycle-4 re-review, max 5).**
  **Superseded — `/implement:phase` (phase 19 — cycle-3 fix).**
  **Superseded — `/implement:feature-pr` (re-push the phase-18 fixes → CI poll) → `/implement:pr-review` (cycle-2
  **Superseded — `/implement:feature-pr` (re-push the phase-19 fixes → CI poll) → `/implement:pr-review` (cycle-4 re-review, max 5).\*\*
  **Superseded — `/implement:phase` (phase 19 — cycle-3 fix).**
  **Superseded — `/implement:feature-pr` (re-push the phase-18 fixes → CI poll) → `/implement:pr-review` (cycle-2
  re-review, max 5).** Then human squash-merge of PR #1 (merge is HUMAN-ONLY).

Phase-10 trail: `8c22ffe` 10.1 pyproject→3.12 · `137875f` 10.3 CI→3.12 · operator reinstalled editable
under pyenv 3.12.4 (10.2) · `d35e37a` 10.4 fix (py3.12 mypy comparison-overlap) + gitignore
`.python-version` · `<gate>` phase-10 milestone. Reminder: clear `.mypy_cache` before every gate check
(its incremental cache masked real errors earlier in this feature).

**Remaining = phase-11 live cutover, OPERATOR-RUN, in order:**

1. **§11.0** OLD-disable (BLOCKING): `launchctl bootout` the `xyz.iznogoudatall.kanban-reaper` agent + rm
   its plist; `pm2 stop n8n && pm2 delete n8n && pm2 save`; delete the GitHub org webhook
   (`n8n.iznogoudatall.xyz/webhook/kanban`); `mv ~/.kanban ~/.kanban.old-$(date +%s)`.
2. **§11.1–§11.6** NEW activation: `kanban install --kanban-command "$(pyenv which kanban)"` → paste a
   `project+repo`-scoped PAT into `~/.kanban/token` (chmod 600) → `kanban init --repo IznoCorp/<repo>`
   (FRESH Project v2) → `kanban seed ROADMAP.md` → `pm2 start ecosystem.config.js --only kanban && pm2 save`
   → verify (`kanban doctor`, a real Backlog→agent card-move launching a non-hanging `auto` agent,
   in-daemon reaper). Then mark phase 11 `[x]` → re-invoke `/implement:phase` to chain into the PR flow.
3. **§11.7 / post-merge**: decommission OLD source in `PersonnalScaper/.claude` (separate repo) per the
   Notes block below.

Exact commands live in `docs/features/genesis/plan/phase-11-install-init-run-cutover.md` (§11.0–§11.7).
Nothing is pushed; PR #1 untouched.

> **Deferred post-merge cutover (DESIGN §11, sub-phase 5.6 part B)**: after this PR merges,
> manually decommission the old PoC skill in the external portable-config repo —
> `git rm -r skills/kanban/` in `PersonnalScaper/.claude` (the `personal-scraper` branch),
> clean its `CLAUDE.md` refs, and commit `chore: decommission kanban skill (extracted to KanbanMate)`.
> NOT done automatically: it is a destructive op on a separate repo, outside KanbanMate's history.
