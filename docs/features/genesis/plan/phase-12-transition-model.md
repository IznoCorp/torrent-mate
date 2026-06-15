# Phase 12 — Transition model + prompt routing (per-(from,to) whitelist · rollback · run_script · filled launch prompt)

> Each sub-phase = ONE commit `<type>(genesis): <description>`.
> Design refs: DESIGN §8 (column model — WIDENED here to a per-(from,to) whitelist), §9 (the
> shipped `/implement:*` board), §11 (port-from-PoC; the PoC is the source of truth).
> PoC source of truth (ABSOLUTE OLD root —
> `/Users/izno/dev/PersonnalScaper/.claude/skills/kanban/kanbanmate/`):
> `<OLD>/transitions.py` (the `Transition` / `TransitionConfig` whitelist + `get` wildcard
> resolution + `load_transitions` defaults-block + `permission_mode` validation) ·
> `<OLD>/dispatch.py` (`decide_transition` — the PURE launch | run_script | noop | rollback
> verdicts, keyed on the (from,to) PAIR) ·
> `<OLD>/placeholders.py` (`fill` — `{{key}}`/`{{a.b}}` substitution, fail-loud `KeyError`) ·
> `<OLD>/cli/transitions_yaml.py` (the 7 shipped `_DESIGN/_PLAN/_PREPARE/_IMPLEMENT/_FIXCI/_REVIEW/
_MERGE` prompt strings + `DEFAULT_TRANSITIONS` table + `render_transitions_yaml` /
> `write_transitions_yml`) ·
> `<OLD>/runner.py` (`_guarded_rollback` L170-209, `_apply_launch` ctx-build + `fill` L686-704,
> `_apply_script` advance/on_fail L595-622, the classify→dispatch site L485-533) ·
> `<OLD>/engine/scripts.py` (`run_transition_script` — the mechanical subprocess runner).
> NEW root: `/Users/izno/dev/KanbanMate/src/kanbanmate/`.

**Goal**: restore the **TRANSITION MODEL + PROMPT ROUTING** — the single highest-priority parity
loss (POC_PARITY_AUDIT.md "TRANSITION/DISPATCH model" + "SECURITY/PAYLOAD" placeholders/prompts: 7
confirmed [HIGH] losses). NEW collapsed the PoC's per-(from,to) **whitelist** + per-transition
**action routing** (prompt / script / on_fail / advance / permission_mode) into a destination-only
column-class `decide()`, and dropped `placeholders.fill` + every shipped `/implement:*` prompt
entirely — so every NEW agent column launches an identical bare `claude` with no slash-command, no
codename, no ticket context, and an un-whitelisted human move sticks silently instead of being
rolled back. This phase ports all of that faithfully.

**Scope decisions (operator decisions baked into this plan).**

1. **The whitelist + prompts are POLICY, parsed from a per-repo `transitions.yml`.** The parser
   (`core/transitions.py`) and the verdict (`core/decide.py`) are PURE — `core/` imports nothing
   with I/O (the layering guard). The filled-prompt assembly (`placeholders.fill`) is PURE too.
   Reading `transitions.yml` off the clone is the **adapter/loader** job (wiring, like
   `columns.yml`).
2. **The whitelist SUPERSEDES, does not replace, the column-class model.** `columns.yml` (column
   classes: AGENT / REACTIVE / INERT) still drives the **Cancel → teardown / reset** routing
   (DESIGN §8.2; the PoC handles `(*, Cancel)` / `(Cancel, Backlog)` mechanically in the runner
   BEFORE `decide_transition`, NOT in the whitelist verdict). Phase 12 layers the (from,to)
   whitelist **on top of** that for the non-reactive moves: reactive routing wins first, then the
   whitelist classifies launch | run_script | noop | rollback. This keeps phase 8's
   teardown/reset/reaper signaling intact.
3. **English-only user-facing artifacts; INTERNAL agent prompts are a conscious language call.**
   The PoC's 7 prompt strings are FRENCH. The launch prompt is an **internal instruction typed into
   the launched agent's own session** (not a GitHub comment), so it is NOT governed by the
   English-only _GitHub-artifact_ rule (phase 8). **Operator decision: translate the prompt prose to
   English** for consistency with the codebase, but **DROP NOTHING** — every `{{placeholder}}` and
   every `/implement:*` slash-command is preserved verbatim (they are load-bearing). See 12.6.
4. **`run_script` (mechanical no-LLM transition) + the script GATE on a launch transition are
   ported here** (the audit lists them under TRANSITION/DISPATCH). The `on_fail` / `advance` /
   fix-CI-cap _consumption_ (the auto-move + park-in-Blocked loop) is the runaway-loop concern
   owned by **phase 13** (concurrency/rate-limit/retry) — this phase wires the **verdict + the
   `RunScriptAction` that runs the script and reports its exit code**, and threads `on_fail` /
   `advance` onto the action for phase 13 to consume. Where phase 13 must extend a seam introduced
   here, this plan flags it inline.
5. **`transitions.yml` provisioning couples to phase 14 (clone bootstrap).** This phase adds the
   per-repo `transitions.yml.tmpl` asset + a `render/write` step + the `kanban init` emit, mirroring
   exactly how `columns.yml` is shipped today (`assets/columns.yml.tmpl` →
   `<clone>/.claude/kanban/columns.yml`, `cli/init.py:248-251`). Phase 14's `ensure_clone` creates
   the clone dir this writes into; this phase only writes the file, referencing phase 14 for the
   clone's existence.

---

## Gate

Phases 1–11 complete; phase 8 (rich sticky + Cancel teardown) merged; branch `feat/genesis`;
`make check` green at start. Re-sync confirmed (DESIGN §11 pre-implementation gate): the PoC
`transitions.py` / `dispatch.py` / `placeholders.py` / `cli/transitions_yaml.py` are present in
`.claude/skills/kanban/kanbanmate/` and read for this port. **Before any authoritative gate check,
clear `.mypy_cache`** (`rm -rf .mypy_cache`) so a stale cache cannot mask a fresh type error.

---

### 12.1 — Pure `core/placeholders.py` (`{{key}}`/`{{a.b}}` fill, fail-loud)

**Layer**: `core/` — PURE, zero I/O (DESIGN §3.2). Direct port of the PoC `placeholders.py`; the
substitution engine the filled launch prompt (12.7) depends on, landed first so 12.7 can import it.

**Files**: `src/kanbanmate/core/placeholders.py` (new), `tests/core/test_placeholders.py` (new),
`tests/core/__init__.py` (exists).

