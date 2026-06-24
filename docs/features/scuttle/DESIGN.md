# DESIGN — scuttle (decommission the old PoC skill `.claude/skills/kanban`)

> **Ticket**: #27 · **roadmap**: cutover · **codename**: scuttle · **bump**: patch (0.17.0 → 0.17.1)
> **Nature**: documentation-only in the KanbanMate repo; the one behavioural removal (`git rm -r`)
> lives entirely in the **separate `.claude` config repo**, performed as a documented implementation
> step. No engine / runtime / behaviour change.

## 0. Re-entry note (2026-06-23)

This feature is being **re-run**. A prior pass already produced this design + plan and performed the
`.claude` deletion locally, but PR #85 was **closed without merging** and the `.claude` deletion commit
(`4aaad85 chore(kanban): remove decommissioned PoC skill …`) is **local-only / unpushed**; the card was
rolled back to Backlog to re-run the flow. Verified current state (2026-06-23):

- KanbanMate repo: design (`8e371db`) + plan (`1457768`) already committed on `kanban/ticket-27`; the
  five version sources (§7.4) are still at `0.17.0` (the §7 bump to `0.17.1` is **not yet applied**).
- `.claude` repo (`/Users/izno/dev/KanbanMate/.claude`, HEAD `4aaad85`): `skills/kanban` is **already
  removed** — `git ls-files skills/kanban/` → **0** files, the dir is gone on disk, `kanbanmate-design`
  is intact. The 159-file count in §2/§3 reflects the **original** pre-deletion state for provenance.

**Consequence for the plan/implement stages (idempotency):** §6's `git rm -r skills/kanban` must be
**idempotent** — if `git -C /Users/izno/dev/KanbanMate/.claude ls-files skills/kanban/` is already empty
(commit `4aaad85` present), the removal step is a **no-op**; do NOT fail on `git rm` matching no files,
and do NOT create a duplicate deletion commit. The KanbanMate-repo doc + version-bump work (§7) is
unaffected and still pending.

## 1. Purpose & motivation

This is the **final remnant** of the genesis extraction cutover (genesis `DESIGN.md` §11,
"Cutover & decommission"). §11 lists three decommission actions for the old PoC location:

> remove `skills/kanban/` from the portable-config repo, **remove the old launchd reaper plist**
> (`xyz.iznogoudatall.kanban-reaper`), clean `.claude/CLAUDE.md` refs.
> — `docs/archive/features/genesis/DESIGN.md:825-827`

Two of the three are already done:

- the global `~/.claude/skills/kanban` is gone;
- the old launchd reaper plist `xyz.iznogoudatall.kanban-reaper` no longer exists, and there are no
  stale `.claude/CLAUDE.md` references.

The **only un-ticked bullet** is *remove `skills/kanban/` from the portable-config repo*. The old
skill was the PoC orchestrator (n8n dispatcher + a copy of the engine + helper bins + tests); it is
**fully replaced** by the extracted `kanbanmate` engine + daemon and the live plugin skills. Keeping
the dead PoC tree around is pure confusion risk — it is the last thing standing between genesis and a
clean cutover.

The operator placed a "pending a manual look" hold on this on 2026-06-16. This brainstorm **lifts
that hold** (authorization confirmed), conditioned on a backup-before-delete safety step (§5).

## 2. Two repositories, one feature (grounded layout)

This feature spans **two distinct git repositories**, and the distinction is load-bearing — getting
it wrong makes the deletion a silent no-op.

| Repo | Path (canonical) | HEAD at design time | Role in this feature |
| --- | --- | --- | --- |
| **KanbanMate** | `/Users/izno/dev/KanbanMate` (dev clone; this work runs in worktree `…/worktrees/ticket-27`) | `b0b4cbe` | Records the cutover as complete (DESIGN + ROADMAP + version bump). No deletion happens here. |
| **`.claude` portable-config** | `/Users/izno/dev/KanbanMate/.claude` | `e9a9297` | Holds the old PoC tree `skills/kanban/`. The `git rm -r` + commit happens **here**. |

**Critical, verified fact** (grounding, do not skip in the plan):

- The `.claude` directory **inside a worktree** (e.g. `…/worktrees/ticket-27/.claude`) is a **plain
  copy with no nested `.git`** — `git -C …/worktrees/ticket-27/.claude rev-parse --show-toplevel`
  resolves **up to the KanbanMate worktree**, and KanbanMate's global ignore treats `.claude/` as
  ignored. So a `git rm` run from a worktree's `.claude/` does **nothing** to the real config repo.
