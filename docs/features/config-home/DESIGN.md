# Config Home — relocate the canonical config out of every git working tree

**Ticket**: #326 [Config-Shared]
**Date**: 2026-08-01
**Status**: operator-approved (4 structural decisions validated 2026-08-01)
**Codename**: `config-home`
**Version**: 0.72.2 → 0.73.0 (minor)
**Branch**: feat/config-home

## 1. Problem

The live config directory is `~/dev/PersonalScraper/config/` — inside the DEV git working
tree — and all 9 PM2 processes (prod `~/deploy/torrentmate`, staging `~/staging/torrentmate`,
crons) read it live via `PERSONALSCRAPER_CONFIG`. Config models are strictly
`extra="forbid"`. Consequence: **any new config key that appears in the dev working tree —
by branch checkout, commit, or plain editing during feature work — crashes the boot of every
process still running pre-feature code.** Demonstrated twice:

- PR #320 B1 — old prod code crashed on a new value written into the shared substrate.
- PR #322 BLOCKER — a new provider block in `config/tracker.json5` (dev working tree, not
  even committed) killed every prod cron at boot.

Two aggravating factors: 5 of the 19 config files are **git-tracked** (`config.json5`,
`indexer.json5`, `tracker.json5`, `watch_seed.json5`, `web.json5`) so branch switches rewrite
them live; and the topology is **pinned by tests** (`tests/indexer/test_ecosystem.py` asserts
`PERSONALSCRAPER_CONFIG == /Users/izno/dev/PersonalScraper/config` for every app).

## 2. Operator decisions (validated 2026-08-01)

| #   | Decision           | Choice                                                                                      |
| --- | ------------------ | ------------------------------------------------------------------------------------------- |
| D1  | Canonical location | **`~/.torrentmate/config`** — outside every git working tree                                |
| D2  | Dev checkout       | **Shares the canonical** (single-config model preserved; only the location changes)         |
| D3  | Versioning         | **Local mini git repo** in the canonical dir (never pushed) — history/diff/rollback         |
| D4  | New-key migration  | **`personalscraper init-config --sync`** — additive example→canonical diff, non-destructive |

## 3. Architecture

### 3.1 Relocation (D1, D2)

- Canonical dir becomes `~/.torrentmate/config/`. All consumers point at it via
  `PERSONALSCRAPER_CONFIG` (already the highest-priority resolution after `--config`):
  - `ecosystem.config.js` — the 11 `PERSONALSCRAPER_CONFIG` occurrences.
  - Dev sessions — shell/env of the dev checkout.
  - `scripts/deploy.sh` — the JWT-forge post-check currently reads `repo/config/web.json5`
    verbatim; it must resolve `$PERSONALSCRAPER_CONFIG` (fallback to the canonical path).
- `resolve_config_path()` is untouched (env-first already). No loader code change.
- The repo keeps **`config.example/` only**. The 5 tracked files are un-tracked
  (`git rm --cached`), `config/` becomes fully gitignored, and the local `config/` dir is
  removed after migration. CI never loads real config (already true) — no CI change.
- Strict `extra="forbid"` **stays**: with the config out of the working tree, strictness is
  pure quality again (a typo fails fast); the "branch arms a prod boot-break" vector is
  gone by construction.

### 3.2 Canonical mini-repo (D3)

- `git init` inside `~/.torrentmate/config` (no remote, never pushed).
- The web-UI S4 write path (`personalscraper/web/routes/config.py` → its save service)
  auto-commits after each successful save: message `config_edit: <file> (web-UI)`.
  **Fail-soft**: a git failure never blocks or fails the save (log warning only).
- Manual edits remain allowed; they are swept into a `config_edit: manual edits` commit the
  next time S4 saves or `--sync` runs (both commit `-A`).
- Implementation seam: one small module (e.g. `personalscraper/conf/config_git.py`) with
  `commit_config_dir(config_dir, message) -> bool` — no dependency on the web layer, callable
  from CLI and web.

### 3.3 `init-config --sync` (D4)

- Extends the existing `init-config` command.
- Semantics: **additive only** — copy example files missing from the canonical; for existing
  files, add missing keys (deep-merge at the JSON5 object level) with example values.
  **Never modifies or removes an existing key/value.** Reports every addition.