- [ ] Port `placeholders.fill(template, ctx)` **verbatim-in-spirit** from PoC
      `placeholders.py:1-22` (only docstrings adapted to Google-style):
  - `_TOKEN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")` — the `{{key}}` / `{{a.b}}` token grammar
    (whitespace-tolerant inside the braces, dotted paths over `[\w.]`).
  - `_resolve(path: str, ctx: Mapping) -> object` — walk the dotted path; at each segment, if the
    current node is not a `Mapping` or the segment is absent, **raise `KeyError(path)`** (FAIL
    LOUD — the whole `path`, not the missing segment, mirrors the PoC). Type the input
    `ctx: Mapping[str, object]`.
  - `fill(template: str, ctx: Mapping[str, object]) -> str` — `"_TOKEN.sub"` replacing every match
    with `str(_resolve(...))`. A `KeyError` propagates (no swallow) so a launch prompt referencing a
    placeholder absent from the context fails loudly rather than launching a half-filled agent.
  - English Google-style docstrings (`Args:`/`Returns:`/`Raises:` — document the `KeyError` on an
    unknown key).
- [ ] `tests/core/test_placeholders.py` — port the 4 PoC `test_placeholders.py` cases + a fail-loud
      case: a flat `{{x}}` substitutes; a dotted `{{a.b}}` resolves through a nested mapping;
      whitespace-padded `{{ x }}` substitutes; a non-string value is `str()`-coerced; an **unknown
      key raises `KeyError`** (assert the raised path); a dotted path whose intermediate node is not
      a mapping raises `KeyError`.
