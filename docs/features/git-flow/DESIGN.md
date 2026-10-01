# Git flow — `feature → develop → main → staging → prod`, and the deployment that follows it · DESIGN

This document draws the lot that changes how every pull request reaches production. It is written for a session that
has none of the context it was produced in. **Nothing live was touched to write it**: no PM2 restart, no ruleset or
repository setting, no branch on origin but `docs/git-flow`, nothing under `~/deploy` or `~/staging`. Every figure
carries the command that produced it, run from the worktree root (read-only).

**Written 2026-10-01, on `docs/git-flow` cut from `main` at `50fff4832`; his rulings on § 5 entered the same day.**
The lot follows PRs #672/#673 and comes before the « À traiter » lot ships.

## 0. The ruling

Source: the operator's decision round of 2026-10-01, backend question 8 and its two precisions
(`docs/reference/backend-brief.md` § 5 Q1 and § 4 « Decided »; `docs/reference/operator-method.md` § 3
« Environnements et back-end », the lines dated 10-01). Not reopenable. Quoted:

- « `feature → develop → main`. `develop` is deployed automatically on tm-design (tm-design = `develop` plus the lot
  in flight, merged on the fly); `main` holds everything validated — the orchestrator promotes validated features to
  it. »
- « `staging` is deployed VOLUNTARILY by him, only when a complete user story is ready for test users » — his words:
  « on déploie en staging que quand la user story est prête au complet ».
- « `prod` is deployed VOLUNTARILY after functional validation on staging; it is a branch carrying release tags,
  auto-deployed. »
- « Defaults kept, as he did not object: promotions are fast-forwards; a `hotfix/` branch cut from `prod` is merged
  back into `develop`. »
- « `staging` IS the preprod of ruling 23 » — his words: « l'env staging est bien la préprod ! » — « with its own
  data » (Q2: one file per environment by suffix; ONE `library.db` written by prod alone); Q4: the preprod runs the
  whole engine, « the read-only :8711 instance is retired, its port and host taken by preprod ».
- « Today's `/api` is v0; the new backend is served under `/api/v1` […] A v0 route is DEPRECATED as soon as its v1
  works: it answers a `Deprecation` header and is entered in a register, which is the cleanup list once v1 is fully
  deployed and validated. »
- « Consequence: today's CD — the autodeploy poller tracks `main` and deploys prod — changes to this flow. »

Read as one chain of fast-forwards, each arrow a different hand:

```text
feature/fix/docs ──PR, squash, auto-merge──▶ develop ──orchestrator, ff──▶ main ──HIM, ff──▶ staging ──HIM, ff──▶ prod
                                               │                                            │                     │
                                       tm-design (+ lot in flight)              tm-staging (preprod)      tm (prod), tag vX.Y.Z
hotfix/<x> cut from prod ──PR──▶ prod ;  prod ──merge commit──▶ develop
```