- `--dry-run` flag prints the would-be additions without writing (the runbook's first step).
- On apply: commits the result to the canonical mini-repo (message
  `config_sync: <n> additions from config.example`).
- JSON5 comment handling: syncing rewrites only the FILES IT CHANGES; a rewritten file keeps
  its data but may lose hand-written comments in merged sections — acceptable (documented);
  untouched files are never rewritten.
- Solves the known `config.example → config/` drift pain as a side effect.

### 3.4 Migration + guard tests

- One-shot migration script `scripts/migrate-config-home.sh` (idempotent, refuses to run
  twice): stop PM2 writers → `rsync -a` current `config/` → `~/.torrentmate/config` →
  `git init` + initial commit → verify boot (`personalscraper --config ~/.torrentmate/config
info` smoke) → operator flips `ecosystem.config.js` + dev env → `pm2 startOrRestart` →
  post-checks (`/api/version`, one pipeline `--dry-run`).
- `tests/indexer/test_ecosystem.py`: `_CANONICAL_CONFIG` becomes
  `/Users/izno/.torrentmate/config`; plus a **new invariant test**: for every app,
  `PERSONALSCRAPER_CONFIG` must NOT point inside any git working tree (walk up from the
  path looking for a `.git` — the REAL invariant, expressed as a test).
- New lightweight `verify` check `config_home`: WARN when the RESOLVED config dir lives
  inside a git working tree (defense in depth on every host/clone).

## 4. Non-goals

- No `extra="ignore"` tolerance (strictness is a deliberate choice — rejected).
- No per-env config copies (rejected by operator — D2).
- No backward compatibility (<1.0.0 — config/DB/NFO move together).
- No change to the overlay composition (`config-overlay-layout.md` semantics unchanged).
- No remote/backup automation beyond the local mini-repo.

## 5. Acceptance criteria seeds (executable — ACCEPTANCE.md format)

```bash
# ACC-01 — canonical dir exists, is a git repo, and is NOT inside a working tree
test -d ~/.torrentmate/config/.git && ! git -C ~/dev/PersonalScraper ls-files --error-unmatch config/config.json5 2>/dev/null; echo $?   # expect: 0 then non-zero from ls-files (untracked)

# ACC-02 — every PM2 app points at the canonical
node -e "const e=require('/Users/izno/dev/ecosystem.config.js');process.exit(e.apps.every(a=>!a.env||!a.env.PERSONALSCRAPER_CONFIG||a.env.PERSONALSCRAPER_CONFIG==='/Users/izno/.torrentmate/config')?0:1)"   # expect: exit 0

# ACC-03 — repo working tree carries no live config
git -C ~/dev/PersonalScraper ls-files config/ | wc -l   # expect: 0

# ACC-04 — sync is additive and non-destructive (golden test in suite + live dry-run)
personalscraper init-config --sync --dry-run   # expect: exit 0, report of missing keys (possibly none)

# ACC-05 — prod serves the same build after migration (no boot-break)
curl --connect-timeout 10 --max-time 30 -s -H "Cookie: tm_session=$TM_TOKEN" https://tm.iznogoudatall.xyz/api/version   # expect: 200, build_commit == deployed sha

# ACC-06 — S4 save auto-commits to the mini-repo
git -C ~/.torrentmate/config log --oneline -1   # expect: a config_edit/config_sync/initial commit
```

## 6. Test plan

- Unit: sync merge engine (additive deep-merge, never-destructive golden pairs, dry-run
  no-write), config_git commit helper (fail-soft), verify `config_home` check.
- Integration: `init-config --sync` end-to-end on a tmp canonical (example fixture → apply →
  re-run idempotent → values preserved).
- `tests/indexer/test_ecosystem.py` updated pins + the new not-in-a-worktree invariant.
- Post-merge: ACC-01..06 re-exercised live (feature-lifecycle convention).

## 7. Risks

- **Migration window**: processes restarted while the env flips — mitigated by the scripted
  order (stop writers first, smoke before restart) and the operator running it attended.
- **Comment loss on synced files** (3.3) — documented, limited to files the sync changes.
- **Forgotten consumer** still reading the old path: the old `config/` dir is REMOVED after
  migration, so any straggler fails loudly at boot (wanted), and the resolution fallback
  chain (`./config` CWD, pkg root) no longer finds a dir in the dev checkout.