- [ ] Verify: `make test` pass; `make lint` (mypy strict on the new module) zero errors; the
      layering guard sees `core/placeholders.py` import nothing with I/O (stdlib `re` +
      `collections.abc.Mapping` only).
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): pure placeholder fill engine ({{key}}/{{a.b}}, fail-loud, ported from PoC)"
```

---

### 12.2 — Pure `core/transitions.py` (parse `transitions.yml` → `TransitionConfig` + wildcard `get`)

**Layer**: `core/` — PURE, zero I/O. The parser takes a YAML **string** (not a path) so it stays
I/O-free — reading the file off the clone is the wiring/loader's job (12.9), exactly like
`core/columns.load_columns` takes a string today.

> **Divergence from the PoC (load-bearing).** PoC `load_transitions` takes a **path** and reads it
> (`Path(path).read_text()`, `transitions.py:93`). NEW's `core/` MUST NOT do I/O (the layering
> guard rejects a `Path.read_text` in `core/`). So NEW splits it: `load_transitions(yaml_text: str)`
> parses a STRING (mirroring `core/columns.load_columns`), and the wiring (12.9) does the
> `read_text`. Document this divergence in the module docstring.

**Files**: `src/kanbanmate/core/transitions.py` (new), `tests/core/test_transitions.py` (new).

- [ ] Port the dataclasses from PoC `transitions.py:25-78` **faithfully**:
  - `@dataclass(frozen=True) Transition` with EXACTLY the PoC fields (`transitions.py:29-36`):
    `from_col: str`, `to_col: str`, `profile: str = ""`, `prompt: str | None = None`,
    `script: str | None = None`, `advance: str = "stop"` (`"stop"` | `"auto:<column>"`),
    `on_fail: str = ""` (`""` | `"move:<column>"` | `"rollback"`),
    `permission_mode: str = "auto"`. Keep the `has_action` property
    (`bool(self.prompt) or bool(self.script)`, PoC L38-41).
  - `_ALLOWED_PERMISSION_MODES = frozenset({"default", "acceptEdits", "auto", "dontAsk", "plan"})`
    (PoC L20-22). **`bypassPermissions` is BANNED** (it skips the deny layer — breaks
    merge=human-only / no-force-push). Port the comment explaining `auto` is the headless-safe
    default that still enforces `permissions.deny`. NB this overlaps phase 9 (permission-mode
    `auto`); the frozenset is the same allow-list — re-use phase 9's constant if it already exposes
    one, else define it here and let phase 9 reference it.
  - `@dataclass(frozen=True) TransitionConfig` (PoC L44-78): `project: str`, `concurrency_cap: int`,
    `move_rate_limit_per_hour: int = 10`, and the three private lookup tables
    `_explicit: dict[tuple[str, str], Transition] | None = None`,
    `_wild_to: dict[str, Transition] | None = None` (from=`*`, keyed by `to`),
    `_wild_from: dict[str, Transition] | None = None` (to=`*`, keyed by `from`).
  - `TransitionConfig.get(from_col, to_col) -> Transition | None` — **wildcard precedence EXACTLY
    as PoC L63-78**: explicit `(from,to)` pair > `(from, *)` > `(*, to)`; `None` when unlisted. Keep
    the post-load `assert _explicit is not None` guards.
- [ ] Port `load_transitions(yaml_text: str) -> TransitionConfig` from PoC `load_transitions`
      (`transitions.py:81-155`), adapted to take a STRING:
  - `data = yaml.safe_load(yaml_text) or {}`; `project = data.get("project") or ""`.
  - **defaults block** (PoC L95-97): `defaults = data.get("defaults") or {}`,
    `cap = int(defaults.get("concurrency_cap", 2))`,
    `move_rate_limit = int(defaults.get("move_rate_limit_per_hour", 10))`. (NB the loader fallback
    cap is **2**; the shipped template default is **3** — 12.6/12.8 — matching the PoC exactly.)
  - For each raw entry: raise `ValueError` if `from`/`to` is missing (PoC L104-105). Validate
    `permission_mode` **in this order** (PoC L106-126): non-string → `ValueError` (YAML coerces
    `no`/`yes`/`5`/`null`); `"bypass" in mode.lower()` → `ValueError` (banned); not in
    `_ALLOWED_PERMISSION_MODES` → `ValueError`. Fail-CLOSED: an unvalidated mode aborts the load,
    no session ever launches with it.
  - Build the `Transition`, then route into the lookup tables (PoC L137-146): `"*"->"*"` →
    `ValueError` (not allowed); `from=="*"` → `wild_to[to_col]`; `to=="*"` → `wild_from[from_col]`;
    else `explicit[(from_col, to_col)]`. Return the assembled `TransitionConfig`.
  - English Google-style docstrings (`Raises:` documents the `"*"->"*"` + bad-`permission_mode`
    - missing-`from`/`to` `ValueError`s).
- [ ] `tests/core/test_transitions.py` — port the PoC `tests/test_transitions.py` assertions:
      explicit-pair beats a matching wildcard; `(from, *)` matches any destination from a source;
      `(*, to)` matches any source into a destination; an **unlisted pair returns `None`** (the
      caller rolls back — e.g. `get("Backlog", "Merge") is None`); a `"*"->"*"` entry raises;
      a `permission_mode: no` (YAML bool) raises with a quote-it hint; `bypassPermissions` raises;
      an unknown `permission_mode` raises; the defaults block parses `concurrency_cap` /
      `move_rate_limit_per_hour` (and falls back to 2 / 10 when absent).
- [ ] Verify: `make check` green; layering guard sees `core/transitions.py` import only stdlib +
      `yaml` (no I/O — `yaml.safe_load` of a string is pure, same as `core/columns`).

```bash
git commit -m "feat(genesis): pure transition whitelist parser (TransitionConfig + wildcard get, ported from PoC)"
```

---

### 12.3 — Extend `core/domain.py` (`ActionKind.ROLLBACK` + `ActionKind.RUN_SCRIPT`; widen `Action`)

**Layer**: `core/` — PURE. The domain additions the new verdicts need; landed before `decide.py`
(12.4) so the rewritten decision can construct them.

**Files**: `src/kanbanmate/core/domain.py` (extend `ActionKind` + `Action`),
`tests/core/test_domain.py` (extend, if present — else assert via the decide tests in 12.4).

- [ ] **Extend `ActionKind`** (domain.py:106-124) with two members (English enum docstrings):
  - `ROLLBACK = "rollback"` — an un-whitelisted (from,to) move; move the card BACK to `from_col`
    (PoC `dispatch.py:60-65` rollback verdict). The rollback target is **load-bearing**.
  - `RUN_SCRIPT = "run_script"` — a transition with a script but no prompt; run it mechanically, no
    LLM (PoC `dispatch.py:68-79`).
    Keep `LAUNCH / TEARDOWN / RESET / BLOCK / NOOP` unchanged.
- [ ] **Widen `Action`** (domain.py:127-143) so the whitelist verdict can carry the per-transition
      routing data the action layer (12.5) + phase 13 consume. Every new field defaulted so the
      existing constructions in `decide.py` (teardown/reset/block/noop/launch) still compile
      unchanged. English docstring on each new field:
  - `to_column: str = ""` — the destination column key (the `to` of the matched transition; on
    ROLLBACK this instead carries the `from_col` the card is bounced back to — mirror the PoC
    `Decision.column` dual use, `dispatch.py:31`).
  - `prompt: str | None = None` — the matched transition's launch prompt template (filled at
    dispatch time by 12.7; `None` for non-launch verdicts).
  - `script: str | None = None` — the matched transition's script (a gate on a launch transition,
    or the sole action on a `run_script` transition).
  - `on_fail: str = ""` — the matched transition's `on_fail` policy (`""` | `"move:<col>"` |
    `"rollback"`), threaded for phase 13's fix-CI loop to consume.
  - `advance: str = "stop"` — the matched transition's `advance` directive (`"stop"` |
    `"auto:<col>"`), threaded for phase 13's auto-advance to consume.
  - `profile: str = ""` — the matched transition's permission profile.
  - `permission_mode: str = "auto"` — the matched transition's `claude --permission-mode`.
    Keep `Transition` (domain.py:86-103, the DIFF output) UNCHANGED — it is the namesake-only diff
    record, distinct from `core/transitions.Transition` (the config entry). Document the two
    same-named types in the domain `Transition` docstring so a reader is not misled.
- [ ] Tests: assert `ActionKind.ROLLBACK` / `ActionKind.RUN_SCRIPT` exist with the documented
      values; an `Action(kind=ActionKind.NOOP, ticket=…, reason="")` still constructs with the new
      fields defaulted (back-compat).
- [ ] Verify: `make check` green; residual: existing `Action(...)` constructions still type-check.

```bash
git commit -m "feat(genesis): add ROLLBACK + RUN_SCRIPT action kinds and widen Action for transition routing"
```

---

### 12.4 — Rewrite `core/decide.py` to consult the whitelist (launch | run_script | noop | rollback)

**Layer**: `core/` — PURE. The heart of the port: replace the destination-only column-class
classification with the PoC's per-(from,to) whitelist verdict, while KEEPING the reactive
teardown/reset routing (decision §2 above) and the BLOCK guards (anti-loop / kill-switch /
unattended-window) intact.

**Files**: `src/kanbanmate/core/decide.py` (rewrite the classification body), `tests/core/test_decide.py`
(extend/rewrite), `tests/core/test_decide_transition.py` (new — port the PoC's verdict-level tests).

- [ ] **Thread the whitelist into `DecideContext`**: add `transitions: TransitionConfig | None = None`
      to `DecideContext` (decide.py:45-83). `None` preserves the legacy column-class-only path for
      any caller that has no whitelist yet (back-compat for the existing tick tests until 12.8 wires
      it); when present it is the source of truth for the launch/run_script/noop/rollback split.
      English docstring on the new field.
- [ ] **Rewrite the `decide` body** (decide.py:133-226), porting PoC `dispatch.py:42-92`
      (`decide_transition`) while preserving NEW's reactive routing + guards. Precedence order:
  1. **Reactive routing FIRST (KEEP, from NEW).** Resolve `destination`/`origin` via
     `resolve_column` (the name/key seam — UNCHANGED). If `origin` is REACTIVE and `destination.key
== ctx.reset_target` → `RESET` (Rule 1, decide.py:178-186). If `destination` is REACTIVE →
     `TEARDOWN` (Rule 2, decide.py:188-194). These mirror the PoC's runner intercepting
     `(*, Cancel)` / `(Cancel, Backlog)` BEFORE `decide_transition`, so they win first.
  2. **Whitelist verdict (NEW behaviour, port of `decide_transition`).** When
     `ctx.transitions is not None`, resolve `t = ctx.transitions.get(from_key, to_key)` where
     `from_key`/`to_key` are the **resolved column KEYS** (use `destination.key` / `origin.key` when
     resolvable, else the raw token — see the keying note below). Then: - `t is None` → `ROLLBACK` with `to_column=from_col` (the bounce target; PoC L60-65). When
     `from_column is None` (a brand-new/first-contact item) DO NOT roll back — there is no origin
     to bounce to; fall through to NOOP (record the column, no action). Document this first-contact
     carve-out (the PoC's webhook had a `from=None` record+skip leniency; NEW's first-contact
     item has `from_column is None` from the diff). - `not t.has_action` → `NOOP` with `to_column=to_col` (allowed no-op; PoC L66-67). - `t.script and not t.prompt` → `RUN_SCRIPT` carrying `script/on_fail/advance/profile/