Ancestry is the invariant the whole flow keeps: `prod ⊆ staging ⊆ main ⊆ develop` (each branch's tip is an ancestor of
the next one's), broken only between a hotfix and its merge-back.

## 1. Today, measured

### 1.1 Branches and tags on origin

| Fact | Value | Command |
| --- | --- | --- |
| Long-lived branches | `main`, `staging`, `pr-assets` (review images, not code) | `gh api repos/IznoCorp/torrent-mate/branches --paginate --jq '.[].name'` |
| `staging` | `67ea6509b`, 2026-08-14, « Merge remote-tracking branch 'origin/main' into feat/shell-mobile »; 99 commits not on `main`, 244 on `main` not on it — DIVERGED | `git log -1 origin/staging`; `git rev-list --left-right --count origin/main...origin/staging` |
| Tags on origin | none | `gh api repos/IznoCorp/torrent-mate/tags` → `[]` |
| Version | `0.98.131`, a patch bump per PR | `grep __version__ personalscraper/__init__.py` |
| Merge rate | 132 commits on `main` since 2026-09-01 | `git log origin/main --since=2026-09-01 --oneline \| wc -l` |
| Open PRs | one, #672 `feat/maquette-desktop` → `main`, auto-merge armed | `gh pr list --base main --state open` |

### 1.2 Repository settings and the ruleset

`gh api repos/IznoCorp/torrent-mate` and `gh api repos/IznoCorp/torrent-mate/rulesets/15201125` (read-only):

- Default branch `main`; `delete_branch_on_merge=true`; `allow_auto_merge=true`; squash, merge and rebase allowed.
- ONE ruleset, `main` (id 15201125), target `~DEFAULT_BRANCH`, active: `deletion`; `pull_request` (0 approvals, all
  three methods); `copilot_code_review` (on push, not on drafts); `required_status_checks`, **strict** (the branch
  must be up to date), nine contexts: `licenses`, `lint`, `secrets`, `security`, `typecheck`, `design-gaps`,
  `coverage-merge`, `test`, `harness-full`. **`version-bump` is NOT required**: it runs and reports, it does not block
  a merge. No `non_fast_forward` rule.
- Bypass actor: the user `LounisBou` (id 34158993), mode `always`. Every agent pushes and merges with that account,
  so for this project's sessions the ruleset is a guard against the accidental only when a tool goes through a PR;
  a direct push is never refused. This shapes § 3.4: the teeth of a promotion live in the script, not the ruleset.

### 1.3 CI

- `.github/workflows/ci.yml`: `on: pull_request: branches: [main]`, types including `labeled`, `ready_for_review`. No
  `push` trigger. Every job carries the draft gate (`tests/scripts/test_ci_skips_draft_pull_requests.py` refuses a job
  without it). `concurrency: ci-${{ github.event.pull_request.number }}`.
- `version-bump` job: `scripts/check_version_bump.py --base "origin/${BASE_REF}"` — already relative to the PR's
  base, compares `__version__` as a tuple of ints (so `0.98.131.1 > 0.98.131` already holds).
- `coverage-merge` compares `fail_under` against `origin/${BASE_REF}` — already relative.
- `.github/workflows/harness-full.yml`: `pull_request: branches: [main]` + `workflow_dispatch`.
- `Makefile` `check`: `check_version_bump.py --base origin/main` — hard-coded `main`.

### 1.4 The CD and the clones

`pm2 jlist` (read-only) and `scripts/autodeploy-poll.sh`:

| PM2 app | cwd / script | Branch it runs | Port |
| --- | --- | --- | --- |
| `torrentmate-autodeploy` | `~/deploy/torrentmate/scripts/autodeploy-poll.sh`, every 60 s | prod clone's `main` | — |
| `torrentmate-web` | `~/deploy/torrentmate`, prod venv, `web` | `main` | 8710 (`tm.`) |
| `personalscraper-watch` + six crons (stopped between runs) | `~/deploy/torrentmate`, prod venv | `main` | — |
| `torrentmate-web-staging` | `~/staging/torrentmate`, staging venv, `web --port 8711`, `PERSONALSCRAPER_WEB_ROLE=staging` (403 on writes) | `staging` | 8711 (`tm-staging.`) |
| `torrentmate-design` | `~/dev/PersonalScraper/frontend/maquette/serve.py 8712` | the DEV checkout's branch (`main`) for `serve.py`; the built `design/dist` for the page | 8712 (`tm-design`) |
| `tm-design-follow` | `/Users/izno/dev/review-archive/tm-design-follow.sh`, every 120 s | line 1 of `review-archive/tm-design-lot.txt` (`main`) + line 2 (the lot in flight, `feat/maquette-desktop`) | — |

The poller's three arms (`one_pass`, lines 179–183):

1. prod: `git fetch origin main`; if advanced, `git pull --ff-only`, then `scripts/deploy.sh` — which refuses unless
   the branch is `main`, the tree clean and `HEAD == origin/main`; builds `frontend/`, stamps `BUILD_COMMIT` with the
   SHA, `pip install -e .`, `pm2 startOrRestart torrentmate-web`, then proves `/api/health` 200 and that
   `/api/version` serves the SHA (R27).
2. staging: `git fetch origin staging`; if advanced, `git reset --hard origin/staging` (staging is a playground a
   feature branch may force-push), then `scripts/deploy-staging.sh` — any branch, clean tree, stamp
   `"<branch> @ <sha>"`, restart `torrentmate-web-staging`, health on 8711.
3. design: restarts `torrentmate-design` when `serve.py`'s mtime is later than the process start.

tm-design is built OUTSIDE the poller: `tm-design-follow.sh` reads the two pushed heads by `ls-remote`, and
`review-archive/tm-design-serve-head.sh` checks out the base in the detached worktree `~/dev/worktrees/tm-design-build`,
merges the lot `--no-commit --no-ff` (a conflict serves the lot alone, logged « APERÇU EN CONFLIT »), builds the
maquette under `scripts/heavy.sh`, rsyncs into `~/dev/PersonalScraper/frontend/maquette/design/dist`, and proves the
served `build.json` equals the disk's. tm-design serves the maquette on mocks: no backend.

### 1.5 The habits that assume `main`

- `CLAUDE.md` « Commits and pull requests »: open READY, `gh pr merge <n> --auto --squash --match-head-commit <sha>`,
  `gh pr update-branch` after `main` moves; a worktree is removed once its PR is merged.
- `docs/reference/method.md`: « Push at every commit: tm-design shows him the work in flight »; a lot is done when its
  gates are green and one reader has looked at its screens on tm-design, « every major fixed before the merge ».
- `docs/production/web-ui.md` § Deploy Runbook, § Autodeploy poller, § ENV-SEP, `ecosystem.config.js`'s header
  comments: « prod tracks `main` », « staging tracks `staging` ».
- `tests/indexer/test_ecosystem.py` and `tests/scripts/test_autodeploy_design_restart.py` pin the poller app and its
  design arm; nothing tests the two branch arms.

## 2. The target, branch by branch

| Branch | Who writes it | How | What it triggers | Deployed where | Data |
| --- | --- | --- | --- | --- | --- |
| `feat/<c>`, `fix/<c>`, `docs/<c>` | an implementer | commits, pushed at every commit | CI on its PR into `develop`; tm-design when it is the lot in flight | tm-design (merged on the fly onto `develop`) | mocks |
| `develop` | GitHub, at a PR's merge | squash merge, auto-merge armed at PR open; a merge commit only for a hotfix's merge-back | tm-design rebuild (follower) | tm-design :8712 | mocks (tm-design has no backend) |
| `main` | the orchestrator | `scripts/promote.sh main <sha>` — fast-forward to a commit of `develop` whose lots are validated | nothing deploys | — | — |
| `staging` | any session ON HIS WORD (the orchestrator or any agent, DECIDED 1) | `scripts/promote.sh staging [<sha>]` — fast-forward to a commit of `main`, when a user story is complete | the poller: `deploy-staging.sh` | `~/staging/torrentmate`, :8711, `tm-staging.` | its own (`acquire-staging.db`, `app-staging.db`; `library.db` read-only) once K0 delivers Q2/Q4; until then today's read-only web |
| `prod` | any session ON HIS WORD (the orchestrator or any agent, DECIDED 1) | `scripts/promote.sh prod [<sha>]` — fast-forward to a commit of `staging`, then the tag `v<__version__>` | the poller: `deploy.sh`, plus the watcher and the crons (they run the prod clone) | `~/deploy/torrentmate`, :8710, `tm.` | prod's (`acquire.db`, `app.db`, `library.db` written) |
| `hotfix/<c>` | an implementer | cut from `prod`; PR into `prod` (squash); then merged back into `develop` | CI on its PR into `prod`; prod's deploy at its merge | prod | prod's |

Rules the table implies:

- **One writer per branch, one gesture each.** No PR ever targets `main` or `staging`. A PR targets `develop`, or
  `prod` for a hotfix.
- **Promotion is a fast-forward of an existing commit, never a new commit.** `main`, `staging` and `prod` therefore
  carry exactly the SHAs that were built and read upstream; the deploy builds the same tree that was promoted.
- **Validated** (for `main`) is the method's « lot done »: its gates green on the PR(s) and its one reader's round
  passed on tm-design, every major fixed. Phase PRs and fixes of a lot merge into `develop` as soon as their CI is
  green (that is what puts them on tm-design); the lot's last merged commit is promoted to `main` when its reader's
  round passes. A fast-forward promotes a PREFIX of `develop`: a commit of a lot not yet validated holds back
  everything merged after it. The orchestrator therefore keeps ONE lot at a time on `develop` beyond `main`; a fix
  that must reach `main` sooner goes in before the lot's first merge, or waits.
- **The version**: every PR into `develop` bumps the patch (`0.98.131 → 0.98.132`); promotions bump nothing. The
  release tag on `prod` is `v` + the `__version__` of the promoted commit (DECIDED 2). A hotfix bumps a fourth component
  from prod's version (`0.98.131 → 0.98.131.1`): it can never collide with a patch number `develop` has already used,
  and the merge-back takes `develop`'s (higher) version plus one patch (§ 3.7).
- **The API versions**: § 3.8.

## 3. What changes, file by file

### 3.1 `scripts/promote.sh` (new) — the only way `main`, `staging` and `prod` move

A plain script any session runs — the orchestrator or any agent (DECIDED 1); it keeps no state but origin's refs.
`scripts/promote.sh <main|staging|prod> [<sha>]`; `<sha>` defaults to the source branch's tip. Source of each target:
`main ← develop`, `staging ← main`, `prod ← staging`. `scripts/promote.sh tag` tags `prod`'s tip alone (rule 4), for
a hotfix that reached `prod` through its PR (§ 3.7). `scripts/promote.sh backport <c>` is a hotfix's merge-back
(§ 3.7 step 3): it merges `develop` into `prod`'s tip, pushes that merge to `backport/<c>` and opens its PR into
`develop` with auto-merge armed by the MERGE method; it refuses when `prod` is already an ancestor of `develop`
(nothing to bring back). A promotion refuses,
with one line saying why, unless ALL hold:

1. `<sha>` is on the source branch (`git merge-base --is-ancestor <sha> origin/<source>`).
2. The target's tip is an ancestor of `<sha>` — a fast-forward (this is what refuses a promotion while a hotfix is
   not yet merged back).
