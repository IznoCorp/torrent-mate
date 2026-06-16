# Implementation Progress — ingress-multiproject (0.4.0 → 0.5.0)

> For Claude: read this file at session start. Current feature tracker.

**Feature**: ingress-multiproject — webhook ingress (config-switchable default, polling fallback) +
multiple GitHub orgs + multiple projects per daemon. The GitHub App is OUT (deferred to ticket #26;
the webhook uses a plain shared secret + the existing PAT).
**Version bump**: minor (Y+1) — 0.4.0 → 0.5.0 (additive; N=1 back-compat preserved).
**Branch**: `feat/ingress-multiproject`
**PR merge**: manual (human-only).
**Design**: `docs/features/ingress-multiproject/DESIGN.md`
**Master plan**: single feature branch — landed as two coherent commit groups (multi-project/org/
config-switch, then the webhook receiver).

Built in an isolated worktree + isolated venv (`/Users/izno/.pyenv/versions/3.12.4/bin/python`); the
live PM2 daemons (editable install from the MAIN worktree) were never touched, never restarted. The
existing single-project deployed config keeps working unchanged (the N=1 path is byte-identical).

## Headline decision

The webhook receiver does NOT synthesize Transitions — it verifies the HMAC, identifies the project,
and bumps the runtime-root nudge sentinel (the cockpit mechanism). The daemon then runs its normal
`tick → snapshot → diff → decide → execute`, idempotent by construction. Polling is never removed
(the always-on fallback; webhook mode polls slowly as a safety net).

## What shipped

| Area | Modules | Status |
|---|---|---|
| Registry generalization (N entries, N=1 collapse) | `cli/init.py` (4 fields + `owner()` + `--ingress` + secret seed) | DONE |
| Pure resolvers | NEW `core/registry_resolve.py` (Protocol + generic resolvers + `safe_project_id`) | DONE |
| Per-project sweep | NEW `daemon/sweep.py`; `daemon/loop.py` (`_load_wirings`/`_wirings_from_registry`/`_load_entry_token`/`_effective_interval` + sweep run loop) | DONE |
| Per-project store sub-roots + daemon-level nudge | `adapters/store/fs_store.py` + `fs_intents.py` (`nudge_root`); `app/wiring.py` (`state_root`) | DONE |
| Multi-org token model | `daemon/loop._load_entry_token` (`token_ref` → `<root>/tokens/<ref>`) | DONE |
| Config switch + polling fallback | `core/interval.daemon_base_seconds`; `WiringConfig.ingress`; `loop._effective_interval` | DONE |
| Helper project-aware resolution | `bin/_pin.py` (project pin + `helper_store_root`), `bin/_clone_config.py` (`resolve_entry`/`resolve_state_root`), 8 `bin/kanban_*.py` | DONE |
| Launch project pin + env export | `adapters/perms.write_project_pin`; `app/actions.py` (`Deps.multi_project`); NEW `core/launch_env.py` | DONE |
| Webhook receiver | NEW `http/__init__.py` + `http/serve.py`; NEW `core/webhook_sig.py`; `cli/app.serve`; layering guard | DONE |
| Install second PM2 app | `cli/install.py` (`kanban-serve` app + secret seed) | DONE |
| Doctor checks | NEW `cli/doctor_ingress.py` (webhook secret + registry summary); wired into `cli/doctor.py` | DONE |
| LOC-ceiling relief | NEW `app/launch_context.py` (extracted from actions.py: 1018 → 945) | DONE |

## Behaviour deltas (gate requirement)

- **One daemon now drives N projects across N orgs.** The run loop builds one `WiringConfig` per
  ENABLED registry entry and sweeps them sequentially (each with its own diff baseline +
  circuit-breaker + per-project heartbeat). A failing project never trips a healthy sibling.
- **Per-project store sub-roots fix the issue-number collision.** For N>1 each project's state lives
  under `<root>/projects/<safe(project_id)>/`; the daemon-wake nudge stays at the runtime root (one
  daemon, one wake). **N=1 keeps the legacy flat layout — zero path change for the deployed daemons.**
- **Webhook ingress as a sub-second nudge.** `kanban serve` (new `http/` layer) verifies the
  `X-Hub-Signature-256` HMAC, routes `project_node_id → resolve_by_project_id`, and bumps the
  runtime-root nudge. It never synthesizes Transitions; the daemon's normal tick + `cheap_probe`
  scope the work to the changed board. Idempotent (a webhook nudge + the safety sweep converge).
- **Config-switchable ingress + always-on polling fallback.** `ingress=webhook` (default) polls
  slowly (120 s safety sweep) and relies on the nudge; `ingress=polling` keeps the tight 10 s. The
  board never stalls even if the receiver is down.
- **Multi-org tokens without a GitHub App.** `token_ref=""` → shared `<root>/token`; a ref →
  `<root>/tokens/<ref>`. `validate_scopes` unchanged (`{project, repo}`; no `admin:org_hook`).
- **N=1 byte-identical.** No `state_root`, no `multi_project`, no `KANBAN_PROJECT_ID` export, no
  project pin, the tight 10 s cadence — the deployed single-project daemon behaves exactly as before.

## Phase gate

- `make check` → exit 0 (ruff + `ruff format --check` + mypy strict + the full pytest suite green
  (9 skipped / 1 deselected) + module-size guard — no module over the 1000-LOC hard ceiling;
  `actions.py` relieved 1018 → 945 via the `app/launch_context.py` extraction). Adversarial-review
  fixes (project-aware CLI, accepted-socket slow-loris guard, placeholder-secret refusal, per-entry
  agent-helper token, per-project back-off, collision-resistant slug, 405/404 + cleanups) added their
  own tests; the suite stays green (the exact count is intentionally not pinned here — it is brittle).
- `python -c "import kanbanmate"` → version `0.5.0`.
- All 5 version pins bumped (VERSION, pyproject, `src/kanbanmate/__init__.py`,
  `.claude-plugin/marketplace.json`, `plugin/.claude-plugin/plugin.json`); manifest lockstep test green.

## Deferred (reported, not silent)

- **GitHub App** → ticket #26 (the webhook uses a plain shared secret + the existing PAT, as the
  operator decided).
- **Concurrent per-project ticks** — the sweep is sequential (the proven single-tick semantics +
  bounded GitHub rate budget); concurrency is a noted future optimization.
- **Per-org webhook secret** — v1 uses one shared `<root>/webhook_secret`; a per-org secret is a
  trivial future refinement (the receiver verifies the single secret first).