permission_mode/to_column` (PoC L68-79). - else (has a prompt, optionally script-gated) → fall through to the AGENT/BLOCK path below,
     carrying `prompt/script/on_fail/advance/profile/permission_mode` onto the eventual LAUNCH
     Action (PoC L80-92).
  3. **BLOCK guards (KEEP, from NEW).** For a LAUNCH-bound verdict, apply the existing guards
     (decide.py:196-218): `is_blocked` anti-loop, `ctx.kill_switch`, `_outside_unattended_window`.
     Any one trips → `BLOCK`. Else → `LAUNCH` carrying the transition's routing fields.
  4. **Whitelist-absent fallback (back-compat).** When `ctx.transitions is None`, keep the legacy
     column-class path EXACTLY as today (AGENT→LAUNCH-or-BLOCK; else NOOP) so pre-12.8 callers and
     tests are untouched.
  - **Column-keying note (load-bearing).** The whitelist keys are column **keys** (e.g.
    `InProgress`), but the GitHub adapter emits Status **NAMES** (e.g. `In Progress`) as
    `to_column`/`from_column`. Resolve each token to its `Column.key` via `resolve_column` BEFORE
    the `get` lookup, so a whitelist authored in keys matches a board move authored in names (the
    same name/key seam `decide` already bridges). Document this; a test must exercise a
    name-vs-key transition resolving to the right whitelist entry.
- [ ] `tests/core/test_decide_transition.py` — port the PoC `tests/test_decide_transition.py` +
      `tests/test_transitions.py` verdict assertions onto NEW's `decide`: a whitelisted prompt
      transition → `LAUNCH` carrying the prompt; a script-only transition → `RUN_SCRIPT` carrying
      `on_fail`/`advance`; an allowed no-op (both null) → `NOOP`; an **unlisted pair → `ROLLBACK`
      with `to_column == from_col`** (assert the bounce target — "load-bearing"); a launch transition
      with BOTH script and prompt → `LAUNCH` carrying both (the gate, consumed in 12.5); a
      first-contact item (`from_column is None`) into an unlisted column → `NOOP` (no rollback).
- [ ] Extend `tests/core/test_decide.py`: the reactive routing (Cancel teardown / Cancel→Backlog
      reset) STILL wins over the whitelist; the BLOCK guards (anti-loop / kill-switch /
      unattended-window) STILL downgrade a whitelisted LAUNCH to BLOCK; `ctx.transitions is None`
      preserves the legacy column-class verdicts (back-compat).
- [ ] Verify: `make check` green; `rm -rf .mypy_cache` then `make lint` — zero mypy errors (the
      widened `Action` + new `DecideContext` field type-check across `decide` + `tick`).

```bash
git commit -m "feat(genesis): decide() consults the (from,to) whitelist — launch|run_script|noop|rollback (port decide_transition)"
```

---

### 12.5 — `app/actions.py`: `RollbackAction` + `RunScriptAction` + wire the FILLED prompt into `LaunchAction`

**Layer**: `app/` — imperative shell. Add the two new command objects and thread the matched
transition's prompt/script/profile/permission_mode onto the launch flow so the agent runs the
FILLED `/implement:*` prompt instead of the bare global `agent_command`.

**Files**: `src/kanbanmate/app/actions.py` (add `RollbackAction` + `RunScriptAction`; extend
`LaunchAction` + `Deps`), `src/kanbanmate/ports/workspace.py` (the script-runner seam — see below),
`src/kanbanmate/adapters/workspace/` (implement the script runner), `tests/app/test_actions.py`
(extend), `tests/adapters/test_workspace.py` (extend — the script runner).

- [ ] **`RollbackAction`** — port PoC `_guarded_rollback` (`runner.py:170-209`), adapted to NEW's
      ports (NEW has no dedup/bookkeeping `record_bot_move` — the diff baseline is the idempotency
      mechanism, DESIGN §6, so the bookkeeping-bot-move step is DROPPED; document the divergence):
  - Fields: `ticket: Ticket`, `to_column: str` (the `from_col` to bounce back to), `reason: str`.
  - `execute(deps)`: `deps.board_writer.move_card(item_id, to_column)` then
    `deps.board_writer.comment(issue, f"KanbanMate: {reason} — card returned to {to_column}.")`
    (English recap; PoC text was French "carte ramenée en"). Order: move → comment (a transient
    comment failure must not leave the board un-bounced). Fail-soft per step.
  - **Idempotency note**: NEW relies on the tick advancing the diff baseline to `to_column` after
    the bounce (the tick records `next_columns[item_id] = to_column` for a ROLLBACK, 12.8) so the
    bounce does NOT re-trigger next poll — the NEW analog of OLD's bookkeeping `record_bot_move`.
    State this in the docstring.
- [ ] **`RunScriptAction`** — port the mechanical-runner half of PoC `_apply_script`
      (`runner.py:595-622`), MINUS the on_fail/advance consumption (deferred to phase 13):
  - Fields: `ticket: Ticket`, `script: str`, `on_fail: str = ""`, `advance: str = "stop"`,
    `to_column: str = ""`.
  - `execute(deps)`: discover the per-ticket worktree + branch (idempotent, via the workspace
    port — see the script-runner seam), build the env `{"KANBAN_REPO": …, "KANBAN_BRANCH": branch}`
    (port `_script_env`, `runner.py:585-592`), run the script via the workspace script-runner,
    capture `(exit_code, stdout)`. Phase 12 records the verdict (exit 0 vs !=0) by logging +
    leaving a clean seam; the **auto-advance on exit 0 / on_fail routing on exit !=0 is wired in
    phase 13** (this action exposes `on_fail`/`advance` for that). Keep fail-soft: a runner
    exception is logged, never raises out of the tick.
  - **Script-runner seam (L2):** add `run_transition_script(self, ticket: int, script: str, env:
dict[str, str]) -> tuple[int, str]` to the `Workspace` (or a focused `ScriptRunner`) Protocol
    in `ports/workspace.py`, and implement it on the workspace adapter as a `subprocess.run`
    (argv-list, NEVER `shell=True`; 120 s timeout; stdout+stderr merged; cwd = the per-ticket
    worktree) — port PoC `engine/scripts.py::run_transition_script`. Keeping the subprocess in the
    adapter keeps `RunScriptAction` `subprocess`-free (the action calls the port). MANDATORY: the
    subprocess MUST set a `timeout=` (network/hang safety — the daemon never blocks on a wedged
    script).
- [ ] **Wire the FILLED prompt into `LaunchAction`** (the headline fix — actions.py:114-173):
  - Add to `Deps` (actions.py:51-89): the per-launch routing the column-less static `agent_command`
    lacked — but DO NOT bloat `Deps` with per-ticket data. Instead, **carry the per-transition
    routing on the `LaunchAction` itself** (it is already constructed per-transition in the tick):
    add `prompt: str | None = None`, `script: str | None = None`, `profile: str = ""`,
    `permission_mode: str = "auto"`, `on_fail: str = ""`, `advance: str = "stop"` fields to
    `LaunchAction` (defaulted so existing constructions compile; the tick fills them from the
    `Action` in 12.8).
  - In `LaunchAction.execute`: when `self.prompt` is set, **fill it** —
    `filled = fill(self.prompt, ctx)` where `ctx` is the launch context (see the context note) —
    and assemble the agent command from it via `quote_command` (actions.py:347-360, currently a
    dead helper the audit flags — this is its first caller). The PoC types the filled prompt into
    the session (`engine/launch.py:251`); NEW's `Sessions.launch(name, cwd, command)` takes a single
    command string, so the launched command becomes the `claude` invocation carrying the filled
    prompt (the exact argv flags — `--session-id`/`--permission-mode`/`--add-dir` + the
    `; kanban-session-end` wrapper — are phase 14's `build_claude_argv`; **reference phase 14**; here,
    minimally, route the filled prompt + `self.permission_mode` into the launched command and leave
    the argv-builder seam for phase 14). When `self.prompt` is `None`, fall back to
    `deps.agent_command` (the legacy bare-`claude` path — back-compat).
  - **Launch context for `fill`**: build the minimal `ctx` the shipped prompts reference (12.6):
    `{"code": f"#{issue}", "title": self.ticket.title, "codename": …, "design_path": …,
"plan_paths": …, "branch": branch, "script_output": script_output, "base_clone": …,
"dev_repo_path": …, "ticket_body": self.ticket.body, "issue_body": …, "comments": …}`.
    Source what NEW HAS today from `self.ticket` (`title`, `body`) + the worktree branch; the
    enriched `issue_context` fields (`issue_body`/`comments`) + the `codename`/`design_path`/
    `plan_paths` ticket-body fields + `dev_repo_path` are SEPARATE audit losses owned by phase 14/16
    — **for THIS phase, default the not-yet-available keys to `""`** so `fill` does not fail loud on
    a key the prompt references but NEW cannot yet supply, and add a `# phase 14/16: enrich` TODO.
    (The fail-loud contract still holds for keys that SHOULD be present — a typo in a template still
    raises.) Document this staged-enrichment decision.
  - Persist `permission_mode`/`profile` on the widened `TicketState` as today (phase 8.1.d already
    threads `mode`/`profile`); set `mode = self.permission_mode` (the per-transition mode) instead
    of `pinned_mode(profile)` when `self.permission_mode` is set — so the 🟡 header + persisted
    state reflect the transition's actual mode.