3. `main` only: every commit of `git rev-list --first-parent origin/main..<sha>` is the commit a merged PR into
   `develop` produced (`gh api repos/:owner/:repo/commits/<c>/pulls`), whose required checks concluded `success` at
   its head — the strict up-to-date policy on `develop` makes that head's tested tree the merged tree. A backport's
   merge commit brings, through its second parent, commits already on `prod`; they were checked on their own PR into
   `prod` and are not re-read. A commit with no PR (a bypass push) is refused by name.
4. `prod` only: `personalscraper/__init__.py`'s `__version__` at `<sha>` has no tag yet.

Then `git push origin <sha>:refs/heads/<target>` (no `--force`, ever), and for `prod` an annotated tag
`v<version>` on `<sha>`, pushed. It prints what moved (`old..new`, the commit count, the PR numbers) and, for
`staging`/`prod`, that the poller deploys within 60 s and how to read it (`/api/version`). `--dry-run` prints the
same without pushing. Tested in `tests/scripts/test_promote.py` against a bare remote and clones in `tmp_path`
(the PR-check arm stubbed through a `GH` command override), like `test_autodeploy_design_restart.py` drives the
poller.

### 3.2 `scripts/autodeploy-poll.sh`

- prod arm: `redeploy_if_advanced "$PROD_CLONE" prod pull …/deploy.sh` — tracks `prod`, strict fast-forward.
- staging arm: tracks `staging` with `pull` (fast-forward) instead of `reset`. `staging` is no longer a playground a
  feature branch force-pushes: it only fast-forwards. A non-fast-forward is now a fault to SEE (logged, pass
  skipped), never followed silently. The `reset` strategy and its comment go.
