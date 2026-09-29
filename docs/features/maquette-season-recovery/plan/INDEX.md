# Season recovery — a whole-season recovery, visible and exclusive · PLAN

Design: `docs/features/maquette-season-recovery/DESIGN.md`; the implementer is held to `docs/reference/implementer-office.md`.

**Written 2026-09-29, on `main` at `b63a45438`.** The CODE is built inside the next lot that touches Acquisition
(order 69 — the orchestrator names it); every figure below was taken by a command on `b63a45438` and is RE-TAKEN at
the phase's real opening — a figure that moved is re-taken, a figure that no longer supports its phase's cut is
STOP D. The backend demand it relies on is `docs/reference/backend-demands-architecture.md` § 14, with the
absorption detail DESIGN § 6 proposes (SR1–SR4); the maquette answers from its mock layer until the engine does.

## The stops

- **STOP A** — the oracle diverging on a state the phase did not name. **STOP B** — the pull request.
- **STOP C — OPEN.** DESIGN § 5's seven questions go to ONE operator round before phase 1 opens. Phases 1, 3, 6, 7,
  8, 9 and 10 carry one; each is written for the RECOMMENDED reading and names what its other reading changes.
- **STOP D** — a measurement that contradicts a home the design decided. Near already (non-blank lines, ceiling
  400): `lib/queue.ts` **390**, `features/media/season-list.tsx` **390**, `mocks/state.ts` **393** — none of them
  grows (the derivation lands in its own `lib/` module, the seeds in seed files, the row's marks already exist).
  Anything outside this plan and its design: STOP, and ask the orchestrator first.

## Points, and the mean

The scale is L23's (`docs/features/maquette-l23/plan/INDEX.md` « Points »). A phase whose re-measure at its opening
exceeds 15 is cut there, never begun, and the orchestrator told.

| # | Phase | Kind | Rule | Points | OPEN |
| ---: | --- | --- | --- | ---: | --- |
| 1 | [The contract](phase-01-the-contract.md) | contract | — | 8 | 1, 5 |
| 2 | [The seeds](phase-02-the-seeds.md) | seed | — | 7 | — |
| 3 | [The mocks that move](phase-03-the-mocks-that-move.md) | mock | — | 13 | 1, 3, 5 |
| 4 | [The derivation moves to lib](phase-04-the-derivation-moves-to-lib.md) | move | — | 6 | — |
| 5 | [The absorption](phase-05-the-absorption.md) | behaviour (S3) | a, e | 13 | — |
| 6 | [« Demandée » on both sheets](phase-06-requested-on-both-sheets.md) | surface (S1) | b | 14 | 4, 6 |
| 7 | [The mark is the chip](phase-07-the-mark-is-the-chip.md) | refactor | — (re-aims) | 5 | 7 |
| 8 | [The season's card and its journey](phase-08-the-season-card-and-its-journey.md) | surface (S2) | — (holds on a, b) | 14 | 1, 3, 6 |
| 9 | [The pointer](phase-09-the-pointer.md) | navigation (S4) | c | 14 | 1, 2 |
| 10 | [The refusal](phase-10-the-refusal.md) | surface (S5) | d, f | 12 | 7 |
| 11 | [The end](phase-11-the-end.md) | behaviour (S6) | — (holds on b, c, d) | 9 | — |
| 12 | [The records](phase-12-the-records.md) | records | — | 6 | — |
| 13 | [The close](phase-13-the-close.md) | close | — | 6 | — |

**Measured** (`python3 -c "print(8+7+13+6+13+14+5+14+14+12+9+6+6)"` → **127**): **127 points over 13 phases, mean
≈ 9.8, max 14** (phases 6, 8 and 9). **The midpoint** — the full suite, its falls repaired before the next phase — is after
phase 6: the derivation, the absorption and the row are in place, every surface after it reads them.

## Why this order

The contract (1) before the seeds (2) before the mocks (3): `scripts/compare-contracts.py --check` refuses a field
apart from its schema, and a handler with no seed answers nothing. The derivation is MOVED (4) before it is extended
(5); the row (6) reads the same derivation; the mark's component (7) precedes the two surfaces that draw it (8, 10);
the card and its journey (8) precede the pointer (9) that lands on the one from the other; the end (11) walks every
surface back to rest; the records (12) and the close (13) end it.

## Gates

Per phase: the office's phase gate (`docs/reference/implementer-office.md` § « The gate »), divergences ONLY on the
states the phase names, the declared list built BY SCRIPT; every navigation (5, 9, 10) walked by finger at order 85's
seven widths; the harness budget read at the midpoint and the close; the pre-PR gate, the patch bump. **THIS docs
pull request's gate** is `check-docs-cited-paths.py`, `check-no-french.py`, `check-implementation-state.py`,
`check-intent-map.py` and `make lint`.
