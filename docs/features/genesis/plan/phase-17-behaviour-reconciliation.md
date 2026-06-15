# Phase 17 — Behaviour reconciliation (the long-tail faithfulness pass)

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Source of truth (DESIGN §11): the PoC code is authoritative; the genesis extraction was meant to
> be faithful. This phase closes the **26 confirmed BEHAVIOUR CHANGES** where NEW diverged from PoC
> semantics — distinct from the 44 feature_losses (phases 12–16). For EACH change we either (a) port
> the PoC semantics back (the default), or (b) explicitly document why NEW's behaviour is acceptable
> **only** when it is a genuine consequence of the n8n→polling pivot.
> PoC source of truth (ABSOLUTE OLD root —
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`; the `bin/` shims are a SIBLING
> of the package, at `.../skills/kanban/bin/`). NEW root:
> `/Users/izno/dev/KanbanMate/src/kanbanmate/`.
> Audit: `docs/features/genesis/POC_PARITY_AUDIT.md` "Confirmed BEHAVIOUR CHANGES (review)"
> (26 entries, grouped by slice).

**Goal**: reconcile every confirmed behaviour change so NEW either matches the PoC or carries an
explicit, design-anchored justification for the divergence. Group by area: 17.1 bin agent-helpers ·
17.2 CLI surface · 17.3 GitHub adapter · 17.4 state management · 17.5 runner / transition / dispatch ·
17.6 engine-adapter behaviours (reaper / heartbeat). Each sub-phase aligns a cluster to the PoC and
adds the parity tests proving the alignment.

**Disposition summary (per behaviour change).** "PORT" = restore PoC semantics; "KEEP+DOC" = NEW is
an accepted pivot consequence, documented in code/docstring + an asserting test:

| #   | Area     | Behaviour change                                         | Disposition        | Sub-phase |
| --- | -------- | -------------------------------------------------------- | ------------------ | --------- |
| 1   | bin      | kanban-move refuses `Merge` → refuses any AGENT column   | KEEP+DOC           | 17.1      |
| 2   | bin      | kanban-comment bare positional → requires explicit mode  | PORT               | 17.1      |
| 3   | bin      | move breadcrumb key node-id → issue number               | KEEP+DOC           | 17.1      |
| 4   | bin      | kanban-progress auto-stage → requires `--stage`          | PORT               | 17.1      |
| 5   | cli      | doctor `gh_installed` check dropped                      | KEEP+DOC           | 17.2      |
| 6   | cli      | doctor token over-scope WARNING → hard FAIL              | PORT               | 17.2      |
| 7   | cli      | doctor required-scopes lower-bound → subset upper-bound  | PORT               | 17.2      |
| 8   | cli      | doctor tmux presence-warning → ownership-FAIL            | KEEP+DOC           | 17.2      |
| 9   | cli      | status TSV per-ticket → table + column counts            | PORT               | 17.2      |
| 10  | cli      | cancel non-destructive → destructive teardown            | KEEP+DOC           | 17.2      |
| 11  | cli      | logs full session text + dispatch.jsonl → daemon.jsonl   | KEEP+DOC           | 17.2      |
| 12  | cli      | seed `--project-id` required vs registry auto-resolve    | PORT               | 17.2      |
| 13  | github   | deps gate live GraphQL state → board-snapshot membership | ENHANCE (hybrid)   | 17.3      |
| 14  | github   | comment GraphQL 2-call → REST single + dead GraphQL code | PORT               | 17.3      |
| 15  | github   | transport transient 502/secondary-rate retry dropped     | PORT               | 17.3      |
| 16  | runner   | move rate-limit park-in-Blocked-column + auto-only feed  | KEEP+DOC           | 17.5      |
| 17  | state    | iter_states corrupt-skip stderr line dropped             | PORT               | 17.4      |
| 18  | state    | advance breadcrumb key node-id → issue number            | KEEP+DOC           | 17.4      |
| 19  | state    | bot-move on-disk dedup + bookkeeping flag → in-memory    | PORT (bookkeeping) | 17.4      |
| 20  | state    | per-item column ledger persisted → in-memory baseline    | KEEP+DOC           | 17.4      |
| 21  | state    | end_session status=idle keep-file → release_slot deletes | REMOVE (dead IDLE) | 17.4      |
| 22  | state    | purge_ticket exhaustive → release_slot partial           | PORT (part)        | 17.4      |
| 23  | dispatch | decide 9-verdict set → 5 ActionKind                      | KEEP+DOC           | 17.5      |
| 24  | dispatch | per-transition permission_mode → static profile pin      | WIRE (per-column)  | 17.5      |
| 25  | adapters | heartbeat hook absolute path → bare PATH command         | PORT               | 17.6      |
| 26  | adapters | reaper dead-session (tmux gone) trigger dropped          | PORT               | 17.6      |

**Net** (after the 2026-06-05 operator decisions on the keeps): **10 KEEP+DOC**
(1, 3, 5, 8, 10, 11, 16, 18, 20, 23) · **16 active changes** — PORT (2, 4, 6, 7, 9, 12, 14, 15, 17,
**19**, 22-part, 25, 26) · ENHANCE-hybrid (**13**) · WIRE-per-column (**24**) · REMOVE-dead-code
(**21**). Every KEEP gets an explicit code/docstring justification AND an asserting test so the
divergence is intentional, not silent. #3 and #18 are the SAME issue-number breadcrumb keying already
mandated by 8.1.d (DESIGN §8.1.d invariant) — KEEP+DOC here only ratifies it.

> **Operator decisions (2026-06-05)** — four keeps were upgraded to active work:
>
> - **#24 → WIRE per-column.** Wire `columns.yml`'s `permission_profile` as the per-column DEFAULT
>   (no longer a dead/advertised field); the phase-12 **per-transition** `profile`/`permission_mode`
>   (`transitions.yml`) takes PRECEDENCE. No single global profile remains. (PoC intent: permissions
>   resolved by context, not one global.) See 17.5 #24.
> - **#13 → ENHANCE (hybrid).** Best-of-both: `core/dependency_gate` stays PURE and returns a
>   **tri-state** per dep (MET in Done/Merge · UNMET on-board-not-done · UNKNOWN absent-from-board);
>   `app/tick` resolves UNKNOWN via a LIVE `issue_state` GraphQL fallback (16.6) — so a closed-but-
>   off-board dep is satisfied (PoC behaviour) WITHOUT the per-tick N queries of the common case
>   (snapshot stays primary). Nothing sacrificed. See 17.3 #13 + phase 16.6.
> - **#19 → PORT (bookkeeping).** Keep the in-memory antiloop (speed) BUT restore the PoC
>   `bookkeeping` flag so a **rollback** move (restored in phase 12) is tagged and bypasses the dedup
>   net (a guarded rollback must not be re-deduped/re-triggered). See 17.4 #19.
> - **#21 → REMOVE.** Delete the dead `TicketStatus.IDLE` enum member outright (vestigial post-pivot).
>   See 17.4 #21.
>
> **⚠️ #21 RE-SCOPED → KEEP+DOC (2026-06-08, operator-approved).** The 2026-06-05 REMOVE decision
> predates phase **15.2** (2026-06-07), which made `TicketStatus.IDLE` **load-bearing**: the reaper
> writes `status=IDLE` BEFORE teardown (`app/reaper.py:174`) so a fail-soft `purge_ticket` failure
> cannot leave a fresh-heartbeat RUNNING zombie (a high-sev defect caught by adversarial verification;
> it is NEW's port of the PoC `_move_to_blocked` "write a terminal non-RUNNING status before releasing"
> ordering). `IDLE` is the only non-RUNNING terminal status, so deletion would either revert that fix
> (re-introducing the zombie) or force a new status member. **Disposition for 17.4 #21 is now KEEP+DOC**:
> do NOT delete `IDLE`; document on the enum member + `release_slot` that it became load-bearing in 15.2
> (the reaper's terminal marker), and add an asserting test that the reaper sets `status=IDLE` before
> teardown. The original REMOVE bullet below is superseded by this note.

---

## Gate

Phases 1–16 complete (PoC parity port + the 44 feature_loss restorations). Branch `feat/genesis`;
`make check` green at start. `.mypy_cache` cleared before the phase gate (mypy strict). Re-sync
confirmed (DESIGN §11): the PoC tree at `.claude/skills/kanban/` is present and read for every
divergence below; each cited PoC `file:line` was re-opened against the live OLD root, not the audit
snapshot, before porting.

---

### 17.1 — Agent-helper parity (kanban-move / kanban-comment / kanban-progress)

> **The cluster.** Four bin-shim behaviour changes (audit "AGENT HELPERS"). Two are genuine PORTs
> (the CLI contract narrowed without cause), two are KEEP+DOC (deliberate, design-anchored).

**Layer**: `bin/` leaves (entrypoints; may import `app`/`core`/`adapters`).
**Files**: `src/kanbanmate/bin/kanban_comment.py`, `src/kanbanmate/bin/kanban_progress.py`,
`src/kanbanmate/bin/kanban_move.py`, `tests/bin/test_kanban_comment.py`,
`tests/bin/test_kanban_progress.py`, `tests/bin/test_kanban_move.py`.

- [ ] **#2 — kanban-comment: restore the bare-positional free-form default (PORT).**
      PoC `bin/kanban-comment:15-34` (+ `cli/agent_helpers.py:47-49`) accepted
      `kanban-comment <issue> <msg>` and posted a plain free-form comment with NO mode flag. NEW
      `bin/kanban_comment.py:130-188` REQUIRES `--append` or `--sticky <STEP>` and exits 2 with
      "choose a mode" on the bare positional form — a backward-incompatible contract break the agents
      (and any PoC-era muscle memory) hit. **Change**: make `--append` the IMPLICIT default when a
      positional message is given and neither mode flag is present, i.e. `kanban-comment <issue>
<msg>` ≡ `kanban-comment <issue> --append <msg>` (free-form `client.comment`). Keep `--sticky
<STEP>` as the NEW two-zone capability. Preserve fail-clean exit codes (2 usage / 1 other).
      Document in the module docstring that bare-positional defaults to free-form for PoC parity.
- [ ] **#4 — kanban-progress: restore auto stage-resolution (PORT, adapted to NEW's store).**
      PoC `bin/kanban-progress:26-65` auto-resolved the CURRENT stage from the persisted per-item
      column (`get_item_column`, falling back to the state column); the agent never passed a stage.
      NEW `bin/kanban_progress.py` (append_to_stage:75-94) REQUIRES `--stage <step-key>`, shifting
      stage resolution from the engine to the caller. **Change**: when `--stage` is omitted, resolve
      the stage from the persisted `TicketState.stage` (the launch column 8.1.d now records on the
      ticket — NEW's single-source replacement for OLD's `columns/` marker). Keep `--stage` as an
      explicit override. Only error when neither `--stage` nor a persisted stage exists. The NEW
      default no-flag free-form timestamped-comment mode is an additive extension — keep it, but it
      must not shadow the auto-stage path when a sticky stage is resolvable. Cite 8.1.d in the
      docstring as the stage source (NOT OLD's `get_item_column`).
- [ ] **#1 — kanban-move HUMAN_ONLY refusal: keep AGENT-column anti-loop guard (KEEP+DOC).**
      PoC `cli/agent_helpers.py:38,68-72` (+ `bin/kanban-move:44-50`) refused moving into the
      human-only `Merge` column (`HUMAN_ONLY_COLUMNS={'Merge'}`) as the primary merge-authorization
      control. NEW `bin/kanban_move.py:146-156` refuses moving into ANY AGENT-class column (read from
      `columns.yml` via `ColumnClass.AGENT`), justified as an anti-loop guard. **KEEP**: in NEW `Merge`
      is modelled INERT (DESIGN §9 board table: "Merge | inert (human only) | bot cannot reach it")
      and there is no merge-profile agent — the merge boundary now rests on Merge-being-inert + branch
      protection + the `gh pr merge` ban, not on this client-side refusal. The AGENT-column refusal is
      the correct anti-self-trigger guard post-pivot. **DOC**: add a module-docstring paragraph stating
      the security boundary moved from "refuse Merge" to "Merge is inert + GitHub protection", so an
      operator carrying the PoC mental model is not surprised. Add a test asserting a move into the
      INERT `Merge` column is ALLOWED (passes the AGENT-only guard) and a move into an AGENT column is
      REFUSED.
- [ ] **#3 — move breadcrumb keyed by issue number: keep (KEEP+DOC, ratifies 8.1.d).**
      PoC `bin/kanban-move:76-82` keyed the advance breadcrumb by the CONTENT NODE ID. NEW
      `bin/kanban_move.py` keys it by the ISSUE NUMBER — the deliberate 8.1.d invariant (DESIGN
      §8.1.d: writer and readers share the issue key). The no-dedup / bug-#2 note is already preserved.
      **KEEP**: functionally equivalent ✅/⚠️ split, only the key changed; no capability lost. **DOC**:
      ensure the docstring cross-references DESIGN §8.1.d as the source of the key choice (already true
      for the writer; verify the move helper repeats it). No code change beyond a docstring confirm if
      the cross-reference is already present.
- [ ] Tests: `kanban-comment <issue> <msg>` (no flag) posts a free-form comment (default `--append`);
      `--sticky` still routes to the two-zone path; `kanban-progress` with no `--stage` resolves the
      stage from `TicketState.stage` and appends; with no persisted stage AND no flag it errors;
      `kanban-move` allows Merge (inert) and refuses an AGENT column; the move breadcrumb is written
      by issue number.
- [ ] Verify: `make check` green.

```bash
git commit -m "fix(genesis): agent-helper CLI parity (kanban-comment default free-form, kanban-progress auto-stage)"
```

---

### 17.2 — CLI-surface parity (doctor checks · status · cancel · logs · seed)

> **The cluster.** Eight CLI behaviour changes (audit "CLI command surface"). Three doctor checks
> tightened or dropped; status/logs reshaped by the polling model; cancel deliberately destructive;
> seed lost the registry handoff.

**Layer**: `cli/` (entrypoints).
**Files**: `src/kanbanmate/cli/doctor.py`, `src/kanbanmate/cli/status.py`,
`src/kanbanmate/cli/cancel.py`, `src/kanbanmate/cli/logs.py`, `src/kanbanmate/cli/seed.py`,
`src/kanbanmate/cli/app.py` (seed flag), `tests/cli/test_doctor.py`, `tests/cli/test_status.py`,
`tests/cli/test_cancel.py`, `tests/cli/test_logs.py`, `tests/cli/test_seed.py`.

- [ ] **#6 — doctor over-scoped token: downgrade hard-FAIL to WARNING (PORT).**
      PoC `cli/plan_doctor.py:93-97` modelled `delete_repo`/`admin:org`/`admin:enterprise`/`site_admin`
      as a non-blocking WARNING (over-scoped allowed but flagged). NEW `cli/doctor.py:253-265` calls
      `validate_scopes` which RAISES `TokenScopeError` (hard FAIL, exit 1) for anything outside
      `{project, repo}`. **Change**: keep `{project, repo}` as the REQUIRED floor (see #7), but report
      EXTRA dangerous scopes as a doctor WARNING line, not an error — restore the PoC's
      "over-scoped → warn, don't block" disposition (DESIGN least-privilege is advisory here, not a
      gate). Split the scope check so "missing required scope" stays a FAIL while "extra/over-scoped"
      becomes a WARNING.
- [ ] **#7 — doctor scopes: enforce the required-floor (lower bound), not a subset upper-bound (PORT).**
      PoC `cli/plan_doctor.py:40-45,86-91` validated that the REQUIRED scopes `{project, repo}` are
      PRESENT (subset-must-contain). NEW `cli/doctor.py:253-258` inverted this to validate scopes are
      a SUBSET of `{project, repo}` (upper bound) — so a minimal fine-grained PAT with no classic
      scopes PASSES NEW but would FAIL the PoC required-floor. **Change**: restore the lower-bound
      semantics — required `{project, repo}` must be present; report missing-required as a FAIL.
      Preserve the fine-grained-PAT escape hatch (empty classic scopes → "likely fine-grained PAT,
      advisory") but as an explicit advisory branch, not a silent pass. With #6 this becomes: FAIL on
      missing-required, WARN on over-scoped, advisory on empty/fine-grained — three distinct outcomes.
- [ ] **#9 — status: restore the per-ticket column + session rows (PORT, snapshot-adapted).**
      PoC `cli/runners.py:87-96` (+ `reports.build_status_report:26-39`) printed ONE row per persisted
      ticket: `#<issue>\t<column>\t<status>\t<session_uuid>`. NEW `cli/status.py:123-167` renders
      per-column COUNTS (from the live snapshot) + a separate "Running agents" section. **Change**:
      keep the human two-section table (it is richer), but RESTORE the per-ticket column+session detail
      the PoC exposed: in the running-agents section, render each running ticket's CURRENT column
      (resolved from the snapshot by issue number) alongside its `session=`/`status=` — recovering the
      `#issue column status session_uuid` tuple the PoC gave per ticket. This is a data-model
      restoration, not a format rollback (the polling model legitimately replaces the TSV). Document
      that the TSV form is intentionally dropped (table is the artifact) but the column+uuid PER TICKET
      is restored.
- [ ] **#12 — seed: auto-resolve project id from the registry (PORT).**
      PoC `cli/runners.py:244-258` auto-resolved the project node id + status field + Backlog option
      from `projects.json` by matching `--repo`, erroring "run kanban init first" if absent. NEW
      `cli/app.py:228-255` REQUIRES `--project-id` on the command line and never consults the registry,
      breaking the init→seed handoff. **Change**: make `--project-id` OPTIONAL; when omitted, resolve
      the project id (and status-field node id + option map) from `projects.json` by `--repo`
      (reuse the existing `_load_registry`/`ProjectEntry` from `cli/init.py`), erroring with
      "no project registered for <repo> — run `kanban init` first" when absent. Keep `--project-id`
      as an explicit override.
- [ ] **#5 — doctor `gh_installed` check: keep dropped (KEEP+DOC).**
      PoC `cli/plan_doctor.py:35-38` checked the `gh` CLI is installed. NEW does not shell out to `gh`
      at all (it uses the urllib token-scope fetch via `adapters/github/token`). **KEEP**: the check is
      moot — NEW has no `gh`-CLI dependency to validate. **DOC**: add a one-line doctor comment (or a
      skipped/advisory note in `run_doctor`) recording that "gh CLI is not a runtime dependency in the
      polling engine — check intentionally removed", so its absence reads as deliberate, not an
      omission. No live check restored.
- [ ] **#8 — doctor tmux: keep the ownership FAIL (KEEP+DOC).**
      PoC `cli/plan_doctor.py:110-113` warned on tmux presence/usability. NEW `cli/doctor.py:316-358`
      stats `/tmp/tmux-<uid>/default` and FAILS unless the socket is owned by the current euid.
      **KEEP**: the ownership FAIL is STRONGER and directly enforces DESIGN §10 (non-root
      socket-ownership; `bypassPermissions` refuses under root). **DOC**: ensure the check docstring
      cites DESIGN §10 as the rationale for the presence→ownership / warning→error tightening, so the
      stricter semantics are intentional. Add a test asserting a foreign-owned socket FAILS.
- [ ] **#10 — cancel: keep the destructive teardown (KEEP+DOC, anchored in 8.2).**
      PoC `cli/plan_cancel.py:24-34` was deliberately NON-destructive (kill tmux + mark `cancelled`,
      NEVER remove the worktree — "worktree remove --force is banned, §4.5"). NEW `cli/cancel.py:52-67`
      reuses the app-layer `TeardownAction`, which kills the session, REMOVES the worktree (`--force`),
      releases the slot, closes the PR (keeps the remote branch) and recaps. **KEEP**: this is the
      operator-decided Cancel semantics baked into phase 8.2 (DESIGN §8.2) — `kanban cancel` is
      intentionally byte-for-byte the SAME teardown the Cancel column runs, and resumability is
      preserved via the **remote branch** (kept) + "move the card to Backlog" re-arm, not via a
      retained local worktree. **DOC**: the `cli/cancel.py` docstring already states the destructive
      semantics; ADD the explicit divergence note ("PoC `plan_cancel` was non-destructive — NEW unifies
      manual + Cancel-column teardown per DESIGN §8.2; resumability moves to the kept remote branch +
      Backlog re-arm"). Add a test asserting `kanban cancel` removes the worktree AND closes the PR
      while keeping the remote branch (parity with 8.2.b).
- [ ] **#11 — logs: keep the daemon-JSONL model (KEEP+DOC).**
      PoC `cli/runners.py:113-125` printed the full per-ticket session-log TEXT + `dispatch.jsonl`
      transitions (`<from> -> <to> (<uuid>)`). NEW `cli/logs.py` reads the structured daemon JSONL
      (`<root>/log/daemon.jsonl`), filters by issue, tails N (`--tail`, default 50) and surfaces the
      per-ticket log PATH but not its body. **KEEP**: the `dispatch.jsonl` history is a webhook-era
      artifact with no analogue in the polling model (no per-dispatch webhook log) — genuinely
      pivot-mooted. **DOC**: ensure the `logs` docstring records that (a) `dispatch.jsonl` is replaced
      by `daemon.jsonl` (polling has no dispatch log), and (b) the session-log BODY is intentionally
      surfaced by PATH (the operator `cat`s / `tail`s it themselves) to avoid dumping unbounded text.
      Add an asserting test for the issue filter + `--tail`.
- [ ] Tests: doctor FAILs on missing-required scope, WARNs on over-scoped, advisory on fine-grained;
      status shows per-running-ticket column + session uuid; seed resolves the project id from the
      registry when `--project-id` omitted and errors when unregistered; cancel removes worktree +
      closes PR + keeps branch; logs filters by issue + tails; the tmux ownership FAIL fires on a
      foreign socket; the `gh_installed`-removal note is present.
- [ ] Verify: `make check` green.

```bash
git commit -m "fix(genesis): CLI-surface parity (doctor scope floor + over-scope warn, status per-ticket detail, seed registry auto-resolve)"
```

---

### 17.3 — GitHub-adapter parity (transport retry · GraphQL comment dead-code · dependency gate)

> **The cluster.** Three GitHub behaviour changes (audit "GitHub adapter"). The transport lost its
> transient-error resilience (PORT); the comment path swapped GraphQL→REST leaving dead code (PORT —
> remove the residue); the dependency gate moved to the board snapshot (KEEP+DOC — pivot consequence).

**Layer**: `adapters/github/` + `core/dependency_gate.py` + `app/tick.py` (the #13 hybrid fallback).
**Files**: `src/kanbanmate/adapters/github/client.py`,
`src/kanbanmate/adapters/github/_queries.py`, `src/kanbanmate/adapters/github/_parsers.py`,
`src/kanbanmate/core/dependency_gate.py`, `src/kanbanmate/app/tick.py`,
`tests/adapters/github/test_client.py`, `tests/core/test_dependency_gate.py`,
`tests/app/test_tick.py`. (The GraphQL `issue_state` method + parser this #13 fallback calls is
restored in **phase 16.6** — a hard prerequisite; 16 runs before 17.)

- [ ] **#15 — transport: restore transient 502 / secondary-rate-limit retry+backoff (PORT).**
      PoC `github/client.py::_urlopen_json:63-96` retried up to 3 attempts with `0.5*(n+1)` backoff on
      HTTP 502 OR a 403 "secondary rate limit" body, before raising — keeping the daemon's hot poll
      loop resilient to transient GitHub blips. NEW `adapters/github/client.py:91-131` (`_request`)
      raises `GitHubHTTPError` IMMEDIATELY on status>=400 with NO retry, so a single transient 502
      fails the whole tick. **Change**: wrap the `_request` send/read in a bounded retry loop — on
      `resp.status == 502`, or `403` whose decoded body matches "secondary rate limit", sleep
      `0.5*(attempt+1)` and retry up to 3 attempts; on the final attempt (or any other status>=400)
      raise `GitHubHTTPError` with the decoded body (the decoded-body surfacing is already correct —
      preserve it). The connect+read timeouts (the mandated network-safety, CLAUDE.md) stay on EVERY
      attempt. Keep the retry inside the transport so all REST callers inherit it. Use a monotonic
      sleep guarded so the total bounded backoff (~3s worst case) never approaches the tick budget.
- [ ] **#14 — comment: remove the dead GraphQL builders/parsers (PORT — clean the residue).**
      PoC `github/client.py:174-180` posted a comment via 2 GraphQL calls (`issue_node_id` then
      `add_comment`). NEW `client.py:328-342` posts via a SINGLE REST `POST .../issues/{n}/comments` —
      functionally equivalent and simpler (KEEP the REST path). BUT the GraphQL builders/parsers it
      replaced were PORTED yet are DEAD CODE never called in `src/`: `add_comment` + `issue_node_id`
      (`_queries.py`) and `parse_issue_node_id` (`_parsers.py`). **Change**: DELETE the three dead
      symbols (and any now-orphaned import) so no reader assumes a live GraphQL comment path; keep the
      REST `comment`. Residual-import grep them in `src/` AND `tests/` after deletion (zero matches).
      Document on `comment` that it is REST-by-design (GraphQL comment path intentionally dropped).
- [ ] **#13 — dependency gate: HYBRID snapshot-first + live `issue_state` fallback (ENHANCE — operator
      decision 2026-06-05: "best of both worlds, sacrifice nothing").**
      PoC `github/client.py:182-189` (+ `_queries.issue_state` + `parse_issue_closed`) queried each
      `Depends on #N` issue's LIVE open/closed state via GraphQL and returned True iff ALL closed. NEW
      `core/dependency_gate.py:46-91` resolves deps against the BOARD SNAPSHOT's column membership (met
      iff the dep's card is in `Done`/`Merge`) — fast + PURE, but a dep CLOSED yet NOT on the board (e.g.
      closed-as-not-planned, or a card moved off the board) is wrongly treated UNMET. **The decision is
      to keep BOTH strengths**: the snapshot stays the primary, zero-I/O common path; a live GraphQL
      `issue_state` query is the fallback ONLY for the rare off-board dep — so nothing is sacrificed
      (no per-tick N queries, AND the closed-but-off-board dep is satisfied like the PoC).
      **Change (two layers, layering preserved):**
  - **`core/dependency_gate.py` stays PURE → return a TRI-STATE per dep.** Refactor `evaluate` so each
    `Depends on #N` resolves to `MET` (dep's card in `Done`/`Merge`), `UNMET` (card on board but not
    Done), or `UNKNOWN` (issue NOT present on the board snapshot). The pure function returns the
    aggregate gate verdict PLUS the list of `UNKNOWN` dep issue-numbers (it does NOT do I/O — it only
    reports which deps the snapshot cannot decide). Keep the conservative default (no deps → met).
    English docstrings; a `DependencyVerdict` value object (frozen) carrying `met: bool` +
    `unresolved: tuple[int, ...]`.
  - **`app/tick.py` resolves `UNKNOWN` via the LIVE fallback.** Before treating a launch as gated, if
    the pure verdict reports `unresolved` deps, the tick calls `deps.board.issue_state(n)` (the GraphQL
    `issue_state` restored in **phase 16.6**) for EACH unresolved dep: a CLOSED issue → that dep is MET;
    OPEN → UNMET. Re-aggregate: the gate passes iff the snapshot-MET deps AND the fallback-resolved
    deps are all satisfied. Fail-soft + bounded: a throwing/slow `issue_state` leaves the dep UNMET
    (conservative — never launch on an undecidable dep), and the fallback only fires for `unresolved`
    deps (zero queries in the common all-on-board case — the perf property is preserved). The
    connect+read timeouts (CLAUDE.md) apply to every `issue_state` call.
  - **DOC**: `evaluate`'s docstring records the tri-state contract; `tick`'s gate site documents the
    snapshot-primary / GraphQL-fallback split + the fail-soft "undecidable → UNMET" rule. Note the ONE
    residual edge that even the fallback cannot fix without a board card: an issue that is OPEN but whose
    work is genuinely done out-of-band is still UNMET (correct — represent it on the board).
- [ ] Tests: a 502-then-200 sequence retries and succeeds; a persistent 502 raises after 3 attempts;
      a 403 "secondary rate limit" body retries, a 403 with another body does not; the dead GraphQL
      comment symbols are gone (residual grep). **Dependency gate (hybrid #13)**: the PURE `evaluate`
      returns `MET` for a dep in Done, `UNMET` for a dep on-board-not-Done, and `UNKNOWN` (in
      `unresolved`) for a dep absent from the snapshot — with NO I/O; the `app/tick` fallback queries
      `issue_state` ONLY for `unresolved` deps and treats CLOSED→met / OPEN→unmet; a dep fully on the
      board triggers ZERO `issue_state` calls (perf property); a closed-but-off-board dep PASSES the
      gate via the fallback (the PoC parity win); a throwing `issue_state` leaves the dep UNMET
      (fail-soft, never launches on an undecidable dep).
- [ ] Verify: `make check` green. Residual-import grep:
      `rg --type py "add_comment|issue_node_id|parse_issue_node_id" src tests` → zero matches.

```bash
git commit -m "fix(genesis): github transport transient-retry + drop dead GraphQL comment path; hybrid dependency gate (snapshot + issue_state fallback)"
```

---

### 17.4 — State-management parity (corrupt-skip diagnostic · purge · documented in-memory divergences)

> **The cluster.** Six state behaviour changes (audit "STATE management"). #18/#20 are accepted pivot
> consequences (the on-disk dir-per-concern ledgers collapsed into the in-memory diff baseline — DESIGN
> §6 sanctions this) and get KEEP+DOC; the other four are active work: #17 PORT (restore the corrupt-
> file stderr diagnostic), #22 PORT-part (teardown rate-limit reset), and — per the 2026-06-05 operator
> decisions — **#19 PORT** (restore the rollback-aware `bookkeeping` flag) and **#21 REMOVE** (delete the
> dead `TicketStatus.IDLE` enum member).