- design arm: unchanged.
- Header comment and the boot line: `deploy<-prod, staging<-staging`.
- `tests/scripts/test_autodeploy_branches.py` (new): `--once` against a bare remote and two clones — prod follows
  `prod` and ignores `main`; staging follows a fast-forward and REFUSES a diverged `staging` (logged, HEAD unchanged).

### 3.3 `scripts/deploy.sh`, `scripts/deploy-staging.sh`

- `deploy.sh`: guard 1 becomes « branch is `prod` », guard 3 « `HEAD == origin/prod` »; its header (« ONLY `main` IS
  DEPLOYED ») says `prod`. The stamp stays the bare SHA (R27 compares it with `/api/version`).
- `deploy-staging.sh`: refuses unless the branch is `staging` and `HEAD == origin/staging` (it served « whatever branch
  is checked out » — a playground that is retired); the stamp stays `"<branch> @ <sha>"` (the PWA compares it byte for
  byte). The comment « S1 is read-only, so staging against the real config/data is safe » stays true until K0's Q4
  replaces the read-only role by the preprod's own data; this lot does not change the role.

### 3.4 CI and rulesets

- `ci.yml` and `harness-full.yml`: `pull_request: branches: [develop, prod]`. The cut-over PR itself still targets
  `main` (it is the last one), so it carries `[main, develop, prod]`; the first PR into `develop` drops `main` (§ 4
  step 9). No `push` trigger: the promotion reads the PRs' checks (§ 3.1 rule 3) rather than running CI twice.
