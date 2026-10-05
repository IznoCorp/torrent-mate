// PM2 ecosystem file for personalscraper daemons + scheduled jobs.
//
// Operator cutover (first run):
//   pm2 start ecosystem.config.js && pm2 save
//
// The 'interpreter: "none"' setting means PM2 spawns the command directly,
// not through a Node/Bun interpreter.  personalscraper is a Python CLI
// entry point installed via pip.
//
// ENVIRONMENT SEPARATION (ENV-SEP):
//   dev     = ~/dev/PersonalScraper  — this checkout, feature branches, NO PM2 daemons.
//   prod    = ~/deploy/torrentmate   — tracks `prod` (autodeploy). Runs the web UI AND
//             every daemon/cron below, via the prod clone's own venv binary. Decoupled
//             from the dev checkout so the crons NEVER execute an in-flight feature branch.
//   staging = ~/staging/torrentmate  — tracks `staging` (autodeploy). Web UI ONLY
//             (read-only, PERSONALSCRAPER_WEB_ROLE=staging). NO crons/watcher: the
//             library.db / .data / disks are shared with prod, so a second active
//             watcher/grab/enrich would double-execute and race the single prod authority.
//
// All processes share the single canonical config dir (PERSONALSCRAPER_CONFIG) and the
// real library.db / .data / disks. What differs is the CODE (which branch) and process
// ownership. The daemons/crons run from the prod clone binary + cwd, with the config dir
// passed explicitly (the prod clone has no full config/ of its own).
//
// NOTE: paths are written as inline literals (not JS consts) so the regex drift-guard in
// tests/indexer/test_ecosystem.py can parse them. Keep the three canonical strings in sync:
//   prod clone : /Users/izno/deploy/torrentmate
//   prod binary: /Users/izno/deploy/torrentmate-venv/bin/personalscraper
//   config dir : /Users/izno/.torrentmate/config

