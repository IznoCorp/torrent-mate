# Phase 1 — KanbanMate doc record + five-source version bump

**Goal**: record the genesis §11 cutover as **complete** in the KanbanMate repo and bump the version
(patch, doc-only). This phase is the entire PR diff (DESIGN §7, §8.1). No `src/` behaviour change.

## Sub-phase 1a — Finalize the feature docs

`docs/features/scuttle/DESIGN.md` already exists on this branch (committed `8e371db`). Confirm it is
present and non-empty (`test -s docs/features/scuttle/DESIGN.md`); no rewrite is needed.

`IMPLEMENTATION.md` (repo root) — the feature tracker. The `## Phases` table must be populated from
this plan's INDEX. Target rows (mirroring the INDEX phase list):

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | KanbanMate doc record + five-source version bump | phase-01-doc-record-version-bump.md | [ ] |
| 2 | `.claude` config-repo decommission (backup → `git rm -r` → commit) | phase-02-claude-repo-decommission.md | [ ] |

Set the tracker header to codename `scuttle`, roadmap `cutover`, bump `0.17.0 → 0.17.1`, design
`docs/features/scuttle/DESIGN.md`. (Confirm the current `IMPLEMENTATION.md` shape before editing — it
already carries an in-flight header from an earlier feature; replace its `## Phases` body and header
fields rather than appending.)

## Sub-phase 1b — ROADMAP completion entry

Add a completion entry to `ROADMAP.md` in the house "— IMPLEMENTED (version, codename)" style used by
the other shipped items (after this entry is prepended at line 6, those siblings shift down:
`ROADMAP.md:16` "Board repatriation … — IMPLEMENTED (0.11.0, anchor …)",
`ROADMAP.md:35` "Optional webhook ingress adapter — IMPLEMENTED (0.5.0, ingress-multiproject)").
Use the verbatim block from DESIGN §7.3:

```markdown
## Genesis cutover — old PoC skill decommissioned — IMPLEMENTED (0.17.1, scuttle)

The final un-ticked bullet of genesis `DESIGN.md` §11 ("Decommission old location"). The old PoC
skill `skills/kanban/` (n8n dispatcher + a copy of the engine + helper bins + tests) was removed
from the **separate `.claude` portable-config repo** via `git rm -r skills/kanban` (backed up to
`~/kanban-poc-skill-backup-<date>.tgz` first). It is fully superseded by the `kanbanmate` daemon
and the live plugin skills (`plugin/skills/kanban`, `plugin/skills/kanban-monitor`). The other two
§11 bullets (global skill removed; launchd reaper plist + `.claude/CLAUDE.md` refs cleaned) were
already done. Genesis extraction cutover is now fully complete.
```

**Decision (DESIGN §7):** the frozen genesis archive (`docs/archive/features/genesis/DESIGN.md`) is
**not** edited — completion is recorded in the living `ROADMAP.md`, not by mutating the frozen §11.

## Sub-phase 1c — Five-source version bump 0.17.0 → 0.17.1

Patch bump — doc-only change, no engine/behaviour change. Sync **all five** sources (the
version-drift footgun — all five must agree; the last three are held in lockstep by
`tests/test_plugin_manifest.py:84-129`, so a partial bump **fails CI**). Current value verified
`0.17.0` in every source:

- `VERSION` → `0.17.1` (currently `0.17.0`, single line).
- `pyproject.toml` → `version = "0.17.1"` (`pyproject.toml:7`, currently `version = "0.17.0"`).
- `src/kanbanmate/__init__.py` → `__version__ = "0.17.1"` (`__init__.py:11`, currently
  `__version__ = "0.17.0"`).
- `.claude-plugin/marketplace.json` → the single `kanban` plugin's `"version"`
  (`.claude-plugin/marketplace.json:9`) `"0.17.0"` → `"0.17.1"`.
- `plugin/.claude-plugin/plugin.json` → `"version"` (`plugin.json:3`) `"0.17.0"` → `"0.17.1"`. This
  is the **PLUGIN manifest** (distinct from the marketplace), and `tests/test_plugin_manifest.py`
  asserts it stays equal to both `VERSION` (`:115-120`) and the marketplace entry (`:122-129`) —
  bumping the other four but not this one is a test failure, not a cosmetic gap.

Verify agreement after editing:
- `python -c "import kanbanmate; print(kanbanmate.__version__)"` prints `0.17.1`.
- `grep '^version' pyproject.toml` shows `0.17.1`.
- `cat VERSION` shows `0.17.1`.
- `grep '"version"' .claude-plugin/marketplace.json` shows `0.17.1`.
- `grep '"version"' plugin/.claude-plugin/plugin.json` shows `0.17.1`.
- `make test` passes `tests/test_plugin_manifest.py` (the lockstep guard).

## Sub-phase 1d — Phase gate (CLAUDE.md phase-gate checklist)

The edits are doc/version only; the gate proves they did not break import/packaging (DESIGN §8.1).

1. `make lint` — ruff + mypy, zero errors.
2. `make test` — all pass (check the summary line; any ERROR = collection crash, fix imports first).
3. `make check` — lint + test + module-size guards.
4. `python -c "import kanbanmate"` smoke test.
5. `python -c "import kanbanmate; assert kanbanmate.__version__ == '0.17.1'"` — version assertion.
6. Re-confirm the DESIGN §4 grep is unchanged: `rg --type py -n 'skills/kanban' src/` returns
   **exactly** the four provenance docstrings (`core/launch_argv.py:10`, `core/launch_keys.py:10`,
   `core/ticket_fields.py:10`, `core/placeholders.py:8`) — no new or removed references.

## Commit

```
chore(scuttle): phase 1 — cutover record + bump 0.17.0 → 0.17.1
```

(Per the milestone-commit convention this phase-gate commit may instead read
`chore(scuttle): phase 1 gate — genesis cutover recorded`.) Plan files for this stage are committed
separately by the plan stage as `docs(scuttle): plan`.
