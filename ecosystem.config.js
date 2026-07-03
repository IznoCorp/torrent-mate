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
  ],
};