- [ ] Tests: `tests/app/test_actions.py` — `RollbackAction` moves the card to `to_column` + comments
      (English text, no French); `RunScriptAction` runs the script with `KANBAN_REPO`/`KANBAN_BRANCH`
      env via the workspace runner and reports the exit code, fail-soft on a runner exception;
      `LaunchAction` with a `prompt` launches the FILLED prompt (assert a `{{code}}` token was
      substituted, e.g. the session command contains `#<issue>` and the `/implement:*`
      slash-command, NOT a bare `claude`); `LaunchAction` with `prompt=None` falls back to
      `deps.agent_command`; a prompt referencing an unknown key raises `KeyError` (fail-loud)
      — assert a typo'd template raises while a defaulted-`""` enrichment key does not.
      `tests/adapters/test_workspace.py` — `run_transition_script` runs an argv-list subprocess with
      the env + a timeout, returns `(rc, stdout)`, never `shell=True`.
- [ ] Verify: `make check` green; `rg --type py -n "quote_command" src tests` now shows a real
      caller (the audit's dead-helper flag cleared).

```bash
git commit -m "feat(genesis): RollbackAction + RunScriptAction + filled per-transition launch prompt (port _guarded_rollback/_apply_script)"
```

---

### 12.6 — Ship the `/implement:*` prompt defaults + the HYBRID board (full PoC flow, columns.yml gates activation)

**Layer**: a pure constants module (no I/O) holding the shipped prompt strings + the default
transition table (NEW analog of PoC `cli/transitions_yaml.py:39-158`) + a small gate added to the
pure `core/decide.py` + the `columns.yml.tmpl` asset aligned to the unified column set.

> **HYBRID board model (operator decision, 2026-06-06).** The operator chose the **hybrid**: ship the
> PoC's FULL 7-stage transition flow in `transitions.yml` (nothing left behind) while letting
> `columns.yml` decide, **per column**, which stages run autonomously (agent) vs interactively (inert
> human gate). Concrete realization:
>
> 1. **Unified column set = NEW's existing 11 keys + one added `PrepareFeature` column** (the
>    create-branch stage NEW lacked). This is a 1:1 map of the PoC's 12-column board onto NEW's keys,
>    so the live Project v2 needs only ONE column added (`PrepareFeature`) — a deferred, post-merge
>    operational step (like §11.7). Key map (PoC display name → NEW key): `Design`→`Spec`,
>    `Plan`→`Planned`, `Ready to dev`→`ReadyToDev`, `Prepare feature`→`PrepareFeature` (NEW), `Implement`
>    →`InProgress`, `PR Ready`→`PRCI`, others identical (`Backlog`/`Review`/`Merge`/`Done`/`Cancel`/
>    `Blocked`).
> 2. **`transitions.yml` ships the full flow**; `columns.yml` is the per-column on/off switch.
> 3. **`decide()` gains a launch gate**: a whitelist LAUNCH verdict (a prompt-bearing transition) only
>    launches when the **destination column is an AGENT column** (`triggers_agent`); a prompt into an
>    INERT column → NOOP (the human gate). This is the mechanism by which `columns.yml` "decides". It
>    does NOT change PoC fidelity (in the PoC every stage column was an agent column) — it only enables
>    the hybrid's dormant early stages.
> 4. **Default classes = NEW's current choice** (the conservative default): `Spec`/`Planned`/
>    `ReadyToDev`/`PrepareFeature` **inert** (brainstorm/plan/create-branch interactive); `InProgress`/
>    `PRCI`/`Review` **agent**. So the DEFAULT board behaves EXACTLY like NEW today — the early-stage
>    prompts are shipped but DORMANT (their destination columns are inert). An operator flips a column
>    to `triggers_agent: true` to activate that stage's autonomy. Nothing is left behind (the capability
>    ships); the default is safe.
> 5. **Merge stays human (DESIGN §10, ratified phase-17 #1).** Do NOT ship an autonomous squash-merge
>    prompt — `_MERGE_PROMPT` would violate the `gh pr merge` ban. `Review→Merge` ships as a
>    `check-merge-ready.sh` script GATE (run_script, validates mergeability) with NO merge prompt;
>    `Merge` stays inert and a HUMAN performs the merge. (The `bin/kanban-update-main` helper + the
>    check scripts land in phase 15; reference them here.)

> **Language decision (operator, §3 above).** The PoC strings are FRENCH; the launch prompt is an
> INTERNAL agent instruction (NOT a GitHub comment) — **translate the prose to English**, but **DROP
> NOTHING**: every `{{placeholder}}` + every `/implement:*` slash-command is preserved verbatim. A
> test asserts each survives.

**Files**: `src/kanbanmate/core/transitions_defaults.py` (new — pure constants + the default table),
`src/kanbanmate/core/decide.py` (the agent-class launch gate), `src/kanbanmate/assets/columns.yml.tmpl`
(add `PrepareFeature`; move per-column `prompt:` into `transitions.yml`; keep `triggers_agent`/`action`/
`permission_profile`), `tests/core/test_transitions_defaults.py` (new), `tests/core/test_decide.py`
(extend — the gate), `tests/core/test_columns.py` (extend — the new column). Also update **DESIGN §8**
(the agent-class launch gate + the hybrid model) and **DESIGN §9** (the unified-key default board +
the name→key map). `core/transitions.py`/`render_transitions_yaml` (12.7) consume the defaults.

- [ ] **Add the `decide()` agent-class launch gate** (core/decide.py): in the whitelist LAUNCH-bound
      path (precedence step 2→3 from 12.4), BEFORE returning LAUNCH, require the destination column to
      be an AGENT column (`destination` resolved via `resolve_column`; class AGENT / `triggers_agent`).
      If the destination is INERT → return NOOP (the move is whitelisted+allowed but the column is a
      human gate; the transition prompt is dormant). REACTIVE destinations are already TEARDOWN
      (precedence 1, unchanged). Document the gate; a test asserts a prompt-transition into an inert
      column → NOOP, and into an agent column → LAUNCH.
- [ ] Port the prompt constants from PoC `cli/transitions_yaml.py:39-87`, English, placeholders +
      slash-commands VERBATIM: `_DESIGN_PROMPT` (`/implement:brainstorm`), `_PLAN_PROMPT`
      (`/implement:plan`), `_PREPARE_PROMPT` (`/implement:create-branch`), `_IMPLEMENT_PROMPT`
      (`/implement:phase`), `_FIXCI_PROMPT` (CI-fix, no slash-command), `_REVIEW_PROMPT`
      (`/implement:pr-review`, "WITHOUT merging"). **Do NOT port `_MERGE_PROMPT`** (merge=human, point 5
      above) — instead a `_MERGE_GATE` shipped as a SCRIPT (`bin/check-merge-ready.sh`), no prompt.
- [ ] Author `DEFAULT_TRANSITIONS` (`list[dict[str, Any]]`) keyed to the UNIFIED column keys, a 1:1
      map of the PoC table (the exact rows, NEW keys):
      | from | to | profile | action | advance | on_fail |
      | --- | --- | --- | --- | --- | --- |
      | Backlog | Spec | docs | prompt `_DESIGN_PROMPT` | stop | — |
      | Spec | Planned | docs | prompt `_PLAN_PROMPT` | stop | — |
      | Planned | ReadyToDev | — | **allowed no-op** | — | — |
      | ReadyToDev | PrepareFeature | prepare | prompt `_PREPARE_PROMPT` | stop | — |
      | PrepareFeature | InProgress | dev | prompt `_IMPLEMENT_PROMPT` | **auto:PRCI** | — |
      | InProgress | PRCI | check | **script** `bin/check-pr-ready.sh` (run_script) | — | **move:InProgress** |
      | PRCI | InProgress | dev | prompt `_FIXCI_PROMPT` | **auto:PRCI** | — |
      | PRCI | Review | dev | prompt `_REVIEW_PROMPT` | stop | — |
      | Review | Merge | check | **script** `bin/check-merge-ready.sh` (run_script, NO merge prompt) | — | **move:Review** |
      | Merge | Done | — | terminal no-op | — | — |
      | _ | Blocked | — | parking wildcard | — | — |
      | Blocked | _ | — | un-park wildcard | — | — |
      | \* | Cancel | — | teardown (reactive, runner-intercepted) | — | — |
      | Cancel | Backlog | — | reset (reactive) | — | — |
      The two SAME-destination-different-prompt rows are `PrepareFeature→InProgress` (`_IMPLEMENT_PROMPT`)
      vs `PRCI→InProgress` (`_FIXCI_PROMPT`) — the discriminator the per-column model could not express.
      `defaults`: `concurrency_cap: 3`, `move_rate_limit_per_hour: 10`.
- [ ] **Align `columns.yml.tmpl`** to the unified set: ADD a `PrepareFeature` column (name `"Prepare
    feature"`, inert by default); keep the existing classes (`Spec`/`Planned`/`ReadyToDev` inert,
      `InProgress`/`PRCI`/`Review` `triggers_agent: true`, `Cancel` teardown); REMOVE the per-column
      `prompt:` fields (prompts now live in `transitions.yml`); KEEP `permission_profile` per column
      (the phase-17 #24 per-column default). Document at the top that the per-stage prompts are in
      `transitions.yml` and a column's `triggers_agent` flag is the per-column autonomy switch.
- [ ] `tests/core/test_transitions_defaults.py`: every `/implement:*` slash-command appears in exactly
      the expected prompt; every `{{placeholder}}` token survives translation (assert the full set per
      prompt); no French prose left (no `Conçois`/`Corrige`/`déplace`); `DEFAULT_TRANSITIONS` round-trips
      through `load_transitions(render_transitions_yaml(...))` (12.7) into a `TransitionConfig` whose
      `get` resolves each shipped pair (the `PrepareFeature→InProgress` vs `PRCI→InProgress` discriminator
      resolves to DIFFERENT prompts); NO `_MERGE_PROMPT` autonomous-merge prompt exists (merge=human).
- [ ] Verify: `rm -rf .mypy_cache && make check` green; module-size guard (split into
      `core/transitions_defaults.py` to stay under ~800 LOC). The DESIGN §8/§9 edits land in this commit.

```bash
git commit -m "feat(genesis): ship /implement:* transition defaults + hybrid board (full PoC flow, columns.yml gates activation, merge stays human)"
```

---

### 12.7 — `transitions.yml` renderer + writer + the per-repo template (couples to phase 14)

**Layer**: a pure renderer (`render_transitions_yaml` — string in/out) + a thin I/O writer
(`write_transitions_yml` — the one `Path.write_text`, kept OUT of `core/`). Port PoC
`cli/transitions_yaml.py:161-205`.

**Files**: `src/kanbanmate/assets/transitions.yml.tmpl` (new — OR generated by the renderer; see
below), `src/kanbanmate/cli/init.py` (emit the file into the clone, mirroring the `columns.yml`
write at init.py:248-251), `tests/cli/test_init.py` (extend), and the renderer lands beside the
defaults (12.6) — `render_transitions_yaml` in `core/`/a pure module, `write_transitions_yml` in the
CLI/init layer (it does I/O).

- [ ] Port `render_transitions_yaml(project: str) -> str` from PoC `transitions_yaml.py:161-187`:
      build the doc `{"project": project, "defaults": {"concurrency_cap": 3,
  "move_rate_limit_per_hour": 10}, "transitions": [dict(t) for t in DEFAULT_TRANSITIONS]}`,
      `yaml.safe_dump(..., sort_keys=False, allow_unicode=True, width=120)`, and PREPEND the
      `permission_mode` documentation header (the 3 comment lines explaining the per-transition mode,
      `auto` default, banned `bypassPermissions`, allowed set). This is PURE (string out) — keep it
      in `core/` or the defaults module. NB the template default cap is **3** (the renderer) while
      the loader fallback is **2** (12.2) — faithful to the PoC.
- [ ] Port `write_transitions_yml(clone_dir, project) -> Path` from PoC `transitions_yaml.py:190-205`:
      write `render_transitions_yaml(project)` to
      `<clone>/.claude/kanban/transitions.yml` (mkdir parents, idempotent overwrite). This does I/O,
      so it lives in the CLI/init layer, NOT `core/`. Define a `CLONE_TRANSITIONS_RELPATH =
  Path(".claude")/"kanban"/"transitions.yml"` beside the existing `CLONE_COLUMNS_RELPATH`
      (init.py:60).
- [ ] **Wire into `kanban init`** (init.py:248-251, right after the `columns.yml` write): call
      `write_transitions_yml(clone_path, project_slug)` so a fresh `init` emits the whitelist next to
      `columns.yml`. **Couples to phase 14**: phase 14's `ensure_clone` creates `clone_path`; today
      `init` writes into a clone path that defaults to CWD (the audit's separate `ensure_clone` loss
      — phase 14). This phase only writes the file; reference phase 14 for the clone's creation in a
      `# phase 14: ensure_clone creates clone_path` comment.
- [ ] **Optional static asset**: if shipping a static `assets/transitions.yml.tmpl` is preferred
      over rendering at init time (matching how `columns.yml.tmpl` ships as package data), generate
      it ONCE from `render_transitions_yaml("<project>")` with a placeholder project and check it in;
      `init` then substitutes the project slug. Either approach is acceptable; the renderer is the
      source of truth. Pick the one matching the `columns.yml.tmpl` pattern (static asset + per-repo
      copy) for consistency.
- [ ] Tests: `render_transitions_yaml("owner/repo")` produces a YAML doc that `load_transitions`
      (12.2) round-trips into a `TransitionConfig` matching `DEFAULT_TRANSITIONS`; the
      `permission_mode` header is present; `write_transitions_yml` writes
      `<clone>/.claude/kanban/transitions.yml` (mkdir parents; idempotent re-write); `kanban init`
      emits `transitions.yml` beside `columns.yml` in the clone.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): transitions.yml renderer + writer + kanban init emit (port render/write_transitions_yml)"
```

---

### 12.8 — Wire the whitelist through the tick (construct routed Actions; dispatch rollback/run_script)

**Layer**: `app/` — the imperative shell. Thread the parsed `TransitionConfig` into the per-tick
context + `_build_action`, so the rewritten `decide` (12.4) verdicts become real command objects
and the new ROLLBACK / RUN_SCRIPT verdicts dispatch.

**Files**: `src/kanbanmate/app/tick.py` (`TickConfig` + the decided-action loop + `_build_action`),
`tests/app/test_tick.py` (extend).

- [ ] **`TickConfig`**: add `transitions: TransitionConfig | None = None` (tick.py:66-95) — the
      parsed whitelist, defaulted `None` for back-compat (existing tick tests with no whitelist still
      pass the legacy column-class path). English docstring.
- [ ] **Thread it into `DecideContext`** (tick.py:474-480): pass `transitions=config.transitions`
      into the `DecideContext` the loop builds, so `decide` consults the whitelist.
- [ ] **`_build_action`** (tick.py:165-185): map the two new `ActionKind`s to command objects, and
      carry the routing fields off the `Action` (12.3) onto the `LaunchAction`/`RunScriptAction`:
  - `ActionKind.ROLLBACK` → `RollbackAction(ticket=action.ticket, to_column=action.to_column,
reason=action.reason)`.
  - `ActionKind.RUN_SCRIPT` → `RunScriptAction(ticket=action.ticket, script=action.script or "",
on_fail=action.on_fail, advance=action.advance, to_column=action.to_column)`.
  - `ActionKind.LAUNCH` → `LaunchAction(ticket=action.ticket, prompt=action.prompt,
script=action.script, profile=action.profile, permission_mode=action.permission_mode,
on_fail=action.on_fail, advance=action.advance)` — KEEPING the existing dependency-gate
    pre-check (tick.py:166-177) unchanged (the gate still blocks a launch whose `Depends on #N`
    is unmet, BEFORE the prompt is wired).
    Keep TEARDOWN / RESET / BLOCK / NOOP mappings unchanged.