**Layer**: `adapters/store/fs_store.py` · `core/antiloop.py` · `app/tick.py`.
**Files**: `src/kanbanmate/adapters/store/fs_store.py`, `src/kanbanmate/core/antiloop.py`,
`src/kanbanmate/app/tick.py`, `tests/adapters/test_fs_store.py`, `tests/core/test_antiloop.py`,
`tests/app/test_tick.py`.

- [ ] **#17 — list_running: restore the corrupt-file stderr diagnostic (PORT).**
      PoC `state.py:333-387` (`iter_states`) skipped a corrupt `state/<n>.json` with a NAMED stderr
      line (`kanban: skipping corrupt state file ...`) so a poison file could not abort the reaper
      sweep AND the operator got a diagnostic breadcrumb. NEW `fs_store.py:175-202` (`list_running`)
      preserves the corrupt-file TOLERANCE but skips SILENTLY — the operator loses the breadcrumb.
      **Change**: on a `JSONDecodeError`/load error inside `load`/`list_running`, emit one stderr line
      naming the offending file (`kanban: skipping corrupt state file <path>: <err>`) before
      continuing — restore the PoC diagnostic. Keep the skip-don't-raise behaviour. Same one-line
      diagnostic for the single-`load` corrupt path.
- [ ] **#22 — teardown purge: clear stale in-memory rate-limit history on teardown (PORT — the
      surviving-target gap).** PoC `purge_ticket` (`state.py:427-479`) was the SINGLE exhaustive
      idempotent teardown removing every dir-per-concern marker incl. `moves/item_<item>.json` — which
      ZEROED the move rate-limit history for the ticket. NEW `fs_store.py:135-156` (`release_slot`)
      unlinks only `state/`, `slots/`, `advances/`; the move rate-limit history now lives in volatile
      `PersistedState.antiloop.move_times` (in-memory) which `release_slot` cannot reach — so after a
      cancel/teardown a ticket's accumulated rate-limit timestamps PERSIST in memory until the next
      daemon restart. **Change**: add an in-memory `antiloop` reset for the torn-down item to the
      teardown path (`TeardownAction`/`ResetAction` thread the antiloop reset through `tick` the same
      way the reaper's `record_move` is threaded back, OR add an `antiloop.forget(item_id)` helper in
      `core/antiloop.py` called when a ticket is purged). The dirs OLD purged that no longer exist
      (`columns/`, `botmoves/`, `retries/`, `processed/`, `inflight/`) need no analogue — confirm in a
      docstring that those targets are pivot-erased. The `queue/ticket-<issue>` purge is restored by
      the QUEUE feature_loss phase (cross-reference it; do not duplicate here).
