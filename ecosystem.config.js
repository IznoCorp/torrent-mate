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
//   prod    = ~/deploy/torrentmate   — tracks `main` (autodeploy). Runs the web UI AND
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
//   config dir : /Users/izno/dev/PersonalScraper/config

module.exports = {
  apps: [
    // ---- Daemons (autorestart: true) ----

    // The watcher daemon — PROD. Runs from the prod clone (main), NOT the dev checkout.
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
        PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
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
        PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
        PERSONALSCRAPER_PM2_NAME: "torrentmate-web",
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
        PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
        PERSONALSCRAPER_WEB_ROLE: "staging",
      },
    },

    // ---- Continuous deployment (autodeploy poller) ----
    // Watches origin and redeploys a clone when its tracked branch advances:
    //   main    advances → scripts/deploy.sh          (prod clone ~/deploy/torrentmate)
    //   staging advances → scripts/deploy-staging.sh  (staging clone ~/staging/torrentmate)
    // Runs from the PROD clone (main) so the poller itself is not driven by the dev
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

    // ---- Scheduled jobs (autorestart: false, cron_restart) ----
    // All run from the PROD clone binary + cwd, with the canonical config dir passed
    // explicitly. Decoupled from the dev checkout branch.

    {
      name: "personalscraper-index-enrich",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "library-index --mode enrich --budget 1800 --wait-for-lock 0",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: false,
      cron_restart: "30 4 * * 0", // Sundays 04:30 local — off-peak
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
      },
    },

    {
      name: "personalscraper-backfill-ids",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "library-backfill-ids",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: false,
      cron_restart: "0 5 * * 0", // Sundays 05:00 local (after enrich)
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
      },
    },

    // ---- Follow → auto-acquisition (Follow D3) ----
    // detect aired episodes for followed series → enqueue as wanted, then grab
    // searches the trackers + adds the exact-episode top candidate to qBit.
    {
      name: "personalscraper-follow-detect",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "follow detect",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: false,
      cron_restart: "0 3 * * *", // 03:00 daily — enqueue newly-aired episodes
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
      },
    },

    {
      name: "personalscraper-grab",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "grab",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: false,
      // 03:20 daily (after detect) + 15:20 to retry backed-off items sooner.
      cron_restart: "20 3,15 * * *",
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
      },
    },

    // ---- Proactive health monitor ----
    // Hourly liveness + log-anomaly check; alerts Telegram on any anomaly the
    // pipeline's own event alerting does not cover (dead watcher, stuck lock).
    {
      name: "personalscraper-health-check",
      script: "/Users/izno/deploy/torrentmate-venv/bin/personalscraper",
      args: "health-check",
      interpreter: "none",
      cwd: "/Users/izno/deploy/torrentmate",
      autorestart: false,
      cron_restart: "15 * * * *", // hourly at :15
      env: {
        PYTHONUNBUFFERED: "1",
        PERSONALSCRAPER_CONFIG: "/Users/izno/dev/PersonalScraper/config",
      },
    },
  ],
};