- The **canonical `.claude` git repo** is `/Users/izno/dev/KanbanMate/.claude` (it has its own
  `.git/`, HEAD `e9a9297`). There, `skills/kanban` is **tracked** —
  `git -C /Users/izno/dev/KanbanMate/.claude ls-files skills/kanban/` reports **159 files** — and is
  **not** gitignored (`git check-ignore skills/kanban` → exit 1). Therefore `git rm -r skills/kanban`
  there is valid and complete.

> **Plan must target `/Users/izno/dev/KanbanMate/.claude` explicitly.** Never `git rm` from a
> worktree copy.

## 3. What is removed vs what is kept

### 3.1 Removed — `/Users/izno/dev/KanbanMate/.claude/skills/kanban/` (the old PoC tree, 159 tracked files)

Verified contents (canonical repo):

- `SKILL.md` (the old PoC skill manifest)
- `kanban`, `kanban-dispatch.sh` (the old n8n-era dispatcher)
- `n8n/` (n8n workflow assets — the pre-polling ingress, fully removed by the genesis pivot)
- `kanbanmate/` (a **copy** of the old engine — superseded by `src/kanbanmate/` in the KanbanMate repo)
- `bin/` (PoC helper bins: `kanban-comment`, `kanban-move`, `kanban-progress`, `kanban-reaper`,
  `kanban-heartbeat`, `kanban-session-end`, `kanban-update-main`, `check-pr-ready.sh`,
  `check-merge-ready.sh`)
- `tests/`, `conftest.py`, `pytest.ini`, `pyrightconfig.json`, `requirements-dev.txt`,
  `.ruff_cache/`, `logs/`, `.gitignore`

### 3.2 Kept (explicitly NOT touched)

| Kept artifact | Location | Why it is a different thing |
| --- | --- | --- |
| `plugin/skills/kanban` | KanbanMate repo, under `plugin/` | The **live** plugin skill (thin wrapper → `kanban` CLI), registered in `.claude-plugin/marketplace.json` (plugin `kanban`). Lives in a **different repo and directory** — untouched by a `.claude` deletion. |
| `plugin/skills/kanban-monitor` | KanbanMate repo, under `plugin/` | The live health-sweep skill. Same reasoning. |
| `.claude/skills/kanbanmate-design` | `.claude` repo, `skills/` | A **different** skill (the KanbanMate branding/UI-kit skill). The many in-repo `kanbanmate-design` references point here and must NOT be confused with the old `kanban` skill. |

The deletion is scoped to the single directory `skills/kanban` and removes nothing else.

## 4. Why deletion is safe — no live consumer (verified)

- **No live wiring** references the old path. Verified clean: `ecosystem.config.js`, `scripts/`,
  `Makefile`, `pyproject.toml` contain **no** reference to `skills/kanban`, `kanban-dispatch`, or
  `kanban-reaper`. PM2 serves the daemon (`kanban run`) and the live plugin skills; nothing invokes
  the PoC tree.