- `Makefile` `check`: `--base origin/develop`. `check_version_bump.py`'s default and docstring: `origin/develop`; a
  test that `0.98.131.1 > 0.98.131` and `0.98.132 > 0.98.131.1` (the tuple comparison already does it — the test pins
  it).
- Rulesets (applied by hand at the cut-over, § 4 — the JSON lives in `docs/features/git-flow/rulesets/` so the
  change is reviewed and can be re-applied):
  - `develop` (new): today's `main` rules moved — `deletion`, `non_fast_forward`, `pull_request` (methods `squash` and
    `merge`, the latter for a hotfix's merge-back), `copilot_code_review`, `required_status_checks` strict with the
    same nine contexts.
  - `prod` (new): `deletion`, `non_fast_forward`, `pull_request` (method `squash`) with the nine checks, for a hotfix
    PR. A promotion's push goes through the bypass (§ 1.2) — the script is its guard.
  - `main` (amended) and `staging` (new): `deletion`, `non_fast_forward`. No `pull_request` rule: no PR ever targets
    them; promotions push.
  - The bypass actor is kept as it is (§ 1.2): changing who can bypass is not this lot's.
- Default branch: `develop` — `gh pr create` and the GitHub UI then target it by default, and `~DEFAULT_BRANCH` in a
  ruleset follows it. The rulesets name their branches explicitly (`refs/heads/develop`, …), so moving the default
  branch does not move a rule.

### 3.5 `CLAUDE.md`, `docs/reference/method.md`, the orchestrator's habits

- `CLAUDE.md` « Commits and pull requests »: branches cut from `develop`; a PR targets `develop` (`--base develop`,
  the default once `develop` is the default branch); auto-merge armed at open as today; `gh pr update-branch` after
  `develop` moves; « Every PR bumps the patch version » relative to `develop`; a new paragraph: promotions are
  `scripts/promote.sh` only (`main` by the orchestrator when a lot is validated; `staging` and `prod` on his word
  only); a hotfix is cut from `prod`, PR into `prod`, then merged back into `develop` by a merge-commit PR from a
  `backport/<c>` branch cut at `prod`'s tip (§ 3.7). « Web environments »: prod tracks `prod`, staging tracks
  `staging`.
- `method.md` gains « The flow's scripts »: each run-by-hand step with its exact invocation (`scripts/promote.sh main`,
  `staging`, `prod`, `tag`, `backport <c>`, `--dry-run`), who may call it (any session; `staging` and `prod` on his
  word only) and what it prints — so the orchestrator or any agent runs it without reading this DESIGN (DECIDED 1).
- `method.md` « Lots here »: a lot's PRs merge into `develop` at green CI; done = gates + reader on tm-design; then
  the orchestrator promotes it to `main`; staging and prod move on his word. « He decides the functional; everything
  else goes on without him: decide, merge, deploy » is AMENDED by his ruling for `staging` and `prod`: those two
  deploys are his (operator-method § 3, 10-01). The line is rewritten « … decide, merge, promote to `main` ».
- The orchestrator skill's own texts (`orchestrator:*`, `implement:*`, outside the repository): their `--base` default
  follows the repository's default branch; nothing in the repository changes for them. Where a brief names `main` as a
  PR's base, the orchestrator names `develop`.

### 3.6 tm-design (outside the repository)

- `review-archive/tm-design-lot.txt` line 1: `develop` (the follower already reads its base branch from there; its
  fallback `main` in `tm-design-follow.sh` line 14 becomes `develop`).
- The DEV checkout `~/dev/PersonalScraper` stands on `develop`: `torrentmate-design` loads `serve.py` from it, and
  `qbit-watchdog` and the follower run from it.
- No change to the build, the mutex or the proof.
- From the cut-over, tm-design is no longer served by `main` and evolves on its own (DECIDED 3): a PR merged into
  `develop` reaches it with no word of his; only `staging` and `prod` wait for him.

