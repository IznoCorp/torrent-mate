# Season recovery — a whole-season recovery, visible and exclusive · PLAN

Design: `docs/features/maquette-season-recovery/DESIGN.md`. The method is
`docs/reference/method.md` and the gates are `CLAUDE.md` § Gates.

**Re-cut 2026-09-30, on `main` at `9234341fc`** (orders 97, 98, 99), after the operator's round Q14–Q19: 13 phases
become **5**, one per surface. The old plan is `docs/features/maquette-season-recovery/plan/INDEX.md@9234341fc`; its
correspondence is the last table. The CODE is built inside the next lot that touches Acquisition (order 69 — the
orchestrator names it), after the conformity train has merged (its phase 9 makes the row's mark the chip). The
backend demands it relies on are DESIGN § 6's SR1–SR5; the maquette answers from its mock layer until the engine does.

## The operator's principles, and the phase that proves each (order 97 — the design's table is DESIGN § 0.3)

| Principle, his words | Phase |
| --- | --- |
| « Il faut uniformiser les comportements » — followed or one-off, manual or automatic, one card, one mark, one absorption; the pointer lands like « Voir le tracker » | 1 · 2 · 3 |
| « on crée pas de nouveau composant on adapte » — nothing new drawn (DESIGN § 1.8); rule f | 4 |
| « seule une maquette montrant tout les cas possibles est utile » — 30 named states, none conditional | every phase |
| « tout doit être responsive … sur tous ! » — R-conformity-a on the touched states at each gate; the full sweep at the midpoint and the close | every phase; 2 · 5 |
| « une différence entre film et série » — a recovery is a series'; a film's releases untouched (a hold of rule d) | 4 |
| Constitution § 16 — the pointer stacks, Retour returns to the journey's page, walked by finger | 3 |

## The phases — one surface each, sized by the context (gauge + the last phase's cost ≤ 80), no point cap

| # | Surface | DESIGN | Rules | Page |
| ---: | --- | --- | --- | --- |
| 1 | « En cours » — the season's card and the absorption, and the data they read | S2, S3, S6; § 1.7, § 2 | a, e, g (card) | [phase-01](phase-01-the-season-card-and-the-absorption.md) |
| 2 | The season's row on both sheets — then the MIDPOINT | S1, S6 | b, g (row) | [phase-02](phase-02-the-season-row.md) |
| 3 | The journeys and the pointer | S4, S2's journey | c | [phase-03](phase-03-the-journeys-and-the-pointer.md) |
| 4 | The release picker's refusal | S5 | d, f | [phase-04](phase-04-the-release-picker.md) |
| 5 | The close — the lot's gate, the records, the pull request | — | all, by name | [phase-05](phase-05-the-close.md) |

**Measured**: 13 phases → **5** (4 surfaces + the close). The end (S6) is not a phase of its own: each of its states
lands with the surface it shows (the card's in 1, the row's in 2, the pointer's in 3, the picker's in 4).

## The gates (order 99, amending the office's « The gate »)

- **A phase gate — light**: the static guards on the files touched; the ORACLE ALONE, accepting only the states the
  page names (built by script); `run.sh --rules` on the rules of the surfaces touched — each new hold read RED on the
  old code first, then green (no per-phase mutation, no per-phase `--a11y`); R-conformity-a on the touched states.
  Every browser run names `TM_HARNESS_JOBS=2`; every pytest `-n 2`. Navigation (3, 4) walked by finger.
- **The midpoint, after phase 2**: `--contracts` and the full responsive sweep (Chromium + WebKit), once.
- **Once per lot, at phase 5**: the full suite, `--a11y`, the full sweep, the hold counts, each rule a–g re-run BY
  NAME (order 98); the reader round follows (ten random mutations, the finger walk, the principles).

## The stops

**STOP A** — the oracle diverging on a state the page did not name. **STOP B** — the pull request. **STOP C** — none
left: OPEN 8 is DECIDED 8 = A (DESIGN § 5, 2026-09-30). **STOP D** — a ceiling
(`grep -cv '^\s*$'`, 400): `lib/queue.ts` **390**, `features/media/season-list.tsx` **390**, `mocks/state.ts` **398** (the conformity train's close) —
none grows (the derivation lands in its own `lib/` module). Anything outside these pages: STOP, ask the orchestrator.

## The gate of THIS docs pull request

`python3 scripts/check-docs-cited-paths.py`, `check-no-french.py`, `check-implementation-state.py`,
`check-intent-map.py`, `make lint`.

## Correspondence — every element of the old plan, every ruling → its phase

Old pages: `docs/features/maquette-season-recovery/plan/phase-NN-….md@9234341fc`.

| Element | → |
| --- | --- |
| old 1 the contract: `QueueCard.season`, `episode`, `absorbedBy`; the grab's `200` (`reused`) · the journey read per acquisition | 1 · 3 |
| old 2 the seeds: Silo's season card, its episode card, the season pack | 1 (the pack is read at 4) |
| old 3 the mocks: `grabSeasonForFollow` for a followed series, the absorption, the ladder to « rangé » · `readJourney` per acquisition | 1 · 3 |
| old 4 the derivation moves to `lib/` (a move, proved by the oracle alone before it is extended) | 1 |
| old 5 the absorption, R-a, R-e, R224 re-aimed | 1 |
| old 6 « Demandée » on both sheets, R-b, the key renamed `seasonRequested` | 2 |
| old 7 the mark is the chip (OPEN 7) | **REMOVED — subject taken** by the conformity train's phase 9 (D.1 #5); the harness re-aims of R138 / R158 go with it there |
| old 8 the season's card states · its journey (per acquisition, the absorbed listed) | 1 · 3 |
| old 9 the pointer, R-c, the landing door adapted | 3 |
| old 10 the refusal, R-d, R-f | 4 |
| old 11 the end: shelved rows `7/7` · closed short, abandoned · the ended pointer · `S03E07` takes again · `season-row-ask-failed`, `-ask-held` | 2 · 1 · 3 · 4 · 2 |
| old 12 the records: the four register rows of DESIGN § 6 | 1 (a followed ask draws no card; an episode card beside its season) · 2 (« Demandée » reads another list) · train 9 (`queuedMark`) |
| old 12 · old 13 — the demands SR1–SR5 regenerated, the map's proposal, the report | 5 |
| old midpoint « after phase 6 » | after 2 |
| Q14 = DECIDED 1 (journey per acquisition) · Q15 = DECIDED 2 (the landing) · Q16 = DECIDED 3 (the absorbed downloading, listed) | 3 · 3 · 3 |
| Q17 = DECIDED 4 (one mark at a time) · Q18 = DECIDED 5 (the served link) · Q19 = DECIDED 6 (the auto / manual mark) | 2 · 1 · 1 (card, the field) and 2 (row) |
| OPEN 8 (where the card carries « auto ») | 1 (DECIDED 8 = A, 2026-09-30) |
| B-rows owned: `grep -n -i "season-recovery\|season recovery" BUGS.md \| wc -l` → **0** on `9234341fc` | — |