- [ ] **Diff-baseline advance for ROLLBACK** (the idempotency seam, tick.py:510/540): after a
      ROLLBACK executes, record `next_columns[item_id] = action.to_column` (the bounce target,
      NOT the rejected `to_column`) so the next diff compares against the column the card was bounced
      BACK to — the bounce does not re-trigger (the NEW analog of OLD's bookkeeping `record_bot_move`,
      12.5). For RUN_SCRIPT / LAUNCH, advance to `transition.to_column` as today. Document the
      ROLLBACK-specific baseline.
- [ ] **`_finalize_left_stage` interaction (phase 8) — preserve.** A ROLLBACK is NOT a forward
      advance, so it MUST NOT trigger the ✅-on-advance finalize (tick.py:512-533). Gate the
      `_finalize_left_stage` call to forward verdicts (LAUNCH / NOOP-forward / RUN_SCRIPT-success)
      only — never ROLLBACK / TEARDOWN / RESET / BLOCK (the PoC finalizes ✅ only on accepted
      non-rollback forward moves, `runner.py:497-499,618-620`). A test asserts a rollback leaves the
      LEFT sticky untouched.
- [ ] Tests: `tests/app/test_tick.py` — a whitelisted prompt move launches the FILLED prompt; a
      script-only move dispatches a `RunScriptAction`; an **un-whitelisted move dispatches a
      `RollbackAction` and the next-tick diff baseline is the bounce target** (so it does not
      re-launch/re-rollback); a rollback does NOT finalize the LEFT stage ✅; with
      `config.transitions is None` the tick still drives the legacy column-class path (back-compat);
      the reactive Cancel teardown/reset still routes correctly with a whitelist present.