### 3.7 The hotfix, step by step

1. `git switch -c hotfix/<c> origin/prod`; fix with its regression test; bump `__version__` to prod's plus `.1`.
2. PR `hotfix/<c>` → `prod`, squash, auto-merge armed; CI runs (trigger § 3.4). At its merge `prod` moves; the poller
   deploys it; the orchestrator tags it (`scripts/promote.sh tag` — the tag arm alone, rule 4).
3. Merge-back: `scripts/promote.sh backport <c>` — it merges `develop` into `prod`'s tip in a throwaway worktree,
   pushes the merge to `backport/<c>` and opens the PR `backport/<c>` → `develop`, auto-merge armed with the MERGE
   method (a merge commit makes `prod`'s tip an ancestor of `develop`, which is what restores § 0's chain; a squash
   would not). `__version__` always conflicts (prod's `X.Y.Z.1` against develop's `X.Y.(Z+n)`): the script resolves
   it to `develop`'s version bumped one patch, so the PR carries a real bump and `version-bump` passes with no label.
   Any other conflict stops it before a push, naming the file to resolve by hand. It says « auto-merge armed » only
   when `gh pr merge --auto` succeeded; otherwise it names the pushed branch and the PR and exits non-zero.
   `delete_branch_on_merge` deletes `backport/<c>`.
4. Until the backport merges, a promotion to `prod` is refused by rule 2 — by design. `main` and `staging` then
   receive the hotfix with the next promotions, and the chain is whole again.

### 3.8 What the flow needs from `/api/v1` (the BACKEND mission's, not this lot's)

The versioning lands in K0 (`backend-brief.md` § 6). The flow needs three things from it, recorded here so K0 owes
them:

- The deploy scripts' post-checks read `/api/health` and `/api/version`, today v0. When v1 serves them, the scripts
  follow in the same PR that moves the routes — the deploy is part of the route's consumers.
- The v0 cleanup register is closed only when v1 is on `prod` AND validated there: « once v1 is fully deployed and
  validated » reads, in this flow, as « tagged on `prod` ». Its cleanup PR goes to `develop` like any other.
- The per-environment data (Q2's suffix) is set by ONE environment setting per clone (`ecosystem.config.js` env of the
  staging apps); the deploy scripts do not set it. `deploy-staging.sh` loses its « read-only role » comment the day
  K0 retires `PERSONALSCRAPER_WEB_ROLE=staging`.

### 3.9 Documentation in `docs/production/`

`web-ui.md` § Deploy Runbook (clones table, deploy scripts, autodeploy poller, ENV-SEP « Branch » column, BUILD_COMMIT)
and `ecosystem.config.js`'s header comments are rewritten with the cut-over. `docs/production/` is frozen until the
switchover because it describes the version in production; the CD IS production, and a runbook that names `main` after
the cut-over would send an operator to the wrong branch. `docs/production/commands.md` is checked and changed only if
it names the deploy branch.

## 4. The migration — one cut-over, with its rollback

The repository's rule before v1 is no back-compat: the flow changes in ONE window, not branch by branch. Phases 1–4
(§ 6) ship as ONE PR into `main` (the last PR `main` receives); phase 5 is the window. It needs his sign-off: it
rewrites `staging`, changes the rulesets and restarts the poller — live actions this lot's author may not take. Until
the window, today's flow continues unchanged (a merge into `main` deploys prod); from it, `staging` and `prod` move on
his word only (DECIDED 3).

Preconditions: #672 merged or retargeted; no PR armed into `main` but the cut-over PR; no deploy in flight
(`pm2 logs torrentmate-autodeploy --lines 5 --nostream`); the current rulesets saved
(`gh api repos/IznoCorp/torrent-mate/rulesets/15201125 > review-archive/git-flow/ruleset-main-before.json`).

1. `pm2 stop torrentmate-autodeploy` — nothing deploys during the window.
2. The cut-over PR merges into `main` (auto-merge, CI green). Call its SHA `S`.
3. Branches on origin: `git push origin S:refs/heads/develop S:refs/heads/prod`; `staging` is archived then moved:
   `git push origin origin/staging:refs/tags/archive/staging-2026-08-14` (DECIDED 4), then
   `git push --force-with-lease=staging:67ea6509b origin S:refs/heads/staging` — the only non-fast-forward of the lot.