- The **only** in-repo references to the old path are **historical provenance docstrings** in four
  `core/` modules, each citing the *original* `PersonalScraper/.claude/skills/kanban/…` PoC source
  (the upstream the engine was extracted from — **not** this repo's deleted copy):
  - `src/kanbanmate/core/launch_argv.py:10`
  - `src/kanbanmate/core/launch_keys.py:10`
  - `src/kanbanmate/core/ticket_fields.py:10`
  - `src/kanbanmate/core/placeholders.py:8`

  Deleting our `.claude/skills/kanban` copy does **not** break these — they reference the
  PersonalScraper path for attribution, not an importable target. They stay as accurate history.
- The **frozen genesis archive** (`docs/archive/features/genesis/`) also cites the old path; it is
  frozen historical record and stays untouched.

**Decision (brainstorm): leave historical references as history.** No edits to the four docstrings
or the genesis archive.

## 5. Safety: backup before delete (authorization condition)

The operator's authorization is conditioned on a **backup taken outside both git repos** before any
`git rm`. git history in the `.claude` repo is the secondary safety net; the tarball is the primary.

Backup command (run **before** the `git rm`, from the canonical `.claude` repo's parent):

```bash
tar czf ~/kanban-poc-skill-backup-$(date +%Y%m%d).tgz \
  -C /Users/izno/dev/KanbanMate/.claude/skills kanban
```

- Destination `~/kanban-poc-skill-backup-<date>.tgz` is under `~/`, **outside** both
  `/Users/izno/dev/KanbanMate` (KanbanMate repo) and `/Users/izno/dev/KanbanMate/.claude` (config
  repo), so it is never swept by either repo's clean/reset.
- The plan must **verify the tarball exists and is non-empty** (`tar tzf … | wc -l` ≥ 159 entries —
  the tar captures the working tree, so it includes untracked residue + directory entries and the
  real count is higher than the 159 git-tracked files; observed: 367) before proceeding to `git rm`.

## 6. The deletion (in the `.claude` config repo)

Performed as a documented implementation step, in the **canonical** config repo only:

```bash
cd /Users/izno/dev/KanbanMate/.claude
git rm -r skills/kanban
git commit -m "chore(kanban): remove decommissioned PoC skill (superseded by the daemon + plugin)"
```

- **Conventional Commits** (config-repo rule). `chore` type, scope `kanban`. Description states the
  replacement so history is self-explanatory.
- **No AI attribution** — the `.claude` repo enforces this via `hooks/block_ai_attribution.py`
  (no `Co-Authored-By`, `Claude`, `Anthropic` trailers).
- **Local commit only**; pushing the `.claude` repo is the operator's call (it is a personal
  portable-config repo, separately versioned). The plan documents the commit; it does not push.
- The worktree copies of `.claude/skills/kanban` are irrelevant (they are non-git copies, §2); they
  vanish on the next worktree refresh. No action needed on them.

## 7. KanbanMate-repo deliverable (this PR)

The KanbanMate PR is **documentation-only** and records genesis §11 cutover as **complete**:

1. **`docs/features/scuttle/DESIGN.md`** — this document.
2. **`IMPLEMENTATION.md`** — the feature tracker (phases table; see §9).
3. **ROADMAP.md** — add a completion entry, in the house "— IMPLEMENTED (version, codename)" style
   used by the other shipped items (after this entry is prepended at line 6, those siblings sit at
   `ROADMAP.md:16` Board repatriation, `:35` / `:60` ingress-multiproject):

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

4. **Version bump 0.17.0 → 0.17.1** (patch — doc-only). Sync **all five** version sources (the
   version-drift lesson — all five must match; the last three are held in lockstep by
   `tests/test_plugin_manifest.py:84-129`, so a partial bump fails CI):
   - `VERSION` → `0.17.1`
   - `pyproject.toml` `version = "0.17.1"` (`pyproject.toml:7`)
   - `src/kanbanmate/__init__.py` `__version__ = "0.17.1"` (`__init__.py:11`)
   - `.claude-plugin/marketplace.json` plugin `kanban` version → `0.17.1` (`marketplace.json:9`)
   - `plugin/.claude-plugin/plugin.json` `version` → `0.17.1` (`plugin.json:3`) — the PLUGIN
     manifest (distinct from the marketplace), lockstep-enforced vs `VERSION` + marketplace by
     `tests/test_plugin_manifest.py:115-129`

**Decision (brainstorm): leave the frozen genesis archive untouched.** Completion is recorded in
ROADMAP.md (a living doc), not by editing `docs/archive/features/genesis/DESIGN.md`.

## 8. Files touched

### 8.1 KanbanMate repo (this PR — docs + version only)

| File | Change |
| --- | --- |
| `docs/features/scuttle/DESIGN.md` | **new** — this design |
| `IMPLEMENTATION.md` | **new/updated** — feature tracker for scuttle |
| `ROADMAP.md` | add the "Genesis cutover … — IMPLEMENTED (0.17.1, scuttle)" entry (§7.3) |
| `VERSION` | `0.17.0` → `0.17.1` |
| `pyproject.toml` | `version` → `0.17.1` |
| `src/kanbanmate/__init__.py` | `__version__` → `0.17.1` |
| `.claude-plugin/marketplace.json` | plugin `kanban` version → `0.17.1` |
| `plugin/.claude-plugin/plugin.json` | `version` → `0.17.1` (lockstep with VERSION + marketplace, `tests/test_plugin_manifest.py`) |

No `src/` behaviour change, no test change. `make lint` / `make test` should be unaffected; the phase
gate runs them anyway to prove the version edits did not break import/packaging.

### 8.2 `.claude` config repo (separate repo — documented implementation step, not in this PR's diff)

| Action | Path |
| --- | --- |
| backup | `~/kanban-poc-skill-backup-<date>.tgz` (outside both repos) |
| `git rm -r` + commit | `/Users/izno/dev/KanbanMate/.claude/skills/kanban` |

## 9. Implementation phases (for the plan stage)

A single small phase suffices; the plan may split the two repos into sub-phases for traceability.

- **Phase 1 — KanbanMate doc record + version bump.** Write/finalize `docs/features/scuttle/DESIGN.md`
  (this) + `IMPLEMENTATION.md`; add the ROADMAP entry; bump all five version sources to 0.17.1.
  Gate: `make check` green (lint + test + module-size), `python -c "import kanbanmate"` smoke,
  `kanbanmate.__version__ == "0.17.1"`.
- **Phase 2 — `.claude` config-repo decommission (documented step).** In
  `/Users/izno/dev/KanbanMate/.claude`: (a) take the backup tarball and verify it is non-empty;
  (b) `git rm -r skills/kanban`; (c) commit with the conventional, attribution-free message in §6;
  (d) verify `git -C /Users/izno/dev/KanbanMate/.claude ls-files skills/kanban/` is now empty and the
  kept artifacts (`plugin/skills/kanban`, `plugin/skills/kanban-monitor`,
  `.claude/skills/kanbanmate-design`) are intact. Local commit only — do not push.

## 10. Verification / acceptance

1. **Backup exists & complete**: `tar tzf ~/kanban-poc-skill-backup-<date>.tgz | wc -l` ≥ 159 (the
   tar captures the working tree — tracked files + untracked residue + directory entries — so the
   real count exceeds the 159 git-tracked files; observed: 367) before any deletion.
2. **Deletion complete in the right repo**:
   `git -C /Users/izno/dev/KanbanMate/.claude ls-files skills/kanban/` → empty;
   `ls /Users/izno/dev/KanbanMate/.claude/skills/kanban` → not found.
3. **Kept artifacts intact**: `plugin/skills/kanban`, `plugin/skills/kanban-monitor`,
   `.claude/skills/kanbanmate-design` all still present.
4. **No regression in KanbanMate**: `make check` green; `kanbanmate.__version__ == "0.17.1"`; all five
   version sources agree (`tests/test_plugin_manifest.py` passes — it enforces the lockstep).
5. **No broken references**: the four provenance docstrings (§4) and the genesis archive remain (by
   design); nothing in `src/`, `scripts/`, `ecosystem.config.js`, `Makefile`, `pyproject.toml`
   imports or shells to the deleted path (re-confirm the §4 grep returns only the four docstrings).
6. **Genesis cutover marked complete** in ROADMAP.md.

## 11. Risks & non-goals

- **Risk: deleting from the wrong `.claude`.** Mitigated by §2 — the plan/implementation must operate
  on `/Users/izno/dev/KanbanMate/.claude` (the repo with a real `.git/`), never a worktree copy.
- **Risk: clobbering a kept skill.** Mitigated by §3.2 — scope is exactly `skills/kanban`; the live
  plugin skills are in a different repo/dir, and `kanbanmate-design` is a different skill.
- **Non-goal**: rewriting the four provenance docstrings or the frozen genesis archive (§4).
- **Non-goal**: pushing the `.claude` repo, or any engine/runtime/behaviour change.
- **Non-goal**: touching the live daemons (`kanban-km`, `kanban-km-serve`, `kanban-km-config`); a
  patch version bump on a doc-only change keeps `~/.kanban-km` on-disk state byte-compatible.

## 12. Self-review note

API/paths consistent throughout: the deletion target is `/Users/izno/dev/KanbanMate/.claude` in §2,
§6, §8.2, §9, §10, §11; the backup destination `~/kanban-poc-skill-backup-<date>.tgz` is identical in
§5, §8.2, §10; the version target `0.17.1` and its five sources (incl. the lockstep-enforced
`plugin/.claude-plugin/plugin.json`) match across §7.4, §8.1, §9, §10. The
kept-vs-removed sets (§3) are the full verified directory listing of the canonical
`skills/kanban/` tree. No "should exist" assumptions remain — every cited path, line, and file count
was verified against the canonical repos at design time.
