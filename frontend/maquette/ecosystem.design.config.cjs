// PM2 declaration for the design host — tm-design.iznogoudatall.xyz.
//
// It serves the prototype straight out of THIS working tree, deliberately: the
// point of a permanent design host is to show the design as it stands, not a
// snapshot someone has to remember to refresh. A stale reference is worse than
// no reference, because it is trusted.
//
// The consequence is worth knowing: checking this tree out on a branch that
// does not carry the prototype takes the site down to an explanatory 503, and
// coming back puts it up again. The server holds no state of its own.
//
// Port 8712. NEVER 8710 or 8711 — the reverse proxy routes production and
// staging there, and binding one of them would take the real app off the air.
module.exports = {
  apps: [
    {
      name: "torrentmate-design",
      script: "/Users/izno/dev/PersonalScraper/frontend/maquette/serve.py",
      args: "8712",
      interpreter: "/Users/izno/.pyenv/versions/3.11.9/bin/python3",
      cwd: "/Users/izno/dev/PersonalScraper/frontend/maquette",
      autorestart: true,
      min_uptime: "30s",
      exp_backoff_restart_delay: 200,
      max_restarts: 15,
      max_memory_restart: "256M",
    },
  ],
};
