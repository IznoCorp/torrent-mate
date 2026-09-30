# maquette-navigation — every edge against § 16, and the rule that walks them · PLAN

Design: `docs/features/maquette-navigation/DESIGN.md`. The implementer is held to `docs/reference/implementer-office.md`,
AMENDED by the auditor's orders 98 and 99 (§ « The gates » below); this plan carries only what is the lot's own.
Written 2026-09-30 on `main` at `f71a44f7b`. **The code opens after the conformity train has merged** (DESIGN § 0.3:
its phases 5 and 10 touch Système and the drawer), on `main` holding it — every `file:line` re-read there.

## The operator's principles, and the phase that proves each (order 97 — the design's table is DESIGN § 5)

| Principle, his words | Phase |
| --- | --- |
| § 16 — « Si je passe par système je repasse par systèmes, sinon non. » — menu pages, Profil and in-page links stack; bar pages replace from anywhere | 1 · 2 · 3 |
| « Vérifier les autres cas également » — 35 edges, each walked by R-navigation-a; an unclassified emitter fails it | 1, then every phase |
| « Il faut uniformiser les comportements. Sauf exception volontaire de ma part. » — one reading per kind of edge; OPEN 1–3 | every phase |
| « on crée pas de nouveau composant on adapte » — the entry's `trail`, the driver's `poseTrail`; N6 is the existing Retour | 1 · 3 |
| « seule une maquette montrant tout les cas possibles est utile » — four named states (DESIGN § 4) | 1 · 3 |
| « tout doit être responsive … sur tous ! » — R-conformity-a on the new states at their gate | 1 · 3 |
| « Mes retours sont des corrections sur ce qui est attendu » — a navigation defect he reports while the lot runs joins the phase of its family (order 98) | any |

## The phases — one FAMILY of edges each

**Why families, not surfaces**: every edge of every surface goes through ONE module (`app/page-switch.ts`) and three
verbs (`app/frame-verbs.ts`); a cut by surface (Système, Réglages, the menu …) would reopen that module in every
phase and re-prove its readers each time. A family is one mechanism, its emitters and its readers, closed once.

| # | Family | DESIGN rows | Rules | Page |
| ---: | --- | --- | --- | --- |
| 1 | The machinery and Système's page links — the trail, the destination's class, B-577 | N1–N3, M4, M5, T1–T5, Y5 | a (written whole), b | [phase-01](phase-01-the-machinery-and-b577.md) |
| 2 | The side menu and the account sheet — then the MIDPOINT | M1–M3, M6, M7, P1 | a | [phase-02](phase-02-the-menu-and-the-account-sheet.md) |
| 3 | The links to Acquisition, and the screens' exits | N4–N6, L1–L4, S1–S7 | a | [phase-03](phase-03-links-home-and-screen-exits.md) |
| 4 | The close — the lot's gate, the documents, the pull request | § 7 | all, by name | [phase-04](phase-04-the-close.md) |

**R-navigation-a is written WHOLE in phase 1**, every row of the DESIGN's table in `harness/navigation_edges.py`; a
DEFECT row a later phase owns is declared `owed: <phase>` and asserted RED (its Retour today, read), so each phase
flips its own rows from red to green and the rule never lies about the rows it has not reached.

## The gates (order 99, amending the office's « The gate »)

- **A phase gate — light**: the static guards on the files touched; the ORACLE ALONE, accepting only the states the
  page names (the declared list built BY SCRIPT); `run.sh --rules journey.py` plus the rules the page re-aims, each new
  hold read RED on the old code first; R-conformity-a on the touched states. Every browser run names
  `TM_HARNESS_JOBS=2` (order 88); every pytest `-n 2`. **Navigation is proved by a finger walk** (office): every row
  the phase flips is walked at 369 px, cold, by taps and the system Retour.
- **The midpoint, after phase 2**: `--contracts` and the full responsive sweep, once.
- **Once per lot, at phase 4**: the full suite (CI its authority), `--a11y`, the hold counts, each rule of the lot by
  name. The reader round follows the pull request (`docs/reference/reader-office.md`, order 81's lens first).

## The stops

**STOP A** — the oracle diverging on a state the page did not name. **STOP B** — the pull request. **STOP C** — the
OPEN answers (DESIGN § 6): OPEN 1 read before phase 1, OPEN 3 before phase 2, OPEN 2 before phase 3; each page is
written for the recommended reading. **STOP D** — a ceiling (`grep -cv '^\s*$'`, 400): `add-screen.tsx` **382**,
`run-screen.tsx` **324**, `page-switch.ts` **294** — a phase landing near 400 moves lines out. Anything outside these
pages: STOP, ask the orchestrator.

## The gate of THIS docs pull request

`python3 scripts/check-docs-cited-paths.py`, `check-no-french.py`, `check-implementation-state.py`,
`check-intent-map.py`, `make lint` — the implementer's gates above do not apply to it.
