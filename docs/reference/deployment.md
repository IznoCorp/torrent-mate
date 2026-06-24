# Deployment topology — only `main` is ever served

**Operator rule (2026-06-21):**

> On ne déploie QUE `main`. Si c'est déployé, c'est sur `main`. Pour déployer,
> on met sur `main` d'abord.

KanbanMate self-hosts: the production daemon orchestrates the `kanban-mate` board
itself. Deployment therefore has to be both **safe** (never serve uncommitted or
non-`main` code) and **continuous** (a merge to `main` should reach prod without
a manual step). This page describes the actual topology — three SSH clones, the
autodeploy poller, the PM2 apps, the version-sync points, and the guardrails.

## Three clones, three roles

The repo is cloned three times on the host, each with a distinct, non-overlapping
purpose. PM2 never serves from the development clone.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ~/dev/KanbanMate          DEVELOPMENT — branches + git worktrees.          │
│                           PM2 NEVER serves from here. All feature work,    │
│                           ticket worktrees, and experiments live here.     │
├──────────────────────────────────────────────────────────────────────────┤
│ ~/deploy/kanban-mate      PROD — pinned to `main`. PM2 serves from HERE.   │
│                           Advances only via the autodeploy poller (or a    │
│                           manual `git pull --ff-only origin main` +        │
│                           scripts/deploy.sh). No dev state to leak.        │
├──────────────────────────────────────────────────────────────────────────┤
│ ~/staging/kanban-mate     STAGING — tracks branch `staging`. PM2 serves    │
│                           the UI from here. Lets you test not-yet-merged   │
│                           work against the REAL prod board (no test board).│
└──────────────────────────────────────────────────────────────────────────┘
```

Because the prod clone is only ever advanced to `main` by `scripts/deploy.sh`
(which refuses a dirty or non-`main` tree, see below), it is _physically
impossible_ to serve non-`main` code from prod: there is no dev state to leak.

## PM2 apps

Each clone runs from its own Python venv (`~/deploy/venv`, `~/staging/venv`). The
PM2 process names are:

| App                     | Clone            | Command                                   | Listens          | Public                                                      |
| ----------------------- | ---------------- | ----------------------------------------- | ---------------- | ----------------------------------------------------------- |
| `kanban-km`             | `~/deploy/...`   | `kanban run --root ~/.kanban-km`          | —                | (daemon — polls + reconciles)                               |
| `kanban-km-serve`       | `~/deploy/...`   | `kanban serve --root ~/.kanban-km`        | `127.0.0.1:8765` | `https://km.iznogoudatall.xyz` (webhook ingress, via Caddy) |
| `kanban-km-config`      | `~/deploy/...`   | `kanban config serve --root ~/.kanban-km` | `127.0.0.1:8796` | `https://km.iznogoudatall.xyz` (KanbanMateUI, via Caddy)    |
| `kanban-staging-config` | `~/staging/...`  | `kanban config serve`                     | `127.0.0.1:8797` | `https://km-staging.iznogoudatall.xyz`                      |
| `kanban-autodeploy`     | `~/deploy/...`\* | `scripts/autodeploy-poll.sh`              | —                | (CD poller — see below)                                     |

- The running poller executes the **prod clone's** copy of `autodeploy-poll.sh`,
  so a fix to the poller only takes effect once it is on `main` and the
  `kanban-autodeploy` app is restarted.

The three prod apps are created by `scripts/bootstrap-pm2.sh` (all three are
`kanban run|serve|config serve --root ~/.kanban-km`). Caddy fronts both prod HTTP
apps on one domain: `/webhook` + `/healthz` → `:8765`, everything else → `:8796`.
Staging carries an amber **STAGING** frame.

> Legacy note: an old `kanban` daemon (driving `~/.kanban` for a separate board)
> was decommissioned and `pm2 delete`d. `scripts/deploy.sh` still _opportunistically_
> restarts a `kanban` app if one exists (its restart loop tolerates a missing app),
> but it is not part of the canonical set above.

## Continuous deployment — the autodeploy poller

`scripts/autodeploy-poll.sh` runs as the PM2 app `kanban-autodeploy`, looping
every `AUTODEPLOY_INTERVAL` (default **60 s**; `--once` for a single pass). Each
pass, for both clones, it:

