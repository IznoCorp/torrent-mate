# TorrentMate — what is particular to this project

The generic method lives in the skills: `implement:*` (feature → phase → check → close, and the
pull request), `orchestrator:*` (dispatching agents), `pr-review-toolkit:review-pr` (the lot's
reading), `github:*`. This page holds only what is TorrentMate's, and it is the whole of the
project's method. A finding of an audit, a reading or a bug is fixed in the product; it does not
become a rule. The aim, in his words: « Seul
35 % du temps produit le code. C'est inacceptable ! » — « Alléger les gardes et faire avancer le dev. »

## Authority — his words

- `docs/reference/product-intent.md` (constitution), `operator-method.md` § 1 (principles) and
  § 3 (decisions), the lots' `DESIGN.md`: his, amended by him alone. A web PR cites the §§ it serves.
- The maquette (`frontend/maquette/design/`) is the next version of the app and is changed FIRST;
  what is in it is validated, the existing is the reference, new work conforms to it.
- He decides the functional; everything else goes on without him: decide, merge, deploy.
- His feedback is a correction of what was expected, not an addition: it enters the lot in flight.

## Lots here

- Order and done-when: `docs/reference/frontend-architecture.md` § 4; where it stands:
  `IMPLEMENTATION.md`. A phase is one surface. `CLAUDE.md` names the two gates the skills run.
- tm-design always shows the work in flight: push at each phase end.
- The reading, once per lot, by a fresh session: it walks tm-design by finger at phone width and
  checks design-system reuse, uniform behaviour, navigation against § 16, and that every case of
  every touched surface is a named state (his principles of 09-29).

## Gates

| Gate | What | Time |
| --- | --- | --- |
| Phase | `make lint` · maquette `npm run typecheck && npm test` · pytest of touched modules · harness rules of the touched surface (`run.sh --rules …`) | 1–3 min |
| Push (hook) | ruff, mypy | < 1 min |
| Lot close | `make check`: lint, cheap guards, frontend (typecheck, eslint, vitest, build, OpenAPI and contract-type drift), the harness | ~7 min |
| CI | lint, mypy, full pytest, frontend + no-French, version bump, pip-audit, licenses, gitleaks | 1–9 min |

The full pytest runs in CI only; the full harness runs once, at the lot's close. A harness rule
broken by an intended change is updated or deleted in the same phase. A new rule, guard or check is added only for a defect that reached him or the
product, never « just in case »; rigour comes back when a defect shows it was needed (his 09-12).

## Bugs

- Every defect he reports is a row in `BUGS.md` at once, with his words, and never left unread.
- Its fix carries a regression test seen red and repairs the family (09-28): the cause is fixed;
  no instrument is built for it.

## Code

- Durable text in English; only his two documents are French. UI copy in
  `frontend/maquette/design/src/i18n/fr.json`, never in code; names in English (checked in CI).
- No backward compatibility (09-29). A route change ⇒ `make openapi`, commit the generated files.
- Conventional Commits, no version prefix, no AI attribution (`hooks/commit-msg`); patch bump per PR.

## Machine and service safety (IznoServer)

- Every `rg` has `--type py` or a `-g` glob (14 GB fixture); every curl/wget has
  `--connect-timeout` and `--max-time`.
- Heavy runs one at a time under `scripts/heavy.sh`, fan-out named (`TM_HARNESS_JOBS=2`,
  `pytest -n 2`); Plex comes first. Kill what you start; nothing launched after 04:15 on Monday.
- Never a server on 8710/8711; never qBittorrent's localhost bypass; `personalscraper run` in the foreground.
