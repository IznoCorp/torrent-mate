# Phase 29 — Prompt hardening + reliable ticket↔roadmap binding (brainstorm-driven)

**Trigger:** the #91 e2e exposed four prompt/workflow gaps (operator requirements R1-R4) and a
multi-agent brainstorm (grounded in src/ + the PoC + the #91 trail, adversarially verified by two
lenses, both `sound_with_fixes`) produced this plan. **Root cause of #91 found:** the
`{{issue_body}}` enrichment takes the FIRST cross-referenced issue, direction-blind — #107
"[O1] … Depends on #91" cross-references #91, so O1's feature text was injected into #91's launch
prompt as "linked issue". Also found: the prompts name a `kanban-update-body` helper that DOES NOT
EXIST (agents improvise raw `gh issue edit`/GraphQL — the unsanctioned write path); the brainstorm
prompt orders a body OVERWRITE (destroys the seeded feature description); `_PREPARE_PROMPT` lacks
`_AUTONOMY`; the seed discards the code→issue map; nothing validates title↔body↔roadmap coherence.

**Operator decisions (locked):** late-stage already-shipped exit = **Blocked** (evidence comment →
`kanban-move` to Blocked; Cancel is operator-only — a false-positive must never close a PR/destroy
a worktree); the `{{issue_body}}` direction fix **is in scope** (code); design/plan artifacts go to
**`docs/features/<codename>/`** (parameterized in the rendered transitions.yml); the live board will
be **RE-SEEDED fresh** (no backfill script — the new seed format applies to a new board).

