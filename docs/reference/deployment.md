# Deployment discipline — only `main` is ever served

**Operator rule (2026-06-21):**

> On ne déploie QUE `main`. Si c'est déployé, c'est sur `main`. Pour déployer,
> on met sur `main` d'abord.

## Why this rule exists

The web SPA build lives in `src/kanbanmate/webui/`, which is **gitignored**, and
Vite builds it with `emptyOutDir: true` (`web/vite.config.js`). So a plain
`npm run build` from a dirty or non-`main` working tree (1) serves code that is
not committed anywhere and (2) wipes the previous build. On 2026-06-21 a batch of
UI work was lost exactly this way — built + served from an uncommitted working
tree, then overwritten by a rebuild. Git could never see it because it was never
committed.

## The guardrails (defense in depth)

1. **`scripts/deploy.sh` — the only sanctioned deploy path.** Refuses to build
   unless the working tree is **clean `main`**, fully **in sync with
   `origin/main`**. Then builds, **stamps the served commit** into
   `src/kanbanmate/webui/BUILD_COMMIT`, reinstalls the editable package, and
   restarts the PM2 apps. Never run `npm run build` + `pm2 restart` by hand.

2. **Commit stamp.** `BUILD_COMMIT` records the exact SHA that is live, so "what
   is deployed" is always answerable.

3. **`scripts/verify-deploy.sh` — drift detector (read-only).** Flags a deploy
   clone that is off-main, dirty, or whose `BUILD_COMMIT` ≠ `origin/main`. Run it
   from cron / `kanban doctor` / the kanban-monitor sweep.

4. **Dedicated deploy clone (structural).** The PM2 apps run from a clone that is
   used **only** for deployment — never for development. It only ever advances via
   `git pull --ff-only origin main` followed by `scripts/deploy.sh`. All
   development happens in `~/dev/KanbanMate` and its git worktrees. This makes it
   _physically impossible_ to serve non-`main` code: the deploy clone has no dev
   state to leak.

## How to deploy

```bash
cd <deploy-clone>
git pull --ff-only origin main      # advance to the latest main
./scripts/deploy.sh                 # refuses unless clean+main+synced, then builds+restarts
./scripts/verify-deploy.sh          # confirm live == origin/main
```

## How to ship a change

Put it on `main` first (branch → PR → squash-merge), then deploy. There is no
other path: `deploy.sh` will refuse anything that is not committed-and-pushed to
`main`.
