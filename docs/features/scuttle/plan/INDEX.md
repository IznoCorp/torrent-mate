# scuttle — implementation plan (INDEX)

> **Codename**: scuttle · **roadmap**: cutover · **bump**: patch (0.17.0 → 0.17.1) ·
> **Branch**: `kanban/ticket-27` (single feature branch, one PR) ·
> **Design**: `docs/features/scuttle/DESIGN.md`

## Goal (one line)

Close the **final un-ticked bullet** of the genesis extraction cutover (genesis
`docs/archive/features/genesis/DESIGN.md:825` — "remove `skills/kanban/` from the portable-config
repo"): record the cutover as complete in the KanbanMate repo (docs + version bump only) and remove
the dead PoC tree `skills/kanban/` from the **separate `.claude` portable-config repo** via
`git rm -r`, after a backup taken outside both git repos.

## Phase ordering rationale

Phase 1 lands entirely in the **KanbanMate repo** (this PR's diff): the DESIGN/IMPLEMENTATION
records, the ROADMAP completion entry, and the five-source version bump. It runs first because it is
the PR deliverable and its phase gate (`make check`, import smoke, `__version__` agreement) proves
the doc/version edits did not break import/packaging — independent of anything in the `.claude` repo.

Phase 2 is the one **behavioural** action, performed entirely in the **separate canonical `.claude`
config repo** (`/Users/izno/dev/KanbanMate/.claude`, the clone with a real `.git/`), as a documented
implementation step that is **not part of this PR's diff** (the `.claude` repo is separately
versioned and gitignored by KanbanMate). It runs second so the cutover record (Phase 1) is already
written before the irreversible-ish deletion, and it is gated by a verified backup tarball
(DESIGN §5) taken **before** the `git rm`.

## Phases

| # | Phase | File | Status |
| --- | --- | --- | --- |
| 1 | KanbanMate doc record + five-source version bump | phase-01-doc-record-version-bump.md | [ ] |
| 2 | `.claude` config-repo decommission (backup → `git rm -r` → commit) | phase-02-claude-repo-decommission.md | [ ] |

## Cross-cutting invariants (every phase upholds)

- **Two repos, one feature** (DESIGN §2): Phase 1 touches only the KanbanMate repo; Phase 2 touches
  only `/Users/izno/dev/KanbanMate/.claude` (the canonical config repo with its own `.git/`,
  HEAD `e9a9297`). **Never** `git rm` from a worktree's `.claude/` copy — it is a plain non-git copy
  whose `git rev-parse --show-toplevel` resolves up to the KanbanMate worktree and is gitignored, so
  a deletion there is a silent no-op (DESIGN §2, §11).
- **Backup before delete** (DESIGN §5): the Phase 2 `git rm` happens **only after** the tarball
  `~/kanban-poc-skill-backup-<date>.tgz` exists, is outside both git repos, and is verified
  non-empty (≥159 entries — the tar captures the working tree, so untracked residue + directory
  entries push the real count above the 159 git-tracked files; observed: 367).
- **Scope is exactly `skills/kanban`** (DESIGN §3.2): the kept artifacts — `plugin/skills/kanban`
  and `plugin/skills/kanban-monitor` (KanbanMate repo) and `.claude/skills/kanbanmate-design`
  (a **different** skill in the config repo) — are never touched.
- **No engine/runtime/behaviour change** in KanbanMate (DESIGN §11): doc + version edits only; `src/`,
  tests, and on-disk `~/.kanban-km` state stay byte-compatible (patch bump).
- **Conventional Commits + no AI attribution** in both repos (CLAUDE.md / `.claude` repo
  `hooks/block_ai_attribution.py`): no `Co-Authored-By`, `Claude`, or `Anthropic` trailers.
- **Local commits only**: Phase 2 does **not** push the `.claude` repo (operator's call).
- **Historical provenance left as history** (DESIGN §4): the four `core/` docstrings citing
  `PersonalScraper/.claude/skills/kanban/…` (`src/kanbanmate/core/launch_argv.py:10`,
  `launch_keys.py:10`, `ticket_fields.py:10`, `placeholders.py:8`) and the frozen genesis archive
  are **not** edited — they reference the upstream PoC source for attribution, not this repo's
  deleted copy.
