# Phase 8 — PM2 ecosystem + launchd decommission

## Gate

- **Requires Phase 7**: `personalscraper watch` and `personalscraper watch-now` CLI commands are fully functional. `personalscraper run --no-console` flag exists. Without these, the PM2 ecosystem has nothing to drive.
- **Produces for Phase 9**: A clean repo with PM2 as the sole process manager and zero launchd artifacts remaining. E2E tests (Phase 9) can validate the full daemon lifecycle.

## Overview

Ship `ecosystem.config.js` at the repo root with the `personalscraper-watch` app + scheduled PM2 entries replacing the stale launchd agents. Delete ALL launchd artifacts from the repo (W2/W8). Update docs to reflect PM2-only scheduling. Ship an operator cutover runbook entry in `docs/reference/runbook-post-merge.md`. This phase changes only repo metadata, config files, and docs — no Python code.

### Sub-phases (4 commits)

| #   | Commit                                                                                          | Scope           |
| --- | ----------------------------------------------------------------------------------------------- | --------------- |
| 8.1 | `feat(watch-seed): add PM2 ecosystem.config.js`                                                 | PM2 config      |
| 8.2 | `chore(watch-seed): delete launchd artifacts from repo`                                         | Launchd removal |
| 8.3 | `docs(watch-seed): update docs for PM2 cutover (INSTALLATION, MANUAL, commands, CONFIGURATION)` | Docs            |
| 8.4 | `docs(watch-seed): add operator cutover runbook to runbook-post-merge.md`                       | Runbook         |

## Sub-phase 8.1 — ecosystem.config.js

**Files:**

- Create: `ecosystem.config.js` (repo root)

```javascript
// PM2 ecosystem file for personalscraper daemons + scheduled jobs.
//
// Operator cutover (first run):
//   pm2 start ecosystem.config.js && pm2 save
//
// The 'interpreter: "none"' setting means PM2 spawns the command directly,
// not through a Node/Bun interpreter.  personalscraper is a Python CLI
// entry point installed via pip (pyenv shim).
//
// Ensure `pip install -e ".[dev]"` is done before starting so the
// `personalscraper` CLI is on PATH.

module.exports = {
  apps: [
    // ---- Daemons (autorestart: true) ----

    {
      name: "personalscraper-watch",
      script: "personalscraper",
      args: "watch",
      interpreter: "none",
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      // Log to PM2's default log dir; view with `pm2 logs personalscraper-watch`.
    },

    // ---- Scheduled jobs (autorestart: false, cron_restart) ----

    {
      name: "personalscraper-index-enrich",
      script: "personalscraper",
      args: "library-index --mode enrich --budget 1800",
      interpreter: "none",
      autorestart: false,
      cron_restart: "30 4 * * 0", // Sundays 04:30 local — off-peak
    },

    {
      name: "personalscraper-backfill-ids",
      script: "personalscraper",
      args: "library-backfill-ids",
      interpreter: "none",
      autorestart: false,
      cron_restart: "0 5 * * 0", // Sundays 05:00 local (after enrich)
    },
  ],
};
```

The three stale launchd `personalscraper-index-*` agents (quick/rotate/enrich) are replaced:

- `index-quick` + `index-rotate` → **deleted** (redundant since `index-sync` #211).
- `index-enrich` → becomes the PM2 cron entry above.
- `backfill-ids` → new PM2 cron (replaces the never-installed launchd plist).

## Sub-phase 8.2 — delete launchd artifacts

**Files to DELETE:**

- `com.personalscraper.pipeline.plist.template`
- `scripts/install-launchd.sh`
- `scripts/uninstall-launchd.sh`
- `launchd-plists/` (entire directory, if present)
- `docs/reference/launchd/` (entire directory, if present)

Use `git rm -r` for directories. Verify with `git status` that all five targets are staged for deletion.

```bash
git rm com.personalscraper.pipeline.plist.template \
       scripts/install-launchd.sh \
       scripts/uninstall-launchd.sh
git rm -r launchd-plists/ 2>/dev/null || true
git rm -r docs/reference/launchd/ 2>/dev/null || true
```

## Sub-phase 8.3 — update docs

**Files to MODIFY:**

- `INSTALLATION.md` — replace §launchd with §PM2: "Install PM2 (`npm install -g pm2`), then `pm2 start ecosystem.config.js && pm2 save`."
- `MANUAL.md` — replace "Launch the pipeline via launchd" with "The watcher daemon (`pm2 start personalscraper-watch`) polls qBittorrent and triggers runs automatically."
- `docs/reference/commands.md` — §Scheduling: replace launchd references with PM2 ecosystem + `personalscraper watch` + cron entries.
- `CONFIGURATION.md` — note that the Healthchecks.io 1-day period check stays valid (W3 safety net fills the gap if the watcher fails to trigger for 24 h).
- `README.md` — if it mentions launchd, replace with PM2.

Verify: `rg -t md 'launchd' docs/ INSTALLATION.md MANUAL.md README.md CONFIGURATION.md` returns zero matches (except the runbook in sub-phase 8.4, which documents the cutover itself).

## Sub-phase 8.4 — operator cutover runbook

**Files:**

- Modify: `docs/reference/runbook-post-merge.md`

Append a section `### watch-seed (0.39.0) — launchd → PM2 cutover`:

````markdown
### watch-seed (0.39.0) — launchd → PM2 cutover

**When**: after `git pull` on the production host (IznoServer), before
starting the watcher daemon.

1. **Stop + remove stale launchd agents** (run as the operator, not root):
   ```bash
   # The 3 indexer agents have been silently failing for months
   # (stale repo path /Users/izno/dev/PersonnalScaper — exit 1).
   launchctl bootout gui/$(id -u) com.personalscraper.index-quick 2>/dev/null || true
   launchctl bootout gui/$(id -u) com.personalscraper.index-rotate 2>/dev/null || true
   launchctl bootout gui/$(id -u) com.personalscraper.index-enrich 2>/dev/null || true
   rm -f ~/Library/LaunchAgents/com.personalscraper.index-*.plist
   ```
````

2. **Verify PM2 is installed and running**:

   ```bash
   pm2 ping   # should respond "pong"
   ```

3. **Start the PM2 ecosystem** (from the repo root):

   ```bash
   cd ~/dev/PersonalScraper
   pm2 start ecosystem.config.js
   pm2 save
   ```

4. **Verify the watcher daemon**:

   ```bash
   pm2 status personalscraper-watch   # "online", restarts=0
   pm2 logs personalscraper-watch --lines 10
   ```

   Expected: `watcher_disabled` log line if `config.watch.enabled` is false,
   or cycle log lines if enabled.

5. **Enable the watcher** (only after verifying step 4 is clean):
   Edit `config/config.json5` → set `watch.enabled: true`, then:

   ```bash
   pm2 restart personalscraper-watch
   pm2 logs personalscraper-watch --lines 5
   ```

   Expected: first poll cycle visible (60 s after start).

6. **Rollback** (if the watcher misbehaves):
   ```bash
   pm2 stop personalscraper-watch
   ```
   The rest of the pipeline continues to work manually (`personalscraper run`).

```

## Gate check (before advancing to Phase 9)

- [ ] ACC-12: `ls com.personalscraper.pipeline.plist.template scripts/install-launchd.sh scripts/uninstall-launchd.sh launchd-plists 2>&1 | grep -c 'No such file'` → 4.
- [ ] ACC-12: `test -f ecosystem.config.js && echo OK` → OK.
- [ ] `rg -t md 'launchd' docs/ INSTALLATION.md MANUAL.md README.md CONFIGURATION.md` → 0 matches (except the runbook section).
- [ ] `make lint` — 0 errors (no Python changes in this phase, but verify).
- [ ] `git status` shows deletions staged + ecosystem.config.js + doc changes.
```