- [ ] Verify: `make check` green.

```bash
git commit -m "feat(genesis): wire the transition whitelist through the tick (dispatch rollback/run_script + filled launch)"
```

---

### 12.9 — Load `transitions.yml` into `WiringConfig`/`Deps` (from the clone, like `columns.yml`)

**Layer**: `app/wiring.py` (the composition root) + `daemon/loop.py` (the config readers). Read the
clone's `transitions.yml`, parse it once, and thread the `TransitionConfig` into the per-tick
config — exactly mirroring how `columns.yml` is loaded today.

**Files**: `src/kanbanmate/app/wiring.py` (`WiringConfig` + `build_tick_config`),
`src/kanbanmate/daemon/loop.py` (`_load_wiring_config` + `_wiring_from_registry`),
`tests/daemon/test_loop.py` (extend), `tests/app/test_wiring.py` (extend if present).

- [ ] **`WiringConfig`** (wiring.py:29-58): add `transitions_yaml: str | None = None` (the raw
      `transitions.yml` document; `None` when a board ships none — falls back to the legacy
      column-class path so an un-migrated clone still ticks). English docstring.
- [ ] **`build_tick_config`** (wiring.py:110-122): when `config.transitions_yaml` is set, parse it
      via `load_transitions(config.transitions_yaml)` (12.2) and pass the resulting
      `TransitionConfig` into `TickConfig(transitions=…)`; `None` otherwise. Lazy/guarded so a
      malformed `transitions.yml` surfaces as a clear `ValueError` at wiring time (fail-closed — the
      daemon refuses to tick with an invalid whitelist rather than launch un-whitelisted).
