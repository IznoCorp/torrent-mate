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
      script: "/Users/izno/.pyenv/versions/3.12.4/bin/personalscraper",
      args: "watch",
      interpreter: "none",
      cwd: __dirname,
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      // 30 s grace before SIGKILL — covers 1 s interruptible-sleep slice
      // granularity + context close (acquire, provider_registry) + shutdown log.
      kill_timeout: 30000,
      // Unbuffered stdout so structured poll logs flush to the PM2 log file in
      // real time (Python block-buffers stdout when piped, hiding daemon logs).
      env: { PYTHONUNBUFFERED: "1" },
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
    // overridden on the CLI: `web --port 8711`. S4 enforces read-only via
    // PERSONALSCRAPER_WEB_ROLE=staging → 403 on every config write endpoint
    // (supersedes the S1-era "read-only by construction" assumption).
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
    // This is a shell script (not the Python CLI), so interpreter is /bin/bash.
    // 60 s loop (AUTODEPLOY_INTERVAL); restart_delay backs a crashed poller off
    // by 60 s so a persistent failure does not hot-loop PM2.
    {
      name: "torrentmate-autodeploy",
      script: "./scripts/autodeploy-poll.sh",
      interpreter: "/bin/bash",
      cwd: __dirname,
      autorestart: true,
      restart_delay: 60000,
    },

    // ---- Scheduled jobs (autorestart: false, cron_restart) ----

    {
      name: "personalscraper-index-enrich",
      script: "/Users/izno/.pyenv/versions/3.12.4/bin/personalscraper",
      args: "library-index --mode enrich --budget 1800 --wait-for-lock 0",
      interpreter: "none",
      cwd: __dirname,
      autorestart: false,
      cron_restart: "30 4 * * 0", // Sundays 04:30 local — off-peak
    },

    {
      name: "personalscraper-backfill-ids",
      script: "/Users/izno/.pyenv/versions/3.12.4/bin/personalscraper",
      args: "library-backfill-ids",
      interpreter: "none",
      cwd: __dirname,
      autorestart: false,
      cron_restart: "0 5 * * 0", // Sundays 05:00 local (after enrich)
    },

    // ---- Follow → auto-acquisition (Follow D3) ----
    // detect aired episodes for followed series → enqueue as wanted, then grab
    // searches the trackers + adds the exact-episode top candidate to qBit.
    {
      name: "personalscraper-follow-detect",
      script: "/Users/izno/.pyenv/versions/3.12.4/bin/personalscraper",
      args: "follow detect",
      interpreter: "none",
      cwd: __dirname,
      autorestart: false,
      cron_restart: "0 3 * * *", // 03:00 daily — enqueue newly-aired episodes
    },

    {
      name: "personalscraper-grab",
      script: "/Users/izno/.pyenv/versions/3.12.4/bin/personalscraper",
      args: "grab",
      interpreter: "none",
      cwd: __dirname,
      autorestart: false,
      // 03:20 daily (after detect) + 15:20 to retry backed-off items sooner.
      cron_restart: "20 3,15 * * *",
    },

    // ---- Proactive health monitor ----
    // Hourly liveness + log-anomaly check; alerts Telegram on any anomaly the
    // pipeline's own event alerting does not cover (dead watcher, stuck lock).
    {
      name: "personalscraper-health-check",
      script: "/Users/izno/.pyenv/versions/3.12.4/bin/personalscraper",
      args: "health-check",
      interpreter: "none",
      cwd: __dirname,
      autorestart: false,
      cron_restart: "15 * * * *", // hourly at :15
    },
  ],
};