- [ ] **#18 — advance breadcrumb keyed by issue number: keep (KEEP+DOC, ratifies 8.1.d).**
      PoC `state.py:175-203` keyed the breadcrumb by content-node-id (`_advance_path` via
      `item.translate`). NEW `fs_store.py` keys by issue number (the 8.1.d invariant, DESIGN §8.1.d);
      writer/readers are consistent and NEW adds parse-error tolerance the PoC lacked. **KEEP**:
      internally sound, load-bearing key change is documented. **DOC**: confirm the three breadcrumb
      methods' docstrings state the issue-number key + cite §8.1.d (already required by 8.1.d — verify).
- [ ] **#19 — bot-move dedup: keep in-memory + RESTORE the `bookkeeping` flag for rollback-awareness
      (PORT — operator decision 2026-06-05: "best of both worlds, be able to rollback").**
      PoC `state.py:117-149` persisted `botmoves/<item>__<option>` markers (`_BOT_MOVE_TTL=600s`) with
      a `bookkeeping` audit flag tagging anti-double-session-revert / **rollback** moves. NEW replaced
      this with the PURE in-memory `core/antiloop.py` (`recent_targets`, `recent_ttl=600.0`) and DROPPED
      the flag on the rationale "NEW has no rollback path." **That rationale no longer holds**: the
      guarded ROLLBACK verdict is restored in phase 12 (an un-whitelisted / `on_fail:rollback` move
      bounces the card BACK to `from_col`). A rollback is a daemon-issued board move that MUST NOT be
      deduped/re-triggered as a fresh bot-move, and MUST NOT itself be blocked by the recent-target net.
      **Change (keep the in-memory speed, restore the distinction):**
  - Add a `bookkeeping: bool = False` parameter to `core/antiloop.record_move` (and tag the entry). A
    `bookkeeping=True` move (a rollback bounce, or an anti-double-session revert) is recorded for the
    idempotency baseline but EXCLUDED from the rate-limit counter feed (#16: only genuine auto-loop
    moves count), and a subsequent identical-target check treats a bookkeeping entry as "already
    handled — do not re-trigger" rather than "recently launched — block".
  - `RollbackAction` (phase 12.5) calls `record_move(..., bookkeeping=True)` so the bounce is tagged.
    Cross-reference phase 12: the ROLLBACK diff-baseline advance (12.8) is the PRIMARY no-re-trigger
    mechanism; the `bookkeeping` tag is the SECONDARY guard ensuring the antiloop net does not fight a
    legitimate rollback (the PoC's exact reason for the flag).
  - **DOC**: state in `antiloop.py` that (1) the net is in-memory and a daemon restart wipes it (the
    diff baseline re-sync is the intended backstop — KEPT from NEW), and (2) the `bookkeeping` flag is
    RESTORED to make rollback moves first-class (no longer dropped). Tests: a `bookkeeping=True` move
    does NOT feed the rate-limit counter; a rollback bounce tagged bookkeeping is not re-triggered next
    tick; the 600s TTL holds; a restart wipes the net (documented, asserted).
- [ ] **#20 — per-item column ledger → in-memory diff baseline (KEEP+DOC).**
      PoC `state.py:151-173` persisted `columns/<item>` markers across restarts AND seeded at board-add;
      `None` == first contact. NEW `app/tick.py:137` replaces it with `PersistedState.columns_by_item`
      (the in-memory `diff` baseline; an absent item → `from_column=None` → first-contact leniency,
      `diff.py:24-25`). DESIGN §5/§6 sanctions rebuilding from the board on restart. **KEEP**: the
      in-memory baseline is the polling data model. **DOC**: record the accepted semantics shift — the
      first tick post-restart treats every card as first-contact and re-syncs silently (no durable
      seed-at-add), which is the intended "restart + diff recovers downtime moves" behaviour (DESIGN
      §6 line 185). Add a test asserting a post-restart empty baseline re-syncs without spurious launches.
- [ ] **#21 — end_session idle-state → release_slot deletes; REMOVE the dead `TicketStatus.IDLE` enum
      member (operator decision 2026-06-05: "remove the dead code").**
      PoC `state.py:395-425` (`end_session`) set `status='idle'` and KEPT the state file (so the
      anti-double-session guard saw no live session) + released the slot. NEW has no `end_session`;
      `release_slot` (`fs_store.py:135-156`) deletes the state file, and the idle/session-end
      orchestration lives in `bin/kanban_session_end.py` (the 8.1.f finalizer). The
      idempotent-no-op-on-purged-ticket safety is preserved (`release_slot` unlink-if-exists), and the
      `idle` status is vestigial in the polling model (the daemon re-derives liveness from the board
      diff + heartbeat, not a persisted `idle` flag). **Change**: DELETE the `TicketStatus.IDLE` enum
      member outright (confirmed dead post-pivot). First residual-grep it across `src/` AND `tests/`
      (`rg --type py "TicketStatus\.IDLE|\bIDLE\b" src tests`) and excise every reference; if a
      status-rendering or test path still reads it, retarget that path (no live state is `IDLE` in the
      polling model). **DOC**: note in `release_slot`'s docstring that it DELETES rather than idles the
      record (the 8.1.f finalize already ran any ⚠️ before the purge). Tests: release-on-purged-ticket
      is a clean no-op AND a guard test that `TicketStatus` exposes no `IDLE` member (so the dead state
      cannot silently return).
- [ ] Tests: a corrupt `state/<n>.json` is skipped WITH a named stderr line; `release_slot` (teardown)
      resets the item's in-memory rate-limit history (no stale timestamps survive); the 600s antiloop
      TTL + restart-wipes-net; a `bookkeeping=True` move is excluded from the rate-limit counter and a
      rollback bounce is not re-triggered next tick (#19); `TicketStatus` exposes no `IDLE` member
      (#21 guard); the post-restart empty baseline re-syncs cleanly; release-on-purged is a no-op.
- [ ] Verify: `make check` green.

```bash
git commit -m "fix(genesis): restore corrupt-state diagnostic + teardown rate-limit reset + rollback-aware bookkeeping flag; remove dead TicketStatus.IDLE"
```

---

### 17.5 — Runner / transition / dispatch parity (rate-limit backstop · verdict set · permission mode)

> **The cluster.** One runner change + two transition/dispatch-model changes (audit "RUNNER" +
> "TRANSITION/DISPATCH"). #16 (rate-limit backstop) + #23 (reduced verdict set) are KEEP+DOC, each
> with an asserting test, plus the one real tightening on #16 (feed the rate-limit counter from every
> daemon-issued move, not just the reaper's). **#24 is WIRE** (operator decision 2026-06-05): the
> per-column `permission_profile` is wired as the default under the phase-12 per-transition profile —
> no single global profile remains.

**Layer**: `core/antiloop.py` · `core/decide.py` · `core/domain.py` · `app/tick.py` ·
`adapters/perms.py` · `core/columns.py`.
**Files**: `src/kanbanmate/core/antiloop.py`, `src/kanbanmate/app/tick.py`,
`src/kanbanmate/core/decide.py`, `src/kanbanmate/core/domain.py`,
`src/kanbanmate/adapters/perms.py`, `src/kanbanmate/core/columns.py`,
`src/kanbanmate/app/actions.py` (#24 `LaunchAction` profile selection),
`src/kanbanmate/assets/columns.yml.tmpl` (#24 `permission_profile` doc),
`tests/core/test_antiloop.py`, `tests/core/test_decide.py`, `tests/core/test_columns.py`,
`tests/app/test_tick.py`, `tests/app/test_actions.py`.

- [ ] **#16 — move rate-limit backstop: keep comment-not-park + widen the counter feed (KEEP+DOC +
      small PORT).** PoC `runner.py:504-518` parked a runaway item in the Blocked COLUMN (visible board
      move + comment) and counted ONLY auto/bot moves (`move_rate_limit_per_hour`). NEW
      `core/antiloop.py:67-83` keeps a per-ticket rate limit (`rate_limit=10/hour`, PoC default) and
      `decide.py:197-218` downgrades a tripped launch to a `BLOCK` COMMENT, but `tick.py:389` records a
      move into the counter ONLY for the reaper's own move-to-Blocked. **KEEP**: BLOCK-as-comment (not
      a board park) is the correct polling-model behaviour — the daemon already reflects board state via
      the diff, and an autonomous board park would itself feed the diff. **DOC**: record that the
      backstop is DESIGN-documented defense-in-depth (secondary), not the primary idempotence net (the
      diff-against-persisted is primary, DESIGN §6). **SMALL PORT (the real gap)**: the counter is fed
      ONLY by the reaper's move, so a genuine auto-loop of daemon-issued moves is the only thing it can
      ever see — confirm whether NEW issues any OTHER autonomous board move that should feed
      `record_move` (per the in-code TODO at `tick.py:346`: "Any future daemon-issued board move must
      likewise call record_move"). Audit every daemon-issued `move_card` in `app/` and ensure each calls
      `record_move` so the rate-limit backstop is accurate, not just the reaper. Do NOT feed human/agent
      moves (the PoC counted auto/bot moves only — preserve that exclusion). Document the
      "daemon-issued moves only" rule on `record_move`.
- [ ] **#23 — decide verdict set 9→5: keep the reduced ActionKind (KEEP+DOC).**
      PoC `dispatch.py:18-21` had a 9-kind `DecisionKind` (launch/run_script/noop/rollback +
      runner-added skip/queue/block/teardown/reset). NEW `core/domain.py:106-124` keeps
      LAUNCH/TEARDOWN/RESET/BLOCK/NOOP (5). The two GENUINELY-lost verdicts (`rollback`, `run_script`)
      are feature_losses restored in their own phases (cross-reference — NOT re-done here). `skip` and
      `queue` collapsed: `skip` = idempotency/dedup handled in `tick`; `queue` = concurrency-cap handled
      in the app layer via `reserve_slot` (restored by the QUEUE feature_loss phase). **KEEP**: the
      5↔9 mapping is a reorganisation, not a capability loss (once rollback/run_script/queue are
      restored elsewhere). **DOC**: add a comment on `ActionKind` mapping each PoC verdict to its NEW
      home (skip→tick dedup, queue→reserve_slot path, rollback/run_script→cross-referenced phases) so a
      reader can trace the reorganisation. No new ActionKind here. Add a test pinning the documented
      mapping (e.g. an idempotent re-tick produces a NOOP, not a distinct `skip`).
- [ ] **#24 — WIRE per-column permission profile (operator decision 2026-06-05: "câble les permissions
      par colonne, tel que prévu dans le PoC" — option (a) LOCKED, no fallback to removal).** PoC
      `transitions.py:20-22,106-126` set `permission_mode` PER TRANSITION, validated against a 5-value
      allow-set `{default,acceptEdits,auto,dontAsk,plan}` with `bypassPermissions` BANNED. NEW
      `adapters/perms.py:40-53,242-243` pins a mode PER static PROFILE (safe/trusted) and keeps the bypass
      ban — BUT `columns.yml` ADVERTISES a `permission_profile` per column that `core/columns.py:78-89`
      (`load_columns`) does NOT parse, and `LaunchAction` uses one GLOBAL `Deps.profile`, so EVERY agent
      runs under the SAME profile regardless of column (contradicting DESIGN §8/§9). **Decision: WIRE it
      — no single global profile remains.** Two-tier resolution (most specific wins):
  1. **Per-transition `profile` (phase 12, PoC-faithful) takes PRECEDENCE.** Phase 12.5 already carries
     the matched transition's `profile`/`permission_mode` onto `LaunchAction` (from `transitions.yml`).
     A non-empty transition `profile` wins — this IS the PoC model (permission resolved by the (from,to)
     transition).
  2. **Per-column `permission_profile` (this sub-phase) is the DEFAULT** when the matched transition
     leaves `profile == ""`. Parse `permission_profile` in `core/columns.load_columns` (a new optional
     field on the `Column` value object, defaulted), thread it onto the launch `Column`, and have
     `LaunchAction` select `transition.profile or column.permission_profile or <hard error>` — NEVER a
     silent global default. The bypass ban + the validated mode allow-set survive unchanged (the §10
     safety floor is intact; `bypassPermissions` still rejected at load).
  - **DOC**: record the two-tier resolution (transition profile → column default) on `LaunchAction` and
    in the `columns.yml.tmpl` comment for `permission_profile` (it is now LIVE, not advertised-but-
    unwired). The `columns.yml` template and the code MUST agree (no dead field).
  - Tests: a transition carrying an explicit `profile` overrides the column default; a transition with
    `profile == ""` falls back to the launch column's `permission_profile`; a column with NO
    `permission_profile` AND a transition with no profile FAILS LOUD (no silent global); the bypass ban
    still rejects `bypassPermissions`.
- [ ] Tests: every daemon-issued `move_card` feeds `record_move` (the rate-limit counter sees all
      autonomous moves, not just the reaper's); a tripped rate limit yields a BLOCK comment (not a
      board park); the ActionKind mapping (re-tick → NOOP); **per-column profile selection (two-tier)**:
      an explicit transition `profile` overrides the column default, a transition with no profile falls
      back to the launch column's `permission_profile`, and no profile anywhere FAILS LOUD (no silent
      global); the bypass ban still rejects `bypassPermissions`.
- [ ] Verify: `make check` green.

```bash
git commit -m "fix(genesis): rate-limit counter feeds all daemon moves + wire per-column permission profile; document reduced verdict set"
```

---

### 17.6 — Engine-adapter behaviours (reaper dead-session trigger · heartbeat hook path)

> **The cluster.** Two engine-adapter behaviour changes (audit "engine adapters"). Both are real
> PORTs: the reaper lost a block trigger, and the heartbeat hook bakes a bare PATH command that fails
> if the shim is not on PATH.

**Layer**: `app/tick.py` (reaper) · `adapters/perms.py` (heartbeat hook).
**Files**: `src/kanbanmate/app/tick.py`, `src/kanbanmate/adapters/perms.py`,
`tests/app/test_tick.py`, `tests/adapters/test_perms.py`.

- [ ] **#26 — reaper: restore the dead-session (tmux gone) block trigger (PORT).**
      PoC `engine/reaper.py:49-53` had TWO block triggers: (a) the tmux session is GONE, OR (b) the
      heartbeat is older than the TTL. NEW `app/tick.py:362-363` (`_reap_stale_agents`) checks ONLY
      `(now - state.heartbeat) <= heartbeat_ttl` — it never calls `sessions.is_alive()`. A crashed
      agent whose LAST heartbeat is recent (< TTL, default 1800s) but whose tmux session DIED is NOT
      reaped until the TTL elapses, whereas the PoC reaped it immediately. **Change**: add the
      session-liveness trigger to the reaper loop — for each running `state`, reap when the heartbeat is
      stale OR `not deps.sessions.is_alive(state.issue_number)` (a session that died without updating
      its heartbeat). Keep the existing block→teardown→move-to-Blocked→⛔-flip sequence unchanged; only
      the GATE condition widens. The `is_alive` probe is the same check `sessions.is_alive` already
      backs (used by teardown's guarded kill), so no new adapter surface. Guard the probe so a
      throwing/slow `is_alive` cannot freeze the sweep (it already runs other steps under a watchdog —
      keep the probe cheap and fail-closed: an errored probe leaves the heartbeat-TTL path intact).
- [ ] **#25 — heartbeat hook: bake the resolved shim path, not a bare PATH command (PORT).**
      PoC `engine/perms.py:293-313` baked the ABSOLUTE `shlex.quote`'d path to `bin/kanban-heartbeat`
      (resolved from the skill root) into the worktree `PostToolUse` hook. NEW `adapters/perms.py:253-271`
      bakes the bare command string `kanban-heartbeat <issue>`, relying on the shim being on the
      agent's PATH — which silently no-ops the heartbeat (and so defeats the reaper's freshness signal)
      if the install did not put `kanban-heartbeat` on PATH. **Change**: resolve the heartbeat shim's
      absolute path at hook-materialisation time (mirror how the PoC resolved it from the package /
      install root — e.g. `shutil.which("kanban-heartbeat")` with a fallback to the known install
      location, or the package-relative `bin/` path), `shlex.quote` it, and bake the absolute path +
      issue arg into the hook command. Keep it fail-soft (a non-resolvable shim degrades to the bare
      command with a logged warning, not a crash). This makes the heartbeat robust to a PATH-less agent
      environment, matching the PoC.
- [ ] Tests: the reaper reaps a running ticket whose `is_alive` returns False even with a FRESH
      heartbeat (assert the move-to-Blocked + ⛔ flip fire); a fresh heartbeat WITH a live session is
      NOT reaped; an `is_alive` that raises leaves the heartbeat-TTL path working (no sweep crash); the
      materialised heartbeat hook command contains the resolved absolute shim path (`shlex.quote`'d),
      not a bare `kanban-heartbeat`.
- [ ] Verify: `make check` green.

```bash
git commit -m "fix(genesis): reaper detects dead tmux sessions + heartbeat hook bakes resolved shim path"
```

---

### Phase 17 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`). **Clear `.mypy_cache` first** (`rm -rf
.mypy_cache`) so the strict run is not masked by a stale cache.
2. `make test` — all pass (check the summary line; any ERROR = collection crash → fix imports first).
3. `make check` — clean (lint + test + module-size guards; soft warning ~800 LOC, hard ceiling 1000).
   Confirm no touched module crossed the cap (the GitHub client at ~689 LOC + the transport retry is
   the closest — verify it stays under 800; split a helper out if the retry pushes it over).
4. Residual-import / dead-code grep (type-filtered, MANDATORY per CLAUDE.md search-safety):
   - `rg --type py "add_comment|issue_node_id|parse_issue_node_id" src tests` → **zero matches**
     (17.3 dead GraphQL comment path removed).
   - `rg --type py "permission_profile" src tests` → matches ONLY the wired parse path (17.5 #24
     option a) OR zero matches if the template field was removed (option b) — never an
     advertised-but-unwired field.
5. Behaviour-parity check — every PORT is exercised and every KEEP is asserted-as-intentional:
   - bin: `kanban-comment <issue> <msg>` defaults free-form; `kanban-progress` auto-resolves the stage;
     `kanban-move` allows inert `Merge` + refuses AGENT columns.
   - cli: doctor FAILs on missing-required scope / WARNs on over-scope / advisory on fine-grained;
     status shows per-running-ticket column + uuid; seed auto-resolves the project id from the registry.
   - github: a transient 502 retries then succeeds; the dependency-gate snapshot semantics are pinned.
   - state: a corrupt state file is skipped WITH a named stderr line; teardown resets in-memory
     rate-limit history.
   - runner/dispatch: every daemon-issued move feeds `record_move`; the bypass ban holds.
   - adapters: the reaper reaps a dead-session-but-fresh-heartbeat ticket; the heartbeat hook bakes the
     resolved absolute shim path.
6. Network-safety check (CLAUDE.md MANDATORY): the transport retry loop keeps the connect+read timeouts
   on EVERY attempt and the total backoff is bounded (~3s worst case) — never an unbounded retry.
7. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 17 gate — behaviour reconciliation (26 confirmed divergences resolved)"
```