- [ ] **Daemon config readers** — mirror the `columns.yml` read EXACTLY:
  - `_load_wiring_config` (loop.py:182-199): read `transitions_path` (a sibling key, default
    `<clone>/.claude/kanban/transitions.yml`) and set `transitions_yaml=…read_text()`; tolerate an
    absent file (`None` → legacy path).
  - `_wiring_from_registry` (loop.py:238-245): read
    `(Path(entry.clone) / CLONE_TRANSITIONS_RELPATH).read_text()` (the constant from 12.7), tolerate
    absence (`None`). This is the post-`init` path, so a freshly-`init`'d clone (which 12.7 made emit
    `transitions.yml`) wires the whitelist automatically.
- [ ] Tests: a `WiringConfig` carrying a `transitions_yaml` produces a `TickConfig` with a populated
      `TransitionConfig`; an absent `transitions.yml` (registry path) yields `transitions=None` (the
      daemon still ticks via the legacy path); a malformed `transitions.yml` raises at
      `build_tick_config` (fail-closed). End-to-end: `_wiring_from_registry` after a 12.7 `init`
      reads the emitted whitelist.
- [ ] Verify: `make check` green; `rm -rf .mypy_cache` then `make lint` — zero errors across the
      wiring + daemon readers.

```bash
git commit -m "feat(genesis): load per-repo transitions.yml into WiringConfig/TickConfig (from the clone, like columns.yml)"
```

---

### Phase 12 Gate

1. `make lint` — zero errors (ruff + `mypy src tests`). **Clear `.mypy_cache` first**
   (`rm -rf .mypy_cache`) so no stale cache masks a fresh type error from the widened `Action` /
   new `ActionKind`s / threaded `TransitionConfig`.
2. `make test` — all pass (check the summary line; any ERROR = collection crash → fix imports first).
3. `make check` — clean (lint + test + module-size guards; `core/transitions.py` ±
   `core/transitions_defaults.py` under the ~800 LOC soft cap).
4. Residual / parity grep (split — search safety: every `rg` type-filtered):
   - `rg --type py -n "decide_transition|TransitionConfig|ActionKind.ROLLBACK|ActionKind.RUN_SCRIPT" src tests`
     → the whitelist verdict, the parsed config, and both new action kinds are present and wired.
   - `rg --type py -n "fill\(|placeholders" src tests` → `placeholders.fill` is imported by
     `LaunchAction` (the prompt is actually FILLED, not static).
   - `rg --type py -n "quote_command" src tests` → has a real caller now (the audit's dead-helper
     flag cleared).
   - `rg --type py -n "shell=True" src/kanbanmate/adapters/workspace` → ZERO matches (the script
     runner uses an argv list, never a shell).
5. Parity check — the FULL transition model is exercised in tests:
   - a whitelisted prompt transition LAUNCHES the FILLED `/implement:*` prompt (a `{{code}}` token
     substituted; the slash-command present), NOT a bare `claude`;
   - the SAME destination reached from two origins gets two DIFFERENT prompts
     (`Prepare→Implement` = implement vs `PRReady→Implement` = fix-CI) — the per-column model could
     not express this;
   - a script-only transition dispatches a `RunScriptAction` (mechanical, KANBAN_REPO/BRANCH env);
   - an un-whitelisted (from,to) move dispatches a `RollbackAction` to `from_col` and the diff
     baseline is the bounce target (no re-trigger);
   - the reactive Cancel teardown/reset + the phase-8 ✅/⚠️/⛔/❌ signaling are UNBROKEN by the
     whitelist (a rollback does NOT finalize ✅);
   - `permission_mode` validation rejects `bypassPermissions` + non-strings + unknown modes
     (fail-closed at load).
6. `python -c "import kanbanmate"` — exits 0.

```bash
git commit --allow-empty -m "chore(genesis): phase 12 gate — transition model + prompt routing (whitelist · rollback · run_script · filled prompt)"
```