4. Rulesets: create `develop`, `prod`, `staging` from `docs/features/git-flow/rulesets/*.json`; amend `main`
   (`gh api -X PUT …/rulesets/15201125 --input …`). Default branch → `develop`
   (`gh api -X PATCH repos/IznoCorp/torrent-mate -f default_branch=develop`).
5. Clones: in each, `git fetch origin` first — the stopped poller fetched only `main` and `staging`, so neither clone
   knows `origin/prod` nor `staging`'s new tip. Then in `~/deploy/torrentmate`, `git switch -c prod --track
   origin/prod` (same SHA `S`, no file changes); in `~/staging/torrentmate`, `git switch -C staging origin/staging`
   (tree clean, the deploy script requires it).
6. Deploy once by hand, which proves the new scripts: `bash scripts/deploy.sh` in the prod clone (guard on `prod`,
   `/api/version` serves `S`), `bash scripts/deploy-staging.sh` in the staging clone (`staging @ S`).
7. `pm2 restart torrentmate-autodeploy` (loads the new poller); `pm2 logs torrentmate-autodeploy --lines 5 --nostream`
   shows « `prod` up to date (`S`) » and « `staging` up to date (`S`) ».
8. tm-design: `tm-design-lot.txt` line 1 → `develop`; the dev checkout `git switch develop`; the follower's next pass
   logs « develop S + <lot> — served ».
9. Retarget the lot in flight: `gh pr edit <n> --base develop`; the next PR into `develop` drops `main` from the CI
   triggers (phase 6).

**Rollback**, at any step, in reverse: `pm2 stop torrentmate-autodeploy`; restore the `main` ruleset from the saved JSON
and delete the three new ones; default branch → `main`; the prod clone `git switch main` (still `S`), the staging clone
`git fetch origin && git switch -C staging origin/staging` after
`git push --force origin refs/tags/archive/staging-2026-08-14:refs/heads/staging` if the old playground is wanted back
(without the fetch the clone switches to the `staging` it last saw); revert the cut-over commit by a PR into `main`; `pm2 restart
torrentmate-autodeploy`. `develop` and `prod` may stay on origin unused or be deleted (with his word). No data is
touched by the lot: nothing to restore under `.data/` or the stores.

## 5. DECIDED — his rulings of 2026-10-01

The five questions this DESIGN left open, answered by him on 2026-10-01 (recorded in `docs/reference/operator-method.md`
§ 3 « Environnements et back-end », the lines « 10-01 · git flow … »). Not reopenable; the paragraphs they change above
are rewritten to match.

**DECIDED 1 — His gesture to deploy staging and prod: A, and scripts any session calls.** His words: « A et des
scripts à lancer au besoin que l'orchestrateur ou tout autre agent peut également appelé. » He says it to the
orchestrator (« passe en staging », « mets en prod »); the promotion — and every step of the flow that is run by hand
(the promotions, the release tag, a hotfix's merge-back) — is a plain script in `scripts/` that ANY session runs, the
orchestrator or any agent, with no skill, no workflow and no state of its own. `docs/reference/method.md` names each
one with its exact invocation (§ 3.5). No GitHub Actions « Promote » button (reading B) is built.

**DECIDED 2 — The release tag's name: A.** `v` + the `__version__` the promoted commit carries (`v0.98.160`); the patch
numbers jump between two releases. A promotion stays a pure fast-forward, and the tag names exactly what
`/api/version`'s commit carries.

**DECIDED 3 — When a prod deploy waits for him: A, from the cut-over.** His words: « A, pour l'instant les "mise en
prod" ne touche pas la prod (tm.iznogoudatall.xyz) donc on peut y aller, quand on fera la bascule à ce moment on
attendra mon mot pour les mises en prod et staging, mais à ce moment tm design ne sera plus servi par main et pourra
continué d'évolué en toute autonomie ». Read: « la bascule » is this lot's cut-over (§ 4), the moment tm-design stops
being served by `main`. Until it, today's flow continues — a merge into `main` deploys prod, which today touches
nothing he reads on tm.; from it, `staging` and `prod` move on his word only, and tm-design follows `develop` and
evolves on its own, with no gate of his.

**DECIDED 4 — Today's `staging` branch: A.** Archived as the tag `archive/staging-2026-08-14`, then moved to the
cut-over commit (§ 4 step 3). The tag keeps the cut-over reversible (§ 4 rollback).

**DECIDED 5 — The hotfix path: A, straight to prod.** A `hotfix/<c>` PR merges into `prod` and deploys at once, with
CI on its PR; it is backported to `develop` (§ 3.7), and `main` and `staging` receive it with the next promotions. It
is not tried on the preprod first.

## 6. Phases

Phases 1–4 are one branch and one PR into `main` (the cut-over PR), labelled `no-version-bump` only if it touches
nothing under `personalscraper/`, `scripts/`, `.github/workflows/` — it touches `scripts/` and the workflows, so it
bumps the patch. Each phase's gate: `make lint`; pytest of the touched modules.

| # | Phase | Files | Done when | The command that proves it |
| --- | --- | --- | --- | --- |
| 1 | CI and the version check follow the new bases | `.github/workflows/ci.yml`, `harness-full.yml` (`[main, develop, prod]`), `Makefile` (`--base origin/develop`), `scripts/check_version_bump.py` (default, docstring), `tests/scripts/test_check_version_bump.py` (four-component cases) | the triggers name the three bases; the bump check passes `0.98.131 → 0.98.131.1 → 0.98.132` and refuses the reverse | `grep -n "branches:" .github/workflows/*.yml`; `pytest tests/scripts/test_check_version_bump.py tests/scripts/test_ci_skips_draft_pull_requests.py` |
| 2 | `scripts/promote.sh` | `scripts/promote.sh`, `tests/scripts/test_promote.py` | the four refusals, the three promotions, the tag and the backport are tested against a bare remote in `tmp_path`; `--dry-run` pushes nothing | `pytest tests/scripts/test_promote.py` |
| 3 | The poller and the deploy scripts follow `prod` and `staging` | `scripts/autodeploy-poll.sh`, `scripts/deploy.sh`, `scripts/deploy-staging.sh`, `ecosystem.config.js` (comments), `tests/scripts/test_autodeploy_branches.py`, `tests/indexer/test_ecosystem.py` if a pinned string moves | prod follows `prod` only; staging follows fast-forwards and refuses a diverged history; `deploy.sh` refuses `main`; `deploy-staging.sh` refuses any branch but `staging` | `pytest tests/scripts/test_autodeploy_branches.py tests/scripts/test_autodeploy_design_restart.py tests/indexer/test_ecosystem.py` |
| 4 | The words: method, CLAUDE.md, runbook, rulesets as files | `CLAUDE.md`, `docs/reference/method.md`, `docs/production/web-ui.md` § Deploy Runbook, `docs/features/git-flow/rulesets/{develop,prod,staging,main}.json` | no text in the repository names `main` as a PR base or as the deployed branch | `rg -n "origin/main\|tracks .main.\|--base main" -g '*.md' -g '*.sh' -g '*.yml' -g 'Makefile' .` returns only history and this DESIGN; `python3 scripts/check-no-french.py`; `make lint` |
| 5 | The cut-over (live, his sign-off, the orchestrator executes) | none in the repository; `review-archive/tm-design-lot.txt`, the two clones, origin's branches, the rulesets, PM2 | § 4 steps 1–9 done; prod and staging serve `S`; tm-design serves `develop` + the lot | `git ls-remote origin develop main staging prod` (four × `S`); `gh api repos/IznoCorp/torrent-mate/rulesets --jq '.[].name'`; `pm2 logs torrentmate-autodeploy --lines 5 --nostream`; the prod and staging `/api/version` (`S`, `staging @ S`); `tail -2 ~/Library/Logs/tm-design-follow.log` |
| 6 | The flow proven end to end | `.github/workflows/ci.yml`, `harness-full.yml` (drop `main`) — carried by the first ordinary PR into `develop` | a PR into `develop` runs CI and auto-merges; tm-design serves it; `scripts/promote.sh main` moves `main` to it; the poller logs no deploy (only `staging`/`prod` deploy) | `gh pr checks <n>`; `scripts/promote.sh main --dry-run` then without; `git rev-parse origin/main origin/develop` equal; `pm2 logs torrentmate-autodeploy --lines 5 --nostream` |

The first `staging` and `prod` promotions after the cut-over are on his word (DECIDED 1, DECIDED 3); they are not a
phase of this lot.
