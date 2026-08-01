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
- **Data-anchor precondition** (BLOCKER): the migration script rewrites relative `data_dir`
  (e.g. `"./.data"`) to its absolute path (`/Users/izno/dev/PersonalScraper/.data`) **before**
  the rsync that relocates `config/`. Reason: the loader resolves relative paths against
  `config_dir.parent` — after relocation, `config_dir.parent` changes from the dev checkout
  root to `~/.torrentmate`, so a relative `data_dir` would silently re-root to
  `~/.torrentmate/.data` and abandon ~1.9 GB of live state (library.db, acquire.db, analysis
  artifacts, ingested_torrents.json). The anchor is verified after the rewrite by loading the
  config and asserting `paths.data_dir == /Users/izno/dev/PersonalScraper/.data`.
- **Env layer**: the migration script copies the dev checkout's `.env` to
  `~/.torrentmate/.env` (`cp -p`, Step 0b). The canonical env layer lives at
  `<config parent>/.env` — it preserves secrets (`PLEX_TOKEN`, `WEB_JWT_SECRET`, etc.)
  shared by all clones (prod, staging, dev). Without this copy, every clone would need its
  own `.env` at the new location, breaking the single-config model (D2).
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
  twice). Steps (hardened, see the script for full detail):
  - **Step 0**: Anchor `data_dir` to absolute path (rewrite relative `"./.data"` →
    `/Users/izno/dev/PersonalScraper/.data` in `paths.json5`, verify by loading config).
  - **Step 0b**: Copy `.env` layer (`cp -p`) to `~/.torrentmate/.env` (preserves secrets).
  - **Step 1**: Stop PM2 writers — `torrentmate-autodeploy` first (prevents mid-migration
    deploy), then web/watch one-at-a-time with `pm2 jlist` verification, then crons.
    ERR trap (registered after stops) prints explicit recovery instructions on failure.
  - **Step 2**: `rsync -a` current `config/` → `~/.torrentmate/config` (guard: refuses to
    overwrite a hand-crafted non-git canonical).
  - **Step 3**: `git init` + initial commit.
  - **Step 4**: Update `ecosystem.config.js` PERSONALSCRAPER_CONFIG pins (dev repo only).
  - **Step 5**: Extended smoke — boot with canonical config; assert `data_dir` still resolves
    to `/Users/izno/dev/PersonalScraper/.data`; assert `indexer.db_path` is under it;
    assert `plex_token` non-empty (by name, never by value).
  - **Step 6**: Scoped restart — `pm2 startOrRestart` with `--only
torrentmate-web,torrentmate-web-staging,personalscraper-watch`, then `torrentmate-autodeploy`
    last; `pm2 save` + assert ≥ 9 `.torrentmate/config` refs in dump.pm2 (reboot resurrection).
  - Post-checks: `/api/health` → 200.
- **Merge sequencing**: **migration BEFORE merge on this host.** The migration writes the
  canonical config and flips dev `ecosystem.config.js` pins; the `feat/config-home` branch
  merge brings the deploy clone's ecosystem up to date (autodeploy → redploy with new pins).
  Deploy.sh's migration guard (§3.4 below) protects any other ordering — it refuses to
  restart the web process if the canonical dir doesn't exist when pins point there, converting
  a prod-down incident into a loud no-op deploy (old process keeps serving).
- `scripts/deploy.sh` migration guard (BLOCKER): at the top, before build/restart, checks
  whether the deploy clone's `ecosystem.config.js` pins point to `.torrentmate/config`. If
  yes → requires that `~/.torrentmate/config` exists, else refuses with an explicit "run the
  migration script" message. If pins still point at the old dev config path, the guard is a
  no-op (pre-merge deploys unaffected).
- `tests/indexer/test_ecosystem.py`: `_CANONICAL_CONFIG` becomes
  `/Users/izno/.torrentmate/config`; plus a **new invariant test**: for every app,
  `PERSONALSCRAPER_CONFIG` must NOT point inside any **ancestor** git working tree (walk
  up from the path's **parent** looking for a `.git` — the REAL invariant; the config
  dir's own mini-repo is the sanctioned D3 exemption).
- New lightweight `verify` check `config_home`: WARN when the RESOLVED config dir lives
  inside an **ancestor** git working tree (the path's own `.git` is the sanctioned
  mini-repo — defense in depth on every host/clone).
- `tests/conf/test_watch_seed_config.py`'s local-config anti-drift guard
  (`test_local_config_has_cross_seed_blocks`) is **retired** by the relocation — it
  uses `@pytest.mark.skipif` to skip when `config/` is absent (the normal state after
  migration). Its replacement is `init-config --sync --dry-run` (the additive drift
  detector from D4).

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
node -e "const e=require('/Users/izno/dev/PersonalScraper/ecosystem.config.js');process.exit(e.apps.every(a=>!a.env||!a.env.PERSONALSCRAPER_CONFIG||a.env.PERSONALSCRAPER_CONFIG==='/Users/izno/.torrentmate/config')?0:1)"   # expect: exit 0

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
