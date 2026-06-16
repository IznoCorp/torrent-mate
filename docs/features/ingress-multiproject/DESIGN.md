# DESIGN — ingress-multiproject (webhook ingress + config switch + multi-org + multi-project)

> Codename: **ingress-multiproject**. Branch `feat/ingress-multiproject`. SemVer **0.4.0 → 0.5.0**
> (minor — additive, N=1 back-compat preserved). GitHub App is OUT (deferred to ticket #26 — the
> webhook uses a plain shared secret + the existing PAT). Grounded against HEAD `8ab3d8e` (v0.4.0).

## 0. Summary & headline decision

Three capabilities, one feature: (a) **webhook ingress** as the config-switchable default with a
**polling fallback**; (b) **multiple GitHub orgs**; (c) **multiple projects per daemon**.

The single most important decision, which makes the feature small and low-risk:

> **The webhook receiver does NOT synthesize Transitions or a fake `BoardSnapshot`. It is a trigger
> that wakes the daemon to take a fresh real snapshot.** GitHub `projects_v2_item` payloads do not
> carry the Status column value reliably, and the engine's `diff(persisted, snapshot)` is already
> the authoritative "what moved" computation. So `kanban serve` verifies the HMAC, identifies which
> **project** the event belongs to, and **bumps that project's runtime-root nudge sentinel** — the
> EXACT cockpit `IntentStore.nudge_daemon` → `_interruptible_sleep` early-return mechanism. The
> daemon then runs its normal `tick → snapshot → diff → decide → execute`. This is idempotent by
> construction (a webhook nudge and a poll sweep converge on the same diff — no double-fire).

## 1. What shipped vs the original two-PR plan

The original design proposed a documented TWO-PR sequence (PR1 = multi-project/org/config-switch;
PR2 = the webhook receiver). **Both landed in this single feature branch** as two coherent commit
groups — PR2's receiver is genuinely small because it only nudges (it reuses the proven
nudge/sleep path), so deferring it to a follow-up branch was unnecessary. Everything implemented is
complete + tested; nothing is half-wired.

## 2. Registry generalization (N projects, N orgs, N=1 back-compat)

`ProjectEntry` (`cli/init.py`) gains four OPTIONAL defaulted fields so an OLD-shaped `projects.json`
loads unchanged (rule <1.0, no migration):

```python
org: str = ""          # derived from repo.split("/", 1)[0] when "" (ProjectEntry.owner())
enabled: bool = True   # pause one project without de-registering it
ingress: str = "webhook"  # per-project switch; "webhook" | "polling"
token_ref: str = ""    # "" → shared <root>/token; else <root>/tokens/<token_ref>
```

`_load_registry` reads them via `.get(..., default)` (back-compat). The registry stays keyed by
`project_id`.

**NEW pure module `core/registry_resolve.py`** (no I/O — operates on the loaded dict): a
`ProjectEntryLike` read-only Protocol + generic resolvers `resolve_by_project_id` /
`resolve_by_repo` / `resolve_by_issue(repo_hint)` / `enabled_entries` / `safe_project_id`. The
`len != 1` raises in `daemon/loop._wiring_from_registry` and `bin/_clone_config.resolve_entry` are
REMOVED — both generalize to N entries. N=1 is the special case: zero behaviour change, no pin/hint
required.

## 3. Per-project tick + per-project store namespacing

**NEW `daemon/sweep.py`** — `sweep_projects(wirings, state_by_project, …) -> SweepResult`: the run
loop builds `list[WiringConfig]` (one per ENABLED entry) and runs `run_one_tick` per project
**sequentially**, each with its own `PersistedState` diff baseline + circuit-breaker + per-project
heartbeat (`<root>/projects/heartbeats/<safe(pid)>.heartbeat`). A failing project never trips a
healthy sibling; a daemon-level rollup feeds the loop's idle clock + back-off. `loop.py` keeps the
lock/signal/config-reload/sleep skeleton and calls `sweep_projects`.