1. `git remote update --prune origin` (fetch all refs).
2. Compares the clone's `HEAD` to its tracked remote tip (`origin/main` for prod,
   `origin/staging` for staging). If equal → nothing to do.
3. Otherwise: checkout the tracked branch, **`git reset --hard origin/<branch>`**,
   then run that clone's deploy script (`scripts/deploy.sh` for prod,
   `scripts/deploy-staging.sh` for staging).

So:

```
push to `main`    → prod    (~/deploy/kanban-mate)  auto-redeploys within ~60 s
push to `staging` → staging (~/staging/kanban-mate) auto-redeploys within ~60 s
```

**Why `reset --hard`, not `pull --ff-only`:** `staging` is intentionally
force-pushed (you push a rebased feature branch onto it), so its history diverges
and a fast-forward-only pull aborts — the env then silently never updates. A hard
reset to the remote tip deploys cleanly regardless. `main` only ever
fast-forwards, so the hard reset is equivalent there. The deploy scripts refuse a
dirty tree, so a clone never carries local work that a reset would discard.

> Historical bug (fixed 2026-06-21): the old poller used `git pull --ff-only`,
> which printed `ff-only pull failed (diverged) — skipping` and silently froze
> staging on a force-pushed branch. The fix is the `reset --hard` above. Because
> the running poller executes the **prod clone's** copy, the fix only took effect
> once it was on `main` and `kanban-autodeploy` was restarted.

The poller **requires SSH remotes** (silent / non-interactive) — HTTPS + the git
credential manager would pop a credential dialog every pass.

## scripts/deploy.sh — the only sanctioned prod deploy

`scripts/deploy.sh` is the single sanctioned path that builds and serves prod. It
enforces the deployment invariant with three hard guards, then builds, stamps,
and restarts:

1. **Guard 1 — must be on `main`.** Any other branch is refused.
2. **Guard 2 — clean working tree.** Any uncommitted change is refused (no
   uncommitted code can ever be served).
3. **Guard 3 — local `main` == `origin/main`.** It `git fetch`es (30 s timeout)
   and refuses if the local SHA differs from the remote (no un-pushed / diverged
   code). The fix is `git pull --ff-only origin main` first.

Then it:

- builds the SPA reproducibly from source: `( cd web && npm ci && npm run build )`
  (Vite builds into `src/kanbanmate/webui/` with `emptyOutDir: true`);
- **stamps the served commit** into `src/kanbanmate/webui/BUILD_COMMIT` so "what
  is live" is always answerable;
- `pip install -e .` (reinstall the editable package — picks up CLI/engine
  changes);
- `pm2 restart` the prod apps + `pm2 save`.

```bash
cd ~/deploy/kanban-mate
git pull --ff-only origin main      # advance to the latest main
./scripts/deploy.sh                 # refuses unless clean+main+synced, then builds+restarts
./scripts/verify-deploy.sh          # confirm live == origin/main
```

`scripts/verify-deploy.sh` is a read-only drift detector: it flags a deploy clone
that is off-`main`, dirty, or whose `BUILD_COMMIT` ≠ `origin/main` HEAD. Exit 0 =
no drift, exit 1 = drift (described on stderr). Wire it into cron / `kanban
doctor` / the kanban-monitor sweep.

## scripts/deploy-staging.sh — the non-`main` playground

`scripts/deploy-staging.sh` builds the **current branch** of the staging clone and
restarts only `kanban-staging-config`. Unlike prod it serves whatever branch is
checked out — that's the point. It still **refuses a dirty tree** (only ever serve
committed code). Like prod it `npm ci && npm run build`, writes `BUILD_COMMIT`
(here `<branch> @ <sha>`), `pip install -e .`, and restarts the staging UI.

Staging points at the **REAL prod root** `~/.kanban-km`: the prod daemon does the
real work, so a card move / config edit made in the staging UI applies **for real**
on the prod board. There is no test board. Safety rests on one design rule (see
`docs/reference/repo-safety.md`): a feature must keep the on-disk state/config
format **backward-compatible**, so the feature build (staging) and the prod daemon
(`main`) read and write `~/.kanban-km` safely.

