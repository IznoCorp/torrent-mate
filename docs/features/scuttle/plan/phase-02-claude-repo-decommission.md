# Phase 2 — `.claude` config-repo decommission (backup → `git rm -r` → commit)

**Goal**: remove the dead PoC tree `skills/kanban/` from the **separate canonical `.claude`
portable-config repo**, after a verified backup. This is the one behavioural action of the feature
(DESIGN §6, §8.2, §9). It runs **entirely in `/Users/izno/dev/KanbanMate/.claude`** and is **not**
part of the KanbanMate PR's diff (that repo is separately versioned and gitignored by KanbanMate).

> **Repo-target invariant (DESIGN §2, §11):** every command below targets
> `/Users/izno/dev/KanbanMate/.claude` — the clone with a real `.git/` (HEAD `e9a9297`), where
> `skills/kanban` is tracked (159 files, verified) and not gitignored. **Never** operate on a
> worktree's `.claude/` copy (e.g. `…/worktrees/ticket-27/.claude`): it has no nested `.git`, its
> `git rev-parse --show-toplevel` resolves up to the KanbanMate worktree, and KanbanMate ignores
> `.claude/`, so a `git rm` there is a silent no-op.

## Sub-phase 2a — Backup before delete (authorization condition, DESIGN §5)

The operator's authorization is conditioned on a backup written **outside both git repos** before any
`git rm`. Take it from the canonical config repo:

```bash
tar czf ~/kanban-poc-skill-backup-$(date +%Y%m%d).tgz \
  -C /Users/izno/dev/KanbanMate/.claude/skills kanban
```

The destination `~/kanban-poc-skill-backup-<date>.tgz` is under `~/`, outside both
`/Users/izno/dev/KanbanMate` and `/Users/izno/dev/KanbanMate/.claude`, so neither repo's clean/reset
ever sweeps it.

**Verify the tarball before proceeding** (gate for 2b):
- `test -s ~/kanban-poc-skill-backup-*.tgz` — exists and non-empty.
- `tar tzf ~/kanban-poc-skill-backup-*.tgz | wc -l` — the tar captures the **working tree** (tracked
  files + untracked residue like `.ruff_cache/`, `logs/` + directory entries), so the count is
  materially **higher** than the 159 git-tracked files (observed: 367 entries). The gate is simply
  `≥ 159` (the tracked-file floor). If it is materially below 159, **stop** — do not delete.

## Sub-phase 2b — `git rm -r` + commit (canonical `.claude` repo only), idempotent

**Idempotency guard (DESIGN §0 re-entry note).** A prior pass already performed this deletion as
local commit `4aaad85` ("chore(kanban): remove decommissioned PoC skill …"), which is **unpushed**
in the canonical `.claude` repo. So before deleting, check whether `skills/kanban` is still tracked
and **only** run `git rm` + commit if it is — never fail on a no-match `git rm`, never create a
duplicate deletion commit:

```bash
cd /Users/izno/dev/KanbanMate/.claude
if [ "$(git ls-files skills/kanban/ | wc -l | tr -d ' ')" -gt 0 ]; then
  git rm -r skills/kanban
  git commit -m "chore(kanban): remove decommissioned PoC skill (superseded by the daemon + plugin)"
else
  echo "skills/kanban already removed (commit 4aaad85 present) — no-op, do NOT re-commit"
fi
```

- **Conventional Commits** (the `.claude` repo's rule): `chore` type, scope `kanban`; the description
  names the replacement so history is self-explanatory (DESIGN §6).
- **No AI attribution** — the `.claude` repo enforces this via `hooks/block_ai_attribution.py`
  (no `Co-Authored-By` / `Claude` / `Anthropic` trailers).
- **Local commit only** — do **not** push; pushing the personal portable-config repo is the
  operator's call (DESIGN §6).
- **Re-entry note**: if commit `4aaad85` is already present (the `else` branch above), the deletion is
  already recorded — the backup (2a) and verification (2c) still run, but no new commit is produced.

## Sub-phase 2c — Verify (DESIGN §10 acceptance)

In `/Users/izno/dev/KanbanMate/.claude`:

1. **Deletion complete in the right repo**:
   - `git -C /Users/izno/dev/KanbanMate/.claude ls-files skills/kanban/` → **empty**.
   - `ls /Users/izno/dev/KanbanMate/.claude/skills/kanban` → **not found**.
2. **Kept artifacts intact** (DESIGN §3.2):
   - `.claude/skills/kanbanmate-design` — still present on disk in the config repo
     (`test -d /Users/izno/dev/KanbanMate/.claude/skills/kanbanmate-design`). Note: this skill is
     **untracked** in the `.claude` repo (never committed there, not gitignored), so a `git ls-files`
     check returns empty — use the on-disk test, not a tracked-file count, to confirm it survived.
   - `plugin/skills/kanban` and `plugin/skills/kanban-monitor` — still present in the **KanbanMate**
     repo (a different repo/dir; untouched by this deletion).
3. **Backup retained**: `~/kanban-poc-skill-backup-<date>.tgz` still on disk (secondary safety net is
   the `.claude` repo's own git history).
4. **Worktree copies are irrelevant** (DESIGN §6): the non-git `.claude/skills/kanban` copies inside
   worktrees vanish on the next worktree refresh — no action needed.

## Definition of done (this phase)

- Backup tarball exists, verified ≥159 entries, outside both repos.
- `skills/kanban` removed from `/Users/izno/dev/KanbanMate/.claude` via a single local
  conventional-commit; nothing pushed.
- Kept artifacts (`plugin/skills/kanban`, `plugin/skills/kanban-monitor`,
  `.claude/skills/kanbanmate-design`) all intact.
- DESIGN §4 provenance docstrings and the frozen genesis archive untouched (non-goal: editing them).

## Commit

The deletion **is** the commit (in the `.claude` repo, message above). No KanbanMate-repo commit is
produced by this phase — its record lives in Phase 1's ROADMAP entry.