module.exports = {
  apps: [
    // ---- Daemons (autorestart: true) ----

    // The watcher daemon — PROD. Runs from the prod clone (prod), NOT the dev checkout.
    {
      name: "personalscraper-watch",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "watch",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      // 30 s grace before SIGKILL — covers 1 s interruptible-sleep slice
      // granularity + context close (acquire, provider_registry) + shutdown log.
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
      // Log to PM2's default log dir; view with `pm2 logs personalscraper-watch`.
    },

    // TorrentMate web UI — PROD (tm.iznogoudatall.xyz, port 8710 from config/web.json5).
    // Runs from the deploy clone (~/deploy/torrentmate) with its OWN venv — per-clone
    // isolation from the dev editable install (avoids the stale-editable-finder incident
    // class, DESIGN §6). PERSONALSCRAPER_CONFIG points every clone at the single real
    // config dir. The DEV checkout stays runnable ad hoc via `personalscraper web`.
    {
      name: "torrentmate-web",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "web",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      // 30 s grace before SIGKILL — covers uvicorn graceful shutdown
      // (active WS connections closed, event loop drained) + context
      // close (provider_registry, acquire) + shutdown log.
      kill_timeout: 30000,
      // Unbuffered stdout + the single canonical config dir shared by all clones.
      // PERSONALSCRAPER_PM2_NAME enables POST /api/config/restart-web (S4) to
      // target this app; unset it to disable the endpoint (404 + hidden button).
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        PERSONALSCRAPER_PM2_NAME: "torrentmate-web",
        // A new account starts in the project's configured language (the
        // operator, 2026-10-05): set here, not inherited from PM2's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    // TorrentMate web UI — STAGING (tm-staging.iznogoudatall.xyz, port 8711).
    // Runs from the staging clone (~/staging/torrentmate) with its OWN venv. Shares
    // the SAME real config dir as prod (where web.port=8710), so the port is
    // overridden on the CLI: `web --port 8711`. PERSONALSCRAPER_WEB_ROLE=staging →
    // 403 on every mutating endpoint (config S4 + pipeline S2 + maintenance S3, via
    // the shared require_not_staging guard). Web ONLY — no crons/watcher on staging.
    {
      name: "torrentmate-web-staging",
      script: "/Users/izno/staging/torrentmate-venv/bin/personalscraper",
      args: "web --port 8711",
      interpreter: "none",
      cwd: "/Users/izno/staging/torrentmate",
      autorestart: true,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        PERSONALSCRAPER_WEB_ROLE: "staging",
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    // ---- Continuous deployment (autodeploy poller) ----
    // Watches origin and redeploys a clone when its tracked branch advances:
    //   prod    advances → scripts/deploy.sh          (prod clone ~/deploy/torrentmate)
    //   staging advances → scripts/deploy-staging.sh  (staging clone ~/staging/torrentmate)
    // Both move only through scripts/promote.sh, by fast-forward (docs/features/git-flow).
    // Runs from the PROD clone (prod) so the poller itself is not driven by the dev
    // checkout's branch. This is a shell script (not the Python CLI), so interpreter
    // is /bin/bash. 60 s loop (AUTODEPLOY_INTERVAL); restart_delay backs a crashed
    // poller off by 60 s so a persistent failure does not hot-loop PM2.
    {
      name: "torrentmate-autodeploy",
      script: "./scripts/autodeploy-poll.sh",
      interpreter: "/bin/bash",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
    },

    // ---- Machine guard (B-703) ----
    // Looks at the one-minute load once a minute; after three minutes in a row above the
    // machine's capacity it logs the heaviest process trees and kills the trees that run
    // from an agent checkout or scratchpad — never a service, never a `claude` process —
    // leaving `GUARD KILLED` lines in ~/Library/Logs/machine-guard.log. A long-lived loop
    // (`--loop`), not `cron_restart`, for the reason the scheduled jobs below give. A
    // standalone stdlib script, run by the prod venv's Python from the prod clone.
    {
      name: "torrentmate-machine-guard",
      script: "./scripts/machine_guard.py",
      args: "--loop",
      interpreter: "/Users/izno/deploy/torrentmate-venv/bin/python",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },

    // ---- Scheduled jobs (one `schedule` loop per job, autorestart: true) ----
    // All run from the PROD clone binary + cwd, with the canonical config dir passed
    // explicitly. Decoupled from the dev checkout branch.
    //
    // NO `cron_restart`: PM2 6.0.8's cron ticks TWICE around a boundary (15:14:59 then
    // 15:15:00) and its second tick SIGINT-kills the run the first just started
    // (measured 2026-10-02: 25 health-check, 4 search, 4 grab, 1 follow-detect runs cut).
    // `schedule --cron EXPR -- JOB` (personalscraper/scheduler.py) is one long-lived loop
    // that runs JOB at each boundary, to its end, never twice at once; PM2 only keeps it
    // alive. `kill_timeout` lets a stop reach a running job before SIGKILL.
    // Cadences: index-full Mon 01:00 (~22 min), index-enrich Sun 04:30 (off-peak),
    // backfill-ids Sun 05:00 (after enrich), follow-detect daily 03:00, search 03:10 and
    // 15:10, grab 03:20 and 15:20 (after search; the 15:20 retries backed-off items),
    // health-check hourly at :15, seed-sweep hourly at :45.

    // The ONLY mode that retires a file the filesystem no longer has: miss strikes
    // are raised in `full` alone (quick/incremental do not walk every file, so
    // striking there would mark visited-but-not-walked rows as missed), and three
    // strikes tombstone a row. Nothing had ever scheduled it, so ~838 rows for
    // paths deleted or renamed months ago sat in the index indefinitely. Three
    // Mondays retire a given row.
    //
    // Monday 01:00, measured rather than guessed — a full walk of the library took
    // 22 min 00 on 2026-09-04 (97 672 files: 5 min 15 of library-wide item staging,
    // then disk_1's 16 min 44 as the critical path while the other three share the
    // second worker). That leaves 1 h 38 before `follow-detect` at 03:00, and the
    // weekly 05:00 reboot reclaims the wired memory the walk grows — which is why
    // Monday small hours beat Sunday evening.
    //
    // `--no-budget` is not decoration: 22 min against the 1800 s default leaves 27 %,
    // and a slower night would truncate the walk. A truncated walk no longer strikes
    // anything (the run-level guard in `library_index_command`), so the failure mode
    // is a wasted pass rather than a false tombstone — but a pass that completes is
    // the point of scheduling one.
    //
    // `--wait-for-lock 600` because the watch daemon's post-dispatch scans take the
    // indexer writer lock at unpredictable times; the default 0 would abandon the
    // run instead of waiting. The only neighbour at 01:00 is the hourly health check
    // at :15, which merely stats `pipeline.lock`.
    {
      name: "personalscraper-index-full",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "schedule --cron '0 1 * * 1' -- library-index --mode full --no-budget --wait-for-lock 600",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    {
      name: "personalscraper-index-enrich",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "schedule --cron '30 4 * * 0' -- library-index --mode enrich --budget 1800 --wait-for-lock 0",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    {
      name: "personalscraper-backfill-ids",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "schedule --cron '0 5 * * 0' -- library-backfill-ids",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    // ---- Follow → auto-acquisition (three-pass: detect → search → grab) ----
    // detect enqueues newly-aired episodes as wanted; search probes tracker
    // availability for each wanted item; grab walks known-available items,
    // selects the top-ranked candidate and adds it to qBit.
    {
      name: "personalscraper-follow-detect",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "schedule --cron '0 3 * * *' -- follow detect",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    // the search pass states tracker availability between detect (03:00) and grab (03:20)
    // — grab then only walks known-available items.
    {
      name: "personalscraper-search",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "schedule --cron '10 3,15 * * *' -- search",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    {
      name: "personalscraper-grab",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "schedule --cron '20 3,15 * * *' -- grab",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      kill_timeout: 30000,
      // 03:20 daily (after detect) + 15:20 to retry backed-off items sooner.
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    // ---- Proactive health monitor ----
    // Hourly liveness + log-anomaly check; alerts Telegram on any anomaly the
    // pipeline's own event alerting does not cover (dead watcher, stuck lock).
    {
      name: "personalscraper-health-check",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "schedule --cron '15 * * * *' -- health-check",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },

    // ---- Seed-obligation sweep ----
    // Stamps `satisfied_at` once a torrent's seed-time floor (or ratio, +0.1 margin) is
    // reached and `released_at` once it stayed gone from the client for 30 min, then emits
    // the matching events. Hourly because the floors are days long and a release needs the
    // torrent absent over two passes; minute :45 keeps clear of the acquisition crons (:00,
    // :10, :20 of 03h/15h) and the health check (:15). Reads qBittorrent once per pass.
    {
      name: "personalscraper-seed-sweep",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "schedule --cron '45 * * * *' -- seed sweep",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: true,
      restart_delay: 60000,
      kill_timeout: 30000,
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/.torrentmate/config",
        // The operator's Telegram is French and the engine defaults to English
        // (i18n DEFAULT_LANGUAGE): pinned here rather than inherited from the PM2 daemon's LANG.
        PERSONALSCRAPER_LANG: "fr",
      },
    },
  ],
};