### Testing not-yet-merged work on staging

Push your branch onto the `staging` branch (force-push is expected — staging is a
disposable rebase target):

```bash
git push origin <your-branch>:staging --force-with-lease
```

Within ~60 s the poller hard-resets the staging clone and redeploys. Open
`https://km-staging.iznogoudatall.xyz` (same login as prod) and **confirm** the
served asset hash or `/api/health` version changed:

```bash
curl -s --connect-timeout 5 --max-time 10 \
  https://km-staging.iznogoudatall.xyz/ | grep -o 'index-[A-Za-z0-9_-]*\.js'
```

**Reliable manual staging deploy** — use when the poller is mid-rollout or stale,
or when you want a deterministic, immediate deploy. Deploy straight from the
staging clone:

```bash
cd ~/staging/kanban-mate \
  && git remote update --prune origin \
  && git reset --hard origin/staging \
  && PATH="$HOME/staging/venv/bin:$PATH" bash scripts/deploy-staging.sh
```

Use `git remote update`, **not** `git fetch` — the repo's network-timeout hook
flags the bare word `fetch`. This touches only the staging clone +
`kanban-staging-config`, never prod.

## Version sync — bump all five on every release

The version string lives in **five** places and they must stay in lockstep
(current: `0.21.1`). Bump all five on every release, or `kanban doctor` / the
plugin marketplace will report drift:

| #   | File                                | Field                 |
| --- | ----------------------------------- | --------------------- |
| 1   | `VERSION`                           | (whole file)          |
| 2   | `pyproject.toml`                    | `version = "..."`     |
| 3   | `src/kanbanmate/__init__.py`        | `__version__ = "..."` |
| 4   | `.claude-plugin/marketplace.json`   | `"version": "..."`    |
| 5   | `plugin/.claude-plugin/plugin.json` | `"version": "..."`    |

SemVer bump rule (applied at `/implement:create-branch`): bugfix → Z+1, minor →
Y+1, major → X+1.

## The webui build is gitignored — rebuilt on every deploy

`src/kanbanmate/webui/` is in `.gitignore`. The SPA source lives in `web/`; Vite
builds it into `webui/` with `emptyOutDir: true`. Consequences:

- A plain `npm run build` from a dirty or non-`main` tree (1) serves code that is
  not committed anywhere and (2) wipes the previous build. On 2026-06-21 a batch
  of UI work was lost exactly this way. The deploy scripts make that impossible
  (clean-tree guard + `BUILD_COMMIT` stamp).
- The build is **never committed** — every deploy rebuilds it from `web/` source.
  Always commit the SPA _source_; nothing must live only in a working tree.

## Guardrails (defense in depth)

1. **Deploy only `main` to prod.** `scripts/deploy.sh` refuses anything that is
   not clean `main` synced with `origin/main`.
2. **Always commit.** Both deploy scripts refuse a dirty tree — nothing lives only
   in a working tree (the webui build is the cautionary tale).
3. **Never `npm run build` + `pm2 restart` by hand.** Use `scripts/deploy.sh`
   (prod) or `scripts/deploy-staging.sh` (staging). They build reproducibly from
   source and stamp `BUILD_COMMIT`.
4. **Dedicated prod clone (structural).** `~/deploy/kanban-mate` is used _only_
   for deployment — never for dev — so it has no dev state to leak.
5. **Keep on-disk state backward-compatible.** Staging and prod share
   `~/.kanban-km`; the feature build and the prod daemon must read/write the same
   files safely.
6. **Never delete a local branch** that isn't pushed AND merged to `main`
   (enforced by `hooks/reference-transaction`; activate per clone with
   `scripts/install-git-guards.sh`).

## How to ship a change

Put it on `main` first (branch → PR → squash-merge), then let CD deploy it (or run
`scripts/deploy.sh` manually). There is no other path to prod: `deploy.sh` refuses
anything not committed-and-pushed to `main`. To preview before merge, push your
branch onto `staging`.

Related: `docs/reference/repo-safety.md` (branch-deletion + git guards), CLAUDE.md
§ Deployment, Staging & CD.