**Verdict fixes folded in (mandatory):** IDENTITY check BEFORE state check everywhere
("IDENTITY-THEN-STATE" — a misattributed agent must never verify the wrong feature's shipped-ness);
`kanban-update-body` must land in the SAME commit as pyproject + perms allow-lists (else agents are
steered back to the raw path); `Bash(gh issue edit*)` denied for docs/prepare profiles + helper
issue-pinning is REQUIRED (R1 is not enforceable by prompt alone); absent-marker rule in the DESYNC
constant ("no **roadmap** line → the title [CODE] is authoritative; add the marker to YOUR OWN
ticket via kanban-update-body and proceed"); `{{comments}}` framed as context-not-spec too; evidence
sources scoped to repo-local surfaces (ROADMAP.md, docs/archive/features/, git log, the code) so the
docs/prepare profiles need no new gh scopes.

## Sub-phase 29.1 — `kanban-update-body` helper + issue pinning + perms (REQUIRED FIRST)

- New `src/kanbanmate/bin/kanban_update_body.py` + pyproject `[project.scripts]` entry:
  `kanban-update-body <issue> [--set-field key value | --append-section <heading> <text-from-stdin>]`.
  Behaviour: PINNED to the launched issue (see pinning below) — refuses any other issue number;
  preserves `**roadmap**/**codename**/**design**/**plans**` marker lines unless explicitly
  `--set-field`; `--append-section` appends under a markdown heading (the brainstorm output path);
  post-write validates body `**roadmap**` code == title `[CODE]` bracket (non-zero exit + no write
  on mismatch). Uses the existing urllib client seams (timeouts mandatory).
- **Issue pinning (R1 enforcement):** at worktree provision time, write the launched issue number
  into the worktree (e.g. `<worktree>/.claude/kanban-issue`); `kanban-update-body`, `kanban-move`,
  `kanban-comment`, `kanban-progress` read it when present and REFUSE a mismatched `<issue>` argument
  (fail-loud, clear message). Absent pin file (manual/operator use outside a worktree) → unpinned
  (current behaviour).
- **Perms:** add `Bash(kanban-update-body*)` to docs/prepare/dev allow lists; add
  `Bash(gh issue edit*)` to the DENY list for ALL profiles (the universal deny — body writes go
  through the pinned helper; `gh issue view/list` stay allowed via `Bash(gh issue*)`... careful:
  the allow glob `Bash(gh issue*)` covers edit too — deny wins over allow, so the deny entry is
  sufficient and surgical).
- Tests: pin-respected/pin-refused paths; marker preservation; append-section; the
  roadmap==title validation; perms snapshots updated; a gate check asserting every helper named in
  the rendered transitions.yml exists in `[project.scripts]`.

## Sub-phase 29.2 — Seed: durable marker + persisted map

- `src/kanbanmate/cli/seed.py` `_flush`: prepend `**roadmap**: <CODE>` as the FIRST element of
  `body_parts` (its own paragraph — the `Depends on …` line stays byte-identical so
  `_rewrite_depends`'s exact string replace still matches).
- Persist the code→issue map: write `~/.kanban/seed-map/<owner>-<repo>.json` from the
  `CreatedIssue` list (currently discarded at cli/app.py:294).
- Tests: marker is first line + parser-compatible (`ticket_fields` regex); depends rewrite intact;
  map written + correct.

## Sub-phase 29.3 — `{{issue_body}}` direction fix (the #91 poisoning)

- In `app/actions.py::_launch_context` (post-port seam, where `issue` is in scope): filter out a
  cross-referenced issue whose body declares a dependency ON this ticket — match both
  `Depends on #<this-issue>` and `Depends on <CODE>` (code recoverable from the `[CODE]` title
  bracket). Filtered → `issue_body=""` (the fail-soft empty default).
- Tests: a downstream dependent's body is NOT injected; a genuine upstream source still is; the
  code-form `Depends on <CODE>` also filtered.

## Sub-phase 29.4 — Hardened prompts (transitions_defaults.py)

Rewrite the 7 prompts per the verified drafts, with the verdict fixes:

- Shared constants: `_SCOPE_GUARD` ("ticket {{code}} and NOTHING else — never another ticket"),
  `_IDENTITY_THEN_STATE` (identity triangle FIRST — title [CODE] vs **roadmap** line vs the repo
  roadmap entry; absent marker → title [CODE] authoritative + self-backfill via kanban-update-body;
  ALL board moves gated on identity pass), `_STATE_CHECK_EARLY` (shipped → evidence comment FIRST
  then kanban-move Done; repo-local evidence only), `_STATE_CHECK_LATE` (shipped → evidence comment
  FIRST then kanban-move **Blocked**; Cancel is operator-only), `_DESYNC` (STOP, kanban-progress
  journal, DESYNC comment, never guess, never touch another ticket, end session), `_AUTONOMY`
  extended (autonomous + "for identity/state ambiguity follow the DESYNC protocol instead of
  guessing"), per-stage `DONE =` completion checklist + "durable outputs BEFORE any kanban-move"
  - re-entry idempotence ("if the stage output already exists, VERIFY and finalize, don't redo").
- Per-prompt: brainstorm APPENDS (never overwrites) under `## Brainstorm`, preserving the
  `**roadmap**` line + original description; `{{issue_body}}` AND `{{comments}}` framed as
  "related context only — NOT your feature spec"; `_PREPARE_PROMPT` gains autonomy + ticket identity
  ({{code}}/{{title}}) + empty-{{design_path}}/{{plan_paths}} preconditions; `_PLAN_PROMPT` gains the
  empty-{{design_path}} precondition (DESYNC, not guesswork); `_FIXCI_PROMPT` labels
  {{script_output}} possibly-STALE + requires a live CI re-check + green-already fast path + bounded
  to the failing checks; `_REVIEW_PROMPT` names the pr-review skill's terminal merge step and orders
  it SKIPPED + verbatim gh-pr-merge ban; design/plan write to `docs/features/<codename>/`
  (a rendered parameter, not hardcoded prose). All write-backs route ONLY through kanban-update-body.
- Tests: every prompt fill()s against the production context (fail-loud guard); constants present on
  the right prompts (autonomy on ALL non-brainstorm incl. prepare); the Done/Blocked split matches
  the whitelist boundary; render round-trip green.

## Sub-phase 29.5 — DESIGN + live re-seed (operator-gated)

- DESIGN.md: new "agent discipline" subsection (the 5 constants, IDENTITY-THEN-STATE, the
  Blocked-not-Cancel rule, the binding chain incl. seed marker + map + pinned helper).
- Live ops (after deploy, operator's go): re-seed a FRESH board with the new format (new Project or
  cleaned board — operator's call at execution time); restart the daemon; verify with `kanban doctor`.

### Phase gate (per sub-phase)

`rm -rf .mypy_cache && make check` green; diff confined (NEVER the helm prep / ROADMAP /
IMPLEMENTATION / this plan); smoke import. 29.1 MUST land before or with 29.4 (the prompts name the
helper). Then daemon restart + the 29.5 live re-seed on operator signal.