**Per-project store sub-root (the collision fix)** — the flat `<root>/state/<issue>.json` layout
collides across projects (two repos, issue #5). For N>1 each project's `FsStateStore` is rooted at
`<root>/projects/<safe(project_id)>/`; **N=1 keeps the legacy flat layout** (`state_root=""` →
zero path change for the deployed daemons). The daemon-wake **nudge sentinel** stays at the runtime
root (`FsStateStore(root, nudge_root=runtime_root)`) — one daemon, one sleep, one wake — while the
per-project intent QUEUE lives under the sub-root (each project drains its own collision-free
queue). `WiringConfig` gains `state_root` / `multi_project` / `ingress`.

## 4. Webhook receiver — `kanban serve` (NEW `http/` entrypoint layer)

`http` is a NEW top entrypoint (added to the layering guard: `"http": ["daemon", "bin"]` — it may
import app/adapters/core AND the `cli.init` registry loader exactly as `daemon` does, but not the
daemon/bin sibling entrypoints; `core` stays pure). Stdlib `http.server.ThreadingHTTPServer` (no new
dependency). Hardening: bounded body read (Content-Length required; absent/chunked → 411; > 1 MiB →
413), per-connection socket timeout on each ACCEPTED connection (the slow-loris guard — the
listening-socket timeout does not propagate to accepted sockets), method/path allow-list (only
`POST /webhook` + `GET /healthz`; an unknown path → 404, a known path with a disallowed method →
405 with an `Allow` header, never the stdlib default 501), a REAL webhook secret required at start
(an empty/comment-only placeholder is refused — its bytes are public in the source), loopback bind
by default (operator fronts TLS via their reverse proxy), non-root + unprivileged port (8765), fixed
response bodies (no reflection).

**HMAC** (NEW pure `core/webhook_sig.py`): `hmac.compare_digest("sha256="+hmac_sha256(secret, RAW
body))` on the raw bytes BEFORE any JSON parse; secret at `<root>/webhook_secret` (0600); refuse to
start without it. The receiver routes `project_node_id → resolve_by_project_id` (unknown → 202
no-op, never 4xx an unmanaged board) and bumps the runtime-root nudge. `kanban serve` is a SECOND
PM2 app (`kanban-serve`) alongside `kanban run` on ONE runtime root.

## 5. Config switch (webhook | polling) + polling fallback

`ingress` (per-project, default webhook) selects only the POLL CADENCE — the engine ALWAYS ticks.
`core/interval.daemon_base_seconds` picks the daemon base from the projects' modes: any `polling`
project → tight 10 s; an ALL-`webhook` daemon → the slow `webhook_fallback_seconds` (120 s) safety
sweep, accelerated to <1 s by the nudge. **Polling fallback is automatic + always-on** — if the
receiver is down or GitHub drops an event, the slow sweep still reconciles the board. Idempotency:
`diff` against the per-project persisted baseline yields a Transition only when the column differs,
so a webhook nudge + the safety sweep converge, never compound (the cockpit-intent guarantee).

## 6. Multi-org token model (NO GitHub App)

`token_ref=""` → the shared `<root>/token` (today's path; `$KANBAN_TOKEN` still wins). A non-empty
ref → `<root>/tokens/<ref>` (per-org/per-project PAT for SSO-gated / least-privilege orgs).
`validate_scopes` is unchanged (`{project, repo}`; no `admin:org_hook` — the operator creates the
webhook in the GitHub UI). `webhook_secret` is per-runtime-root, shared across projects in v1.

## 7. Helper entry-resolution + per-project pin

The launch exports `$KANBAN_PROJECT_ID` AND writes a worktree project pin (`.claude/kanban-project`,
`adapters.perms.write_project_pin`) ONLY in a multi-project deployment (`Deps.multi_project`); N=1
omits both → byte-identical command/worktree. `bin/_clone_config.resolve_entry` resolves the pinned
project (exact, no collision ambiguity), else the N=1 sole entry, else fails loud with the candidate
list. The kanban-* helpers (`kanban-move`/`-session-end`/`-progress`/`-done`/`-heartbeat`/
`-update-main`) target the per-project store sub-root via `bin/_pin.helper_store_root` (the km-root
invariant extended to multi-project). The export-prefix composition was lifted to the pure
`core/launch_env.build_env_prefix` and the launch context to `app/launch_context.build_launch_context`
to keep the at-ceiling `app/actions.py` under 1000 LOC.

## 8. CLI / install / doctor surface

- `kanban serve --root --host --port` → `http.serve.main`.
- `kanban init --ingress webhook|polling` records the per-entry value; seeds `<root>/webhook_secret`
  (0600 placeholder) when ingress=webhook. Registering a SECOND project is a second `kanban init`
  against the SAME root.
- `kanban install --serve` writes + starts the `kanban-serve` PM2 app; `kanban uninstall` deletes it.
- `kanban doctor` gains advisory checks (`cli/doctor_ingress.py`): webhook-secret presence/perms +
  a multi-project registry summary (both ALWAYS PASS — ingress is config, not a launch gate).

## 9. Test plan (delivered)

`core/registry_resolve` (by-id/repo/issue + collision + N=1 + safe slug + collision-resistant slug),
HMAC verify (valid/tampered/missing/wrong-secret), `daemon_base_seconds`, `daemon/sweep` (per-project
state/isolation/probe-failure/heartbeat + per-project back-off min/max), `_wirings_from_registry`
(N=1 flat / N>1 sub-roots / disabled-skip / token_ref / old-shaped / config.yml override), store
namespacing (same issue two projects, daemon-level nudge), `http/serve` (202+nudge / unknown-202 /
401 / 411 / 413 / 404 / 405 disallowed-method / slow-loris accepted-socket drop / placeholder-secret
refusal / ping / healthz / start-time guards), per-entry agent-helper token (`resolve_entry_token`),
project-aware CLI selector (`--project`/`--repo`; N=1 flagless, N>1 fail-loud), `core/launch_env`,
`cli/doctor_ingress`. All bin-helper + loop tests updated to the sweep architecture. `make check`
green (full suite; the exact test count is intentionally not pinned — it is brittle); every module
< 1000 LOC.

## 10. DESIGN / IMPLEMENTATION delta

New modules: `core/registry_resolve.py`, `core/webhook_sig.py`, `core/launch_env.py`,
`daemon/sweep.py`, `http/__init__.py`, `http/serve.py`, `app/launch_context.py`,
`cli/doctor_ingress.py`. Changed: `cli/init.py` (4 schema fields + owner() + `--ingress` + secret
seed; len!=1 raise gone via the list builder), `daemon/loop.py` (`_load_wirings` /
`_wirings_from_registry` / `_load_entry_token` / `_effective_interval` + sweep-based run loop),
`app/wiring.py` (state_root / multi_project / ingress + nudge_root threading),
`adapters/store/fs_store.py` + `fs_intents.py` (nudge_root), `adapters/perms.py` (write_project_pin),
`app/actions.py` (multi_project Deps field + project pin + env-prefix/launch-context extraction),
`bin/_pin.py` + `_clone_config.py` + the 8 `bin/kanban_*.py` helpers (project-aware resolution),
`cli/app.py` (`serve` + `init --ingress` + `install --serve`), `cli/install.py` (second PM2 app +
secret seed), `cli/doctor.py` (2 ingress checks), `tests/test_layering.py` (http layer). ROADMAP:
"Optional webhook ingress adapter" + "Multi-org support" moved to Implemented; "GitHub App upgrade"
stays deferred → ticket #26.
