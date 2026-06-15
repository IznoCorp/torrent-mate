# DESIGN restore-delta — undo the §8 over-simplification, record the PoC model as the design

> **Status**: ready-to-apply DESIGN edits. A human applies these against
> `docs/features/genesis/DESIGN.md`. Nothing here ports code — it restores the _design_
> so the §8/§9 sections describe the PoC's real model again (DESIGN §11: the PoC code is the
> source of truth; the extraction was meant to be faithful).
>
> **Provenance of the drift.** Commits **a9aa5bf** (`docs: extraction & hardening design spec`)
> and **a6ca85f** (`docs: architecture pivot to unified polling + hexagonal design`) silently
> replaced the PoC's per-`(from,to)` **transition whitelist** (`transitions.yml`) with a
> 3-column-class model (`columns.yml`). The n8n→polling pivot those commits document is real and
> stays; the column-contract rewrite was an **un-flagged simplification** that dropped the
> whitelist, the guarded rollback, script transitions, `on_fail`/`advance`, per-transition prompts,
> the concurrency cap+queue, the per-item move rate-limit durability, the per-repo clone bootstrap,
> the worktree skill provisioning and the prompt-template routing. This delta REVERSES those silent
> drops. See `POC_PARITY_AUDIT.md` — 44 confirmed feature losses; the headline cluster is the
> TRANSITION/DISPATCH model.
>
> **PoC source of truth** (ABSOLUTE OLD root
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`):
> `transitions.py` (whitelist + wildcards) · `dispatch.py` (decide_transition verdicts) ·
> `runner.py` (cap/queue/rate-limit/on_fail/\_guarded_rollback/\_auto_move) ·
> `engine/cap.py` (reserve/release under flock) · `engine/launch.py` (start_session argv +
> provisioning) · `engine/worktree.py` (`ensure_clone` tokenless credential helper) ·
> `engine/perms.py` (`provision_worktree_skills` / `ensure_manual_merge_mode`) ·
> `engine/locks.py` (flock) · `placeholders.py` (`fill`) ·
> `cli/transitions_yaml.py` (the 7 prompt templates + DEFAULT_TRANSITIONS).
> `bin/` shims live at `.../skills/kanban/bin/` (a SIBLING of the package, NOT under it).

---

## Operator decisions on the phase-17 "keeps" (2026-06-05)

After reviewing the 15 phase-17 KEEP+DOC divergences, the operator upgraded four to active restoration
work (the rest stay KEEP+DOC). These are folded into the plan (phases 16–17) and reflected in the
edits below where they touch the design:

| #   | Decision               | Effect on the design / plan                                                                                     |
| --- | ---------------------- | --------------------------------------------------------------------------------------------------------------- |
| 24  | **WIRE per-column**    | Two-tier profile resolution (transition `profile` > column `permission_profile`); no global profile (EDIT 7).   |
| 13  | **ENHANCE (hybrid)**   | `core/dependency_gate` returns tri-state; `app/tick` resolves UNKNOWN deps via live `issue_state` (phase 16.6). |
| 19  | **PORT (bookkeeping)** | Restore the `bookkeeping` flag in the in-memory antiloop so guarded rollback (§8.0.4) bypasses the dedup net.   |
| 21  | **REMOVE (dead code)** | Delete the vestigial `TicketStatus.IDLE` enum member.                                                           |

The full per-change detail lives in `plan/phase-17-behaviour-reconciliation.md` (#13/#19/#21/#24) and
`plan/phase-16-github-cli-parity.md` (16.6 — the `issue_state` fallback seam).

---

## How to apply (summary)

| #   | Action                                                                                                       | DESIGN target       |
| --- | ------------------------------------------------------------------------------------------------------------ | ------------------- |
| 1   | **REPLACE** §8 "Column contract — three column classes" with the §8 below (transition whitelist)             | §8 (lines ~231–241) |
| 2   | **REWRITE** the §9 table to per-transition (from→to) rows + retitle                                          | §9 (lines ~309–326) |
| 3   | **ADD** §8.4 — concurrency cap + queue + move rate-limit + fix-CI retry                                      | new, after §8.3     |
| 4   | **ADD** §8.5 — per-repo clone bootstrap + worktree skill provisioning + launch argv                          | new, after §8.4     |
| 5   | **ADD** §8.6 — prompt routing (per-transition template + `placeholders.fill`)                                | new, after §8.5     |
| 6   | **EDIT** the §3.1 tick pipeline + §3.3 module map to name the restored modules                               | §3.1, §3.3          |
| 7   | **EDIT** §10 to note `permission_mode` is per-transition (validated, bypass-banned)                          | §10                 |
| 8   | Keep §8.1 (sticky), §8.2 (Cancel teardown), §8.3 (heartbeat) as-is — they are already PoC-faithful (phase 8) | —                   |

> §8.1/§8.2/§8.3 are **unchanged** by this delta. The badge lifecycle (§8.1) and Cancel teardown
> (§8.2) were already restored to PoC parity in phase 8; this delta only restores the
> _column-contract / dispatch_ model around them.

---

## EDIT 1 — REPLACE §8 "Column contract — three column classes"

**DELETE** the entire current §8 head (the three-class table + the paragraph beginning
"`kanban-move` refuses **agent** targets…", DESIGN lines ~231–241).

**REPLACE WITH:**

> ### 8. Board contract — per-`(from,to)` transition whitelist (`transitions.yml`)
>
> The board logic is **NOT** a destination-column-class model. It is a per-`(from_col, to_col)`
> **transition whitelist** loaded from `<clone>/.claude/kanban/transitions.yml` (PoC
> `transitions.py` + `dispatch.py`; source of truth per §11). The `(from, to)` **pair is the
> dispatch key**: a move is legal **only** if its pair (or a matching wildcard) is present in the
> whitelist. An un-whitelisted move is **rejected and the card is rolled back** to `from_col`. This
> is the board's self-healing guarantee — the board cannot drift into an un-modelled state.
>
> #### 8.0.1 The `Transition` entry (PoC `transitions.py:25–41`)
>
> Each whitelisted entry carries its own action, keyed `(from_col, to_col)`:
>
> | field             | type / default   | meaning                                                                                                                                                                                                                                  |
> | ----------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------- |
> | `from` / `to`     | `str` (required) | the pair; `"*"` is a wildcard on either side                                                                                                                                                                                             |
> | `profile`         | `str = ""`       | permission profile materialised into the worktree settings (`docs`/`prepare`/`dev`/`check`/`merge`)                                                                                                                                      |
> | `prompt`          | `str             | null`                                                                                                                                                                                                                                    | the per-transition LLM prompt template (`{{key}}` placeholders, §8.6)            |
> | `script`          | `str             | null`                                                                                                                                                                                                                                    | a shell script: mechanical action (no prompt) **or** an LLM gate (with a prompt) |
> | `advance`         | `"stop"          | "auto:<col>"`(default`"stop"`)                                                                                                                                                                                                           | on success, auto-move the card to `<col>` (a triggering bot move, §8.4)          |
> | `on_fail`         | `""              | "move:<col>"                                                                                                                                                                                                                             | "rollback"`(default`""`)                                                         | failure routing for the script/agent (§8.4) |
> | `permission_mode` | `str = "auto"`   | `claude --permission-mode` for the launched session; validated against `{default, acceptEdits, auto, dontAsk, plan}`; `bypassPermissions` **banned** (it skips the deny layer); non-string YAML values (`no`/`yes`/`5`/`null`) fail loud |
>
> `has_action = bool(prompt) or bool(script)`. A pair present with NEITHER is an **allowed no-op**
> (e.g. `Plan → Ready to dev`).
>
> #### 8.0.2 Wildcards & precedence (PoC `transitions.py:63–78`)
>
> `TransitionConfig.get(from, to)` resolves with **explicit-wins** precedence:
> **explicit `(from, to)` pair** > **`(from, "*")`** (any destination from this source) >
> **`("*", to)`** (any source into this destination). A `"*" → "*"` entry is **rejected at load**
> (`ValueError`). Wildcards model the parking/Cancel rows: `("*", "Blocked")`, `("Blocked", "*")`,
> `("*", "Cancel")`, `("Cancel", "Backlog")`.
>
> #### 8.0.3 `decide_transition` verdicts (PURE — PoC `dispatch.py:42–92`)
>
> The pure decision classifies a `(from, to)` move against the whitelist and returns one of **four**
> verdicts; the runner/tick layer adds **five** more (it never returns those four-plus-five on the
> pure path — they are constructed around `decide_transition`):
>
> | verdict                     | condition                                                     | effect                                                                                |
> | --------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
> | `launch`                    | pair present, has a `prompt` (optionally gated by a `script`) | start an agent in the worktree (run the gate script first if present)                 |
> | `run_script`                | pair present, has a `script` but **no** `prompt`              | run the script **mechanically** (no LLM); exit 0 → advance/record, exit≠0 → `on_fail` |
> | `noop`                      | pair present, no action                                       | record the column and continue                                                        |
> | `rollback`                  | pair **absent** from the whitelist                            | move the card **back to `from_col`** (guarded — see below)                            |
> | _(runner-added)_ `skip`     | idempotency / kill-switch / paused                            | record, do nothing                                                                    |
> | _(runner-added)_ `queue`    | concurrency cap full (§8.4)                                   | persist a relaunch marker, defer                                                      |
> | _(runner-added)_ `block`    | misconfigured board / anti-loop / unattended window           | park in `Blocked`                                                                     |
> | _(runner-added)_ `teardown` | a move **into `Cancel`** (§8.2)                               | mechanical raze, no agent                                                             |
> | _(runner-added)_ `reset`    | `Cancel → Backlog` (§8.2)                                     | resume re-arm                                                                         |
>
> #### 8.0.4 Guarded rollback (PoC `runner.py:170–209`)
>
> On a `rollback` verdict the runner moves the card BACK to `from_col`, **records the move as a
> bookkeeping bot move** (so the resulting board change does NOT re-trigger the dispatcher), comments
> `transition not allowed — card returned to <from>`, and persists the column. `_guarded_rollback`
> serves **three** PoC paths, all restored: (a) an un-whitelisted transition, (b) a human move into
> an agent column **during a live session** (anti-double-session), and (c) an `on_fail: rollback`
> script/agent failure (§8.4).
>
> #### 8.0.5 `kanban-move` refusal
>
> `kanban-move` (the agent self-move shim) refuses to move a card into a **launch transition's
> target** — the agent must never re-trigger its own stage. The refusal is keyed on the transition
> whitelist (a launch target), NOT on a static column class. This preserves merge=human-only: the
> `Review → Merge` row is a human-authorised script-gated launch, so an agent cannot self-advance
> into it.

---

## EDIT 2 — REWRITE §9 "Default columns & triggering" as per-transition rows

**RETITLE** §9 to **"Default columns & default transition table"** and **REPLACE** the column-class
table + the closing paragraph (DESIGN lines ~309–326) **WITH** the two tables below (ported verbatim
from PoC `cli/transitions_yaml.py:20–158`).

> The board provisions the canonical 12 columns (PoC `DEFAULT_COLUMNS`), display order:
> `Backlog · Design · Plan · Ready to dev · Prepare feature · Blocked · Implement · PR Ready ·
Review · Merge · Done · Cancel`. (`Blocked` deliberately sits between `Prepare feature` and
> `Implement`; `Cancel` is last.)
>
> The shipped **default transition table** (`DEFAULT_TRANSITIONS`) — each row is one whitelisted
> `(from, to)` entry with its own action. `defaults`: `concurrency_cap: 3`,
> `move_rate_limit_per_hour: 10` (the loader fallbacks are 2 and 10).
>
> | from            | to              | profile | action                                                                                    | advance           | on_fail            |
> | --------------- | --------------- | ------- | ----------------------------------------------------------------------------------------- | ----------------- | ------------------ |
> | Backlog         | Design          | docs    | prompt `/implement:brainstorm` (`_DESIGN_PROMPT`)                                         | stop              | —                  |
> | Design          | Plan            | docs    | prompt `/implement:plan` (`_PLAN_PROMPT`)                                                 | stop              | —                  |
> | Plan            | Ready to dev    | —       | **allowed no-op**                                                                         | —                 | —                  |
> | Ready to dev    | Prepare feature | prepare | prompt `/implement:create-branch` (`_PREPARE_PROMPT`)                                     | stop              | —                  |
> | Prepare feature | Implement       | dev     | prompt `/implement:phase` (`_IMPLEMENT_PROMPT`)                                           | **auto:PR Ready** | —                  |
> | Implement       | PR Ready        | check   | **script** `bin/check-pr-ready.sh` (mechanical, `run_script`)                             | —                 | **move:Implement** |
> | PR Ready        | Implement       | dev     | prompt fix-CI (`_FIXCI_PROMPT`)                                                           | **auto:PR Ready** | —                  |
> | PR Ready        | Review          | dev     | prompt `/implement:pr-review` (`_REVIEW_PROMPT`)                                          | stop              | —                  |
> | Review          | Merge           | merge   | **script gate** `bin/check-merge-ready.sh` **then** prompt squash-merge (`_MERGE_PROMPT`) | **auto:Done**     | **move:Review**    |
> | Merge           | Done            | —       | terminal no-op                                                                            | —                 | —                  |
> | \*              | Blocked         | —       | parking wildcard                                                                          | —                 | —                  |
> | Blocked         | \*              | —       | un-park wildcard                                                                          | —                 | —                  |
> | \*              | Cancel          | —       | teardown (runner-intercepted, §8.2)                                                       | —                 | —                  |
> | Cancel          | Backlog         | —       | reset / resume (runner-intercepted, §8.2)                                                 | —                 | —                  |
>
> **Two transitions land in the SAME destination column `Implement` but carry DIFFERENT prompts** —
> `Prepare feature → Implement` runs `_IMPLEMENT_PROMPT`, `PR Ready → Implement` runs `_FIXCI_PROMPT`.
> This is the load-bearing reason the model is per-`(from,to)` and **not** per-column: a column reached
> from two origins gets two prompts. The 3-class column model could not express this.
>
> The `_MERGE_PROMPT` drives the squash-merge + `bin/kanban-update-main {{base_clone}} {{dev_repo_path}}`
>
> - move to `Done`. The `implement:*` prompt defaults live **only** in the `transitions.yml` template
>   (per-repo, user-editable) — the engine stays generic.

> **Note for the plan**: this restores `transitions.yml` as the per-clone whitelist file. The phase-8
> sticky-marker prefix (`<!-- kanban:step=<key> -->`) and the badge lifecycle (§8.1) are unaffected —
> the sticky stage key is the destination column key, which still exists.

---

## EDIT 3 — ADD §8.4 "Concurrency cap · queue · move rate-limit · fix-CI retry"

**INSERT** after §8.3:

> ### 8.4 Concurrency cap, queue, move rate-limit & fix-CI retry (restored from PoC)
>
> These four runaway/workload guards were ported as primitives but left **unwired** (the cap slot is
> dead code, the queue is a stub). They are restored as live behaviour.
>
> #### 8.4.1 Concurrency CAP — reserve before launch (PoC `engine/cap.py`, `runner.py:706,756–770`)
>
> Active sessions are markers under `~/.kanban/slots/`. **Before** every launch the runner calls
> `reserve_slot(kanban_root, cap, ticket)`: count + reserve happen in **one critical section** under
> `flock("cap")` (PoC `engine/locks.py`) so two simultaneous ticks can never both reserve the Nth
> slot (TOCTOU-safe). Reservation is **idempotent per ticket** (a re-tick of an already-running ticket
> returns `True` without consuming another slot). `cap` is `transitions.yml`'s `concurrency_cap`
> (default 3). **On ANY `start_session` failure the reserved slot is released and the error re-raised**
> — no slot leak (PoC `runner.py:756–770`). The success path does NOT release; the slot is released by
> `kanban-session-end` when `claude` exits, by `TeardownAction`, and by `ResetAction`.
>
> #### 8.4.2 QUEUE — defer on cap-full, drain on slot-free (PoC `runner.py:706–732`, `engine/reaper.py`)
>
> When `reserve_slot` returns `False` (cap full) the runner persists a **self-contained relaunch
> marker** `~/.kanban/queue/ticket-<n>` carrying EVERY input needed to relaunch later (it never
> re-derives from config): the filled `prompt`, `profile`, target `column` + `to_option_id`, the
> GitHub coordinates, `clone_dir`, `config_dir`, `dev_repo_path`, and `concurrency_cap`. It records
> the column and returns a `queue` verdict. The **reap step drains the queue** (a `dequeue` action)
> **only when a slot frees**: it reserves, relaunches **while the marker still exists**, unlinks only
> on a confirmed start, and on empty/invalid inputs releases-the-slot-and-keeps-the-marker (no leak,
> no silent drop). `queue_dir()` and the marker are purged by teardown.
>
> #### 8.4.3 Per-item move RATE LIMIT — durable backstop (PoC `state.py:305–317`, `runner.py:504–518`)
>
> A per-item move history persisted on disk (`moves/item_<item>.json`) over a 3600 s window backs the
> §6 runaway-loop backstop: when an item has made `>= move_rate_limit_per_hour` **AUTO/bot** moves
> within the hour, the runner **parks the card in the `Blocked` column** (a visible board move +
> comment) instead of acting. Fed ONLY by auto/bot moves (`advance:auto`, `on_fail:move`, rollback
> bookkeeping), **never** by human-paced launches. The cap is **configurable per deployment** via
> `move_rate_limit_per_hour` (default 10). **Durability matters**: because the history is on disk, the
> per-hour cap holds across daemon restarts/crashes — the in-memory `core/antiloop.py` shadow alone
> resets to empty on restart and silently hard-pins the cap at 10, which this restore corrects (wire
> the YAML knob; persist the history).
>
> #### 8.4.4 Fix-CI RETRY (N=2) — bounded `on_fail:move` loop (PoC `runner.py:45–47,536–570`, `state.py:205–225`)
>
> `on_fail: move:<col>` performs an AUTO bot move that **DOES re-trigger** the next transition (the
> CI-fix loop, e.g. `PR Ready → Implement → PR Ready`), bounded by a per-loop budget `_FIXCI_CAP = 2`
> keyed by destination column (`onfail:<col>`), backed by a persisted per-`(item,key)` retry ledger
> (`retries/<safe-item>__<key>`, `bump_retry`/`reset_retry`). **Beyond the cap the ticket is parked in
> `Blocked`** (`_park_blocked`: bookkeeping move + comment). `on_fail: rollback` / `""` rolls the card
> back to `from` (guarded, §8.0.4). The reaper additionally relaunches a dead session at most
> `RETRY_LIMIT = 1` time (refresh heartbeat + relaunch) before parking in `Blocked` (DESIGN §8.3 already
> promises this; restore the implementation).

---

## EDIT 4 — ADD §8.5 "Per-repo clone bootstrap · worktree skill provisioning · launch argv"

**INSERT** after §8.4:

> ### 8.5 Per-repo clone bootstrap, worktree provisioning & launch argv (restored from PoC)
>
> #### 8.5.1 `ensure_clone` — tokenless local clone with credential-helper isolation (PoC `engine/worktree.py:20–97`)
>
> `kanban init` creates the per-repo **local git clone** at `<root>/clones/<name>` — the BASE of all
> per-ticket worktrees. The clone is created idempotently and **NON-destructively** (`git init` in
> place when a dir already exists, preserving any generated `transitions.yml`; never delete-and-reclone),
> `origin` set/added idempotently, and `git fetch origin <base>` run (working tree stays empty; the
> worktrees carry the checkouts). The launched agent therefore must NOT be assumed to operate against a
> pre-existing operator clone (the over-simplification told the operator to `cd` into a clone manually).
>
> **Token isolation (a SECURITY behaviour, security-tested in the PoC).** `origin` is kept **tokenless**.
> When a `token_path` is given, `ensure_clone` installs a **git credential helper** that reads the PAT
> from a 600-mode file **at fetch time** — the token is **never persisted in `<clone>/.git/config`**
> (only the helper command + the file path are). An empty `""` helper entry is added FIRST to clear the
> inherited helper chain for the host (so osxkeychain / git-credential-manager cannot shadow ours).
> This raises the bar against an agent exfiltrating a long-lived credential from inside its worktree. (NOT
> a sandbox: same-UID absolute-path access remains; true isolation needs a separate execution boundary.)
>
> #### 8.5.2 Worktree skill provisioning (PoC `engine/perms.py:351–391`, `engine/launch.py:233`)
>
> A worktree is a clone checkout where `.claude/` is **gitignored** — so a launched agent has **none**
> of the `/implement:*` skills (they live in the project's config repo). Before each launch,
> `provision_worktree_skills(worktree, config_dir)` **COPIES** the project's
> `.claude/{skills,commands,agents}` into `<worktree>/.claude/` so the column prompt resolves. It
> **copies, not symlinks** (a write the agent makes inside its worktree cannot propagate through a
> symlink to mutate the shared config repo), and **REFRESHES** on every launch (current skills). The
> registry persists this path as `ProjectEntry.config_dir` (computed at `init`, threaded into launch +
> the queue marker). `ensure_manual_merge_mode(worktree)` additionally pins the worktree's
> `IMPLEMENTATION.md` to `**PR merge**: manual` so an auto-triggered `/implement:pr-review` hands off to
> a human instead of squash-merging unattended — **defense-in-depth alongside** the deny-list.
>
> #### 8.5.3 flock locks (PoC `engine/locks.py`)
>
> Advisory `fcntl.flock` locks serialise clone mutations per repo (`flock(<repo>)` around
> fetch/worktree-add/remove) and the cap count+reserve critical section (`flock("cap")`). Resource
> names are sanitised (`[^A-Za-z0-9._-] → _`) so a name cannot escape the `locks/` dir.
>
> #### 8.5.4 Launch argv (PoC `engine/launch.py:80–115`)
>
> The launched session runs:
> `claude --session-id <uuid> --permission-mode <mode> --add-dir <worktree>`.
> `--session-id` is the single-source-of-truth uuid (resumable via `claude --resume <uuid>`),
> `--permission-mode` is the **per-transition** mode (default `auto`; bypass rejected),
> `--add-dir <worktree>` scopes the session. The command is suffixed with
> `; kanban-session-end <issue>` (`;`, not `&&`, so the session-end finalizer ALWAYS fires and the
> cap slot is always released). Each argv element is `shlex.quote`d (worktree paths may contain spaces).
> Registry inputs `config_dir` / `dev_repo_path` are threaded into `start_session` and persisted into
> state + the queue marker so the reaper can relaunch by reading them back.

---

## EDIT 5 — ADD §8.6 "Prompt routing — per-transition template + `placeholders.fill`"

**INSERT** after §8.5:

> ### 8.6 Prompt routing — per-transition template (`placeholders.fill {{key}}`) (restored from PoC)
>
> **The agent runs the per-transition prompt template — NOT a bare global `agent_command`.** The
> over-simplification launched a single static `claude` (default `agent_command`) for every agent
> column, with **zero ticket-context injection** — the agent received no slash-command and no ticket
> body/comments. The PoC routes a **per-`(from,to)`-transition prompt** through `placeholders.fill`.
>
> #### 8.6.1 `placeholders.fill(template, ctx)` (PoC `placeholders.py`)
>
> A pure `{{key}}` / `{{a.b}}` substitutor with dotted-path resolution that **FAILS LOUD** (`KeyError`)
> on any unknown key. At dispatch time the runner builds the launch context and substitutes it into the
> matched transition's `prompt` **before** typing it into the session (PoC `runner.py:704`:
> `decision.prompt = fill(decision.prompt, ctx)`).
>
> #### 8.6.2 The fill context (PoC `runner.py:686–703`)
>
> `ctx` is assembled live per launch from GraphQL + persisted state (both of which polling still has):
> `code`, `title`, `branch`, `script_output` (the gate script's stdout, §8.0.3), `ticket_body`,
> `issue_body` (the first cross-referenced/linked issue body), `comments` (up to 50 comment bodies),
> `codename`, `design_path`, `plan_paths` (parsed from the ticket body), `base_clone`, `dev_repo_path`.
> The `ticket_body`/`issue_body`/`comments` come from the GitHub adapter's **`issue_context`** query
> (issue body + up to 50 comments + first linked issue), fail-soft — also restored.
>
> #### 8.6.3 The shipped templates (PoC `cli/transitions_yaml.py:39–87`)
>
> Seven per-transition templates ship in the default `transitions.yml`:
> `_DESIGN_PROMPT` (`/implement:brainstorm`), `_PLAN_PROMPT` (`/implement:plan`), `_PREPARE_PROMPT`
> (`/implement:create-branch`), `_IMPLEMENT_PROMPT` (`/implement:phase`), `_FIXCI_PROMPT` (CI-red fix),
> `_REVIEW_PROMPT` (`/implement:pr-review` — explicitly _without_ merging), `_MERGE_PROMPT` (squash-merge
>
> - `bin/kanban-update-main {{base_clone}} {{dev_repo_path}}` + move to `Done`).
>
> > **Language note.** The PoC templates are in **French**. NEW's English-only artifact rule governs
> > docs and _user-facing GitHub stickies_ (§8.1). The launch _prompt_ is an internal instruction typed
> > into the agent's session, not a published artifact; the plan may keep them as-is or translate them,
> > but the **placeholders, slash-commands and routing are load-bearing and MUST be ported faithfully**.
> > (Decide-and-record this in the plan; it does not change the model.)

---

## EDIT 6 — EDIT §3.1 tick pipeline + §3.3 module map

**§3.1** — the tick pipeline currently reads
`cheap_probe → snapshot → diff → decide → LaunchAction|TeardownAction|ResetAction|BlockAction`,
then "reap stale agents + **drain queue** + heartbeat". Update the `decide` step and the action set:

> `decide` is **`decide_transition(from, to, transitions)`** against the per-`(from,to)` whitelist
> (§8), yielding `launch | run_script | noop | rollback` (+ the runner-added
> `skip | queue | block | teardown | reset`). The action set is
> `LaunchAction | RunScriptAction | RollbackAction | TeardownAction | ResetAction | BlockAction`.
> **Before** each launch the runner `reserve_slot`s (§8.4.1); on cap-full it writes a queue marker
> (§8.4.2). The "drain queue" post-step is now **live** (dequeue when a slot frees), not a stub.

**§3.3 module map** — name the restored modules so the layering is explicit:

> - `core/transitions.py` — parse `transitions.yml` → `TransitionConfig` (whitelist + wildcards), PURE.
> - `core/dispatch.py` — `decide_transition` (PURE, four verdicts).
> - `core/placeholders.py` — `fill({{key}})`, PURE.
> - `app/` — the runner glue: `reserve_slot`/`release_slot` gate, queue write/drain, `_guarded_rollback`,
>   `_on_fail`/fix-CI cap, `_auto_move` (advance), prompt `fill` + launch.
> - `adapters/workspace/` — `ensure_clone` (tokenless credential helper), `provision_worktree_skills`,
>   `ensure_manual_merge_mode`, flock `resource_lock`.
> - `adapters/store/` — persisted `slots/`, `queue/`, `moves/`, `retries/` markers (the durable
>   cap/queue/rate-limit/retry ledgers).
>
> Layering is preserved: `core/transitions.py` / `core/dispatch.py` / `core/placeholders.py` are PURE
> (zero I/O); the cap/queue/clone/provisioning side-effects live in `adapters/` behind `ports/`; the
> runner composition lives in `app/`. Downward-only imports (enforced by `tests/test_layering.py`).

---

## EDIT 7 — EDIT §10 "Security & autonomy"

**APPEND** to §10:

> `permission_mode` is configured **per transition** (not pinned per static profile), validated against
> `{default, acceptEdits, auto, dontAsk, plan}` with `bypassPermissions` **banned** at load (it would
> skip the deny layer / break merge=human-only) and non-string YAML values failing loud. The clone is
> **tokenless** with a credential-helper that keeps the PAT out of `<clone>/.git/config` (§8.5.1).
> `ensure_manual_merge_mode` pins each worktree to manual merge (§8.5.2) — defense-in-depth alongside
> the deny-list.
>
> The launch **profile** resolves **two-tier** (genesis #24, operator decision 2026-06-05): the matched
> transition's `profile` (`transitions.yml`) takes precedence; when it is empty the launch column's
> `permission_profile` (`columns.yml`) is the default. **No single global profile remains** — a launch
> with neither a transition profile nor a column default fails loud, never falling back to one global.

---

## What this delta does NOT change

- **The n8n→polling pivot stays.** HMAC/`payload.py`/`security.py`/n8n secret/org-webhook removal,
  delivery-id idempotency removal, in-daemon reaper — all intended (DESIGN §3.1/§6/§10), untouched.
- **§8.1 sticky lifecycle** (🟡→✅/⚠️/⛔→❌, five producers, advance breadcrumb) — already PoC-faithful
  (phase 8), untouched.
- **§8.2 Cancel teardown** (`--force` worktree, `branch -D`, close-PR-keep-branch, ❌ flip, recap) —
  already PoC-faithful (phase 8), untouched.
- **§8.3 heartbeat** — untouched (note: §8.3 already promises the reaper retry, restored in §8.4.4).
- The dependency gate (`Depends on #N`) — snapshot-primary, with a **HYBRID** `issue_state` GraphQL
  fallback resolving off-board deps (genesis #13, operator decision 2026-06-05: the pure `core/`
  evaluate returns a tri-state MET/UNMET/UNKNOWN; `app/tick` resolves UNKNOWN via a live `issue_state`
  query restored in phase 16.6 — closed-but-off-board deps satisfy the gate without per-tick N queries).
  The unattended-hours window + kill-switch — NEW additions, kept.

## Traceability — delta ↔ audit feature-loss

| DESIGN edit           | restores audit loss (POC_PARITY_AUDIT.md)                                                                            |
| --------------------- | -------------------------------------------------------------------------------------------------------------------- |
| §8 (whitelist)        | per-`(from,to)` whitelist (HIGH); rollback verdict (HIGH)                                                            |
| §8.0.3 / §8.0.4       | `run_script` verdict (HIGH); guarded rollback (HIGH); full 9-verdict set (MED)                                       |
| §8.4.1 / §8.4.2       | concurrency cap unenforced (HIGH); queue stub (HIGH); `queue_dir` (LOW)                                              |
| §8.4.3                | move rate-limit durability + configurability (HIGH/MED)                                                              |
| §8.4.4                | `on_fail`/fix-CI cap (MED); retry ledger `bump/reset_retry` (MED); reaper retry-relaunch (LOW)                       |
| §8.5.1                | `ensure_clone` + tokenless credential helper (MED, security)                                                         |
| §8.5.2                | `config_dir` provisioning + `ensure_manual_merge_mode` (HIGH/MED)                                                    |
| §8.5.4                | launch argv `--session-id`/`--permission-mode`/`--add-dir`; `dev_repo_path` thread (MED)                             |
| §8.6                  | `placeholders.fill` (HIGH); per-transition prompts (HIGH); `issue_context` (HIGH); auto-advance `advance:auto` (MED) |
| §9 (transition table) | per-transition prompt routing, two-prompts-one-column discriminator (HIGH)                                           |
| §10                   | per-transition `permission_mode` validation/ban (MED)                                                                |
