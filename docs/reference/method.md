# TorrentMate — what is particular to this project

The generic method lives in the skills: `implement:*` (feature → phase → check → close, and the
pull request), `orchestrator:*` (dispatching agents), `pr-review-toolkit:review-pr` (the lot's
reading), `github:*`. This page holds only what is TorrentMate's, and it is the whole of the
project's method. A finding of an audit, a reading or a bug is fixed in the product, not made a
rule. The aim, in his words: « Seul 35 % du temps produit le code. C'est inacceptable ! »
— « Alléger les gardes et faire avancer le dev. » — « Il faut arrêter de chercher la perfection, et
chercher l'efficacité. »

## Authority — his words

- `docs/reference/product-intent.md` (constitution), `operator-method.md` § 1 (principles) and
  § 3 (decisions), the lots' `DESIGN.md`: his, amended by him alone. A web PR cites the §§ it serves.
- The maquette (`webui/design/`) is the v1 frontend, developed together with its backend
  (product-intent § 15); what is in it is validated, the existing is the reference, new work conforms
  to it.
- He decides the functional; everything else goes on without him: decide, merge, promote to `main`.
  Deploying `staging` and `prod` is his (operator-method § 3, 10-01): they move on his word only. His
  feedback corrects what was expected; it enters the lot in flight, whichever lot caused it.

## Lots here

- Order and done-when: `docs/reference/frontend-architecture.md` § 4; where it stands:
  `IMPLEMENTATION.md`. A phase is one surface. `CLAUDE.md` names the two gates the skills run.
- Push at every commit: tm-design shows him the work in flight (`develop` plus the lot), and he
  accepts its false bugs.
- A lot's PRs target `develop` and merge as soon as their CI is green — that is what puts them on
  tm-design. A lot is done when its gates are green and ONE independent reader has looked at the
  lot's screens at 390 px on tm-design, in one round, every major fixed; the orchestrator then
  promotes its last merged commit to `main`. One lot at a time stands on `develop` beyond `main` (a
  promotion is a fast-forward: an unvalidated commit holds back all that follows it). His own trial
  may come long after; what it finds is noted and fixed in whichever lot is in flight.

## The flow's scripts

`feature → develop → main → staging → prod` (`docs/features/git-flow/DESIGN.md`). Every step run by
hand is a plain script any session runs — the orchestrator or any agent — from any clone, with `gh`
signed in (his 10-01: « des scripts à lancer au besoin que l'orchestrateur ou tout autre agent peut
également appelé »). Each refuses with one line saying why, pushes nothing with `--dry-run`, and never
forces.

| Step | Invocation | Who, when |
| --- | --- | --- |
| Promote a validated lot | `scripts/promote.sh main [<sha>]` — `develop` → `main`; refused unless every commit is a merged PR into `develop` whose required checks were green | the orchestrator, when the lot's reading passed |
| Deploy the preprod | `scripts/promote.sh staging [<sha>]` — `main` → `staging`; the poller deploys it within 60 s (`tm-staging`'s `/api/version` → `staging @ <sha>`) | any session, on his word only (« passe en staging ») |
| Deploy production | `scripts/promote.sh prod [<sha>]` — `staging` → `prod`, then the tag `v<__version__>`; refused if that tag exists | any session, on his word only (« mets en prod ») |
| Raise the version | `scripts/promote.sh release` — when `develop`'s version is already tagged, opens the one PR into `develop` that raises it a patch (armed); otherwise says there is nothing to raise | before `promote.sh prod`, when it refuses a version already released |
| Tag a hotfix | `scripts/promote.sh tag` — tags `prod`'s tip after a hotfix PR merged into `prod` | whoever merged the hotfix |
| Merge a hotfix back | `scripts/promote.sh backport <c>` — `prod`'s tip merged with `develop` on `backport/<c>`, the `__version__` conflict resolved to `develop`'s plus one patch (any other conflict: it stops, pushes nothing, names the file), its PR into `develop` armed with the MERGE method | whoever merged the hotfix |

`<sha>` defaults to the source branch's tip; `--dry-run` goes anywhere on the line. A hotfix:
`git switch -c hotfix/<c> origin/prod`, the fix with its regression test, `__version__` = prod's plus
`.1`, a PR into `prod` (squash, auto-merge), then `tag` and `backport <c>`. Until the backport merges,
`promote.sh prod` refuses (not a fast-forward) — by design.

Before arming a PR: `git merge-tree --write-tree origin/develop <branch>`. Clean ⇒ arm the verified
head as it is, no rebase; a conflict ⇒ merge `develop` in. A stacked branch whose base was
squash-merged keeps its `rebase --onto`.

## Gates

| Gate | What | Time |
| --- | --- | --- |
| Phase | `make lint` · maquette `npm run typecheck && npm test` · pytest of the touched modules | 1–2 min |
| Push (hook) | ruff, mypy | < 1 min |
| Lot close | `make check`: lint, the cheap guards, frontend (typecheck, eslint, vitest, build, OpenAPI and contract-type drift) | ~2 min |
| CI | lint, mypy, full pytest, guards + no-French, frontend, pip-audit, licenses, gitleaks; on a pull request touching the maquette, every harness rule in four shards; all of it again on `develop` after every merge | 1–20 min |

The full pytest and the harness run on GitHub, not on IznoServer, which also serves production. A
rule broken by an intended change is updated or deleted in the same lot. A new rule, guard or check
comes only from a defect that reached him or the product; rigour comes back when one shows it (09-12).

## Bugs

- Every defect he reports is a row in `BUGS.md` at once, with his words. Its fix carries a regression
  test seen red and repairs the family (09-28): the cause is fixed, no instrument is built for it.

## Code

- Durable text in English; only his two documents are French. UI copy in
  `webui/design/src/i18n/fr.json`, never in code; names in English (checked in CI).
- No backward compatibility (09-29). A route change ⇒ `make openapi`, commit the generated files.
- Conventional Commits, no version prefix, no AI attribution (`hooks/commit-msg`). A PR leaves
  `__version__` alone; the version rises once per release (`scripts/promote.sh release`).
- No date or hour is written from memory: briefs and memories are named by their subject,
  state-journal lines carry no hour, a dispatch record's `opened` is left to its script; git and
  file times give the rest.

## The machine (IznoServer)

- Every `rg` has `--type py` or a `-g` glob (a 14 GB fixture). Heavy local runs go through
  `scripts/heavy.sh`, which admits them by budget: 8 cores, minus the reserves of what serves
  someone (Plex per session, Parsec while connected, qBittorrent while downloading, macOS), minus
  the runs already admitted, each class at its declared cost; `--budget` prints it. Plex is
  followed on its own signal, not a calibrated share (10-01): a direct play holds 0.3 core, a
  transcode 1 at its start; while a transcode that is not throttled runs under speed 1.5 no run is
  admitted, and under 1.1 the most recent run heavy.sh admitted is stopped (SIGSTOP) until the
  speed is back above 1.5, then continued. Tools default to half the processors. Kill what you start (his 09-02: « Toujours nettoyer […] TOUT ! »).
- Building agents have no fixed ceiling (10-01): one more only while `memory_pressure` is normal,
  its heavy runs waiting their turn in `heavy.sh`'s budget.
- Never a server on 8710/8711; never qBittorrent's localhost bypass; `personalscraper run` in the
  foreground. The machine reboots every Monday at 05:00.
