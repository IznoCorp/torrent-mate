# ENV-SEP — dev/staging/prod separation + watcher cutover (2026-07-08)

Durable record of the environment-separation change made during the S1–S4 web-UI
review session. Branch: `fix/webui-s1-s4-review`.

## Problem

The 6 `personalscraper-*` PM2 daemons/crons (`watch`, `index-enrich`,
`backfill-ids`, `follow-detect`, `grab`, `health-check`) plus `torrentmate-autodeploy`
ran from the **pyenv editable binary** (`~/.pyenv/versions/3.12.4/bin/personalscraper`)
with `cwd: __dirname` = the **dev checkout** (`~/dev/PersonalScraper`). Because the
pyenv editable install resolves `import personalscraper` to the dev checkout, every
scheduled cron fire executed **whatever feature branch dev was on** — e.g. the
in-flight `fix/webui-s1-s4-review`. Against the **shared** `library.db` (pre-1.0 = no
DB back-compat between versions), this version skew is a real hazard. The web UI
(`torrentmate-web` / `-staging`) was already isolated per-clone; only the crons/watch
were stuck on dev.

## Target topology (decided with operator)

| Role        | Path                    | Branch                 | PM2 processes                                                  |
| ----------- | ----------------------- | ---------------------- | -------------------------------------------------------------- |
| **dev**     | `~/dev/PersonalScraper` | feature branches       | none                                                           |
| **prod**    | `~/deploy/torrentmate`  | `main` (autodeploy)    | `torrentmate-web` + watch + 5 crons + `torrentmate-autodeploy` |
| **staging** | `~/staging/torrentmate` | `staging` (autodeploy) | `torrentmate-web-staging` only                                 |

Shared (unchanged): `library.db`, `.data/`, `config/`, storage disks. Separated:
the code (branch) each process runs + process ownership.

**Staging is web-only (no crons/watcher).** The shared data plane means a second
active watcher/grab/enrich would double-execute and race the single prod authority.
Staging keeps the CLI available for manual ad-hoc testing; it just runs no scheduled
daemons.

## Changes

- **`ecosystem.config.js`** — the 6 daemons/crons + autodeploy repointed to
  `script: ~/deploy/torrentmate-venv/bin/personalscraper`, `cwd: ~/deploy/torrentmate`,
  `env.PERSONALSCRAPER_CONFIG: ~/dev/PersonalScraper/config` (the prod clone has no
  full `config/` of its own; the canonical config still lives in the dev checkout and
  is shared by every process). Constants `PROD_CLONE` / `PROD_BIN` / `REAL_CONFIG`
  added. Commit `a4f6ab7f`.
- **`config/watch_seed.json5`** — `watch.enabled: false → true`. It shipped `false`
  as the conservative opt-in kill-switch (watch-seed #212, DESIGN §W); no documented
  reason to keep it off, and the process that had been "running" was a stale zombie
  holding an obsolete in-memory config (0 `completion`-triggered runs recorded).
  `cross_seed` left disabled. Commit `4bf64a05`.
- **`personalscraper/commands/watch.py`** — when `watch.enabled` is false the daemon
  now **idles** (interruptible-sleep loop honouring SIGTERM/SIGINT) instead of
  returning immediately. An instant exit crash-loops the `autorestart: true` PM2 app.
  Regression test renamed `test_disabled_exits_immediately` →
  `test_disabled_idles_until_shutdown`. Commits `90e3808b` + `471ec936`.
- **`docs/reference/web-ui.md`** — PM2 entries table + "Environment separation"
  subsection.

## Live PM2 cutover (operator-authorized, done in-session)

1. `pm2 delete` each of the 7 entries **individually** (a single space-joined
   `pm2 delete a b c …` silently parsed the list as one name and deleted nothing —
   the first cutover attempt looked successful but the old dev-bound defs survived;
   caught by re-reading `pm2 jlist` script/cwd, not by trusting the table).
2. `pm2 start ecosystem.config.js --only "<7 names>"` — recreated fresh from the
   repointed file (prod-bound script/cwd/env).
3. `pm2 save` — persisted the corrected process list to `~/.pm2/dump.pm2`.

Verification: all 6 personalscraper apps + autodeploy show `cwd=~/deploy/torrentmate`
and the prod venv binary; zero pyenv/dev-bound leftovers; `torrentmate-web` /
`-staging` untouched. `personalscraper-watch` boots cleanly from prod
(registry + trackers + acquire store loaded, no `watcher_disabled`), stays `online`,
fires no run on the first cycle. The 5 crons idle (`stopped`) awaiting `cron_restart`.

## Gotchas recorded

- `pm2 delete a b c` (space-joined in one arg) can no-op silently → delete each name
  individually and re-verify `jlist` script/cwd before trusting the cutover.
- A long-lived PM2 daemon holds its config **in memory**; a config change (here,
  `watch.enabled`) only takes effect on restart. A stale daemon can mask the real
  on-disk config state indefinitely.
- A PM2 `autorestart: true` app whose command exits immediately when a feature is
  config-disabled will **crash-loop**; make the command idle instead.
