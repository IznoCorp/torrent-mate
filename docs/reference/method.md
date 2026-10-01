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
- The maquette (`frontend/maquette/design/`) is the next version of the app and is changed FIRST;
  what is in it is validated, the existing is the reference, new work conforms to it.
- He decides the functional; everything else goes on without him: decide, merge, deploy. His
  feedback corrects what was expected; it enters the lot in flight, whichever lot caused it.

## Lots here

- Order and done-when: `docs/reference/frontend-architecture.md` § 4; where it stands:
  `IMPLEMENTATION.md`. A phase is one surface. `CLAUDE.md` names the two gates the skills run.
- Push at every commit: tm-design shows him the work in flight, and he accepts its false bugs.
- A lot is done when its gates are green and ONE independent reader has looked at the lot's
  screens at 390 px on tm-design, in one round, every major fixed before the merge. His own trial
  may come long after; what it finds is noted and fixed in whichever lot is in flight.

## Gates

| Gate | What | Time |
| --- | --- | --- |
| Phase | `make lint` · maquette `npm run typecheck && npm test` · pytest of the touched modules | 1–2 min |
| Push (hook) | ruff, mypy | < 1 min |
| Lot close | `make check`: lint, the cheap guards, frontend (typecheck, eslint, vitest, build, OpenAPI and contract-type drift) | ~2 min |
| CI | lint, mypy, full pytest, guards + no-French, frontend, version bump, pip-audit, licenses, gitleaks; on a pull request touching the maquette, every harness rule in four shards | 1–10 min |

The full pytest and the harness run on GitHub, not on IznoServer, which also serves production. A
rule broken by an intended change is updated or deleted in the same lot. A new rule, guard or check
comes only from a defect that reached him or the product; rigour comes back when one shows it (09-12).

## Bugs

- Every defect he reports is a row in `BUGS.md` at once, with his words. Its fix carries a regression
  test seen red and repairs the family (09-28): the cause is fixed, no instrument is built for it.

## Code

- Durable text in English; only his two documents are French. UI copy in
  `frontend/maquette/design/src/i18n/fr.json`, never in code; names in English (checked in CI).
- No backward compatibility (09-29). A route change ⇒ `make openapi`, commit the generated files.
- Conventional Commits, no version prefix, no AI attribution (`hooks/commit-msg`); patch bump per PR.

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
