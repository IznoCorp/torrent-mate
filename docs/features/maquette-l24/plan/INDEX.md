# L24 — the orphans: what no lot draws · PLAN

Design: `docs/features/maquette-l24/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L24 — the orphans, what no lot draws`. The implementer is held to `docs/reference/implementer-office.md`; this
plan carries only what is the lot's own.

**Written 2026-09-29, on `main` at `e65130ab1`; re-cut the same day, on `77e7b8436`, on the operator's six rulings**
(DESIGN § 5). The plan before the rulings is `docs/features/maquette-l24/plan/INDEX.md@e6d63bffe`; its journal phases
(S1 as a screen, its filter and counts) and its global-activity half are removed, not kept. L24 opens after L23.
Every figure below was taken by a command on `77e7b8436`; the implementer RE-TAKES each at the phase's real opening,
because L16, L17, L18 and L23 land between — a figure that moved is re-taken, a figure that no longer supports its
phase's cut is STOP D.

---

## The stops

- **STOP A** — the oracle diverging on a state the phase did not name.
- **STOP B** — the pull request.
- **STOP C — LIVE for three questions.** The six of 2026-09-29 are ruled; OPEN 7, 8 and 9 (DESIGN § 5) are raised by
  the rulings and not answered. A phase naming one is not begun before it is ruled; the answer is written into
  DESIGN § 5 and into that phase's file in ONE dated line each. Phases 7, 8 and 10 carry one; the others none.
- **STOP D** — a measurement that contradicts a home the design decided. Two are near already: `lib/addresses.ts`
  holds 395 non-blank lines of 400 (phase 10 adds at most 3), and `mocks/handlers/staging.ts` holds 399 (so no
  phase adds to it — phase 3's enqueue lives in `mocks/handlers/decisions.ts`, 112).

Anything outside this plan and its design: STOP, and ask the steward first.

---

## Points, and the mean

The scale is L23's (`docs/features/maquette-l23/plan/INDEX.md` « Points »): a line edited 1 per 5, written new 1 per
10; a new rule with its mutation 3; a rule re-aimed 1; a named state 1 (re-using a seed) or 2 (a new seed row); an
operation declared new 2, edited 1; a mock route new 2, re-answered 1; a sentence rewritten 1; a documentation row 1.

A phase whose re-measure at its opening exceeds 15 is cut there, never begun, and the steward told.

| # | Phase | Kind | Rules | Points | STOP C |
| ---: | --- | --- | --- | ---: | --- |
| 1 | [The contract](phase-01-the-contract.md) | contract | — | 8 | — |
| 2 | [The seeds](phase-02-the-seeds.md) | seed | — | 13 | — |
| 3 | [The mocks that move](phase-03-the-mocks-that-move.md) | mock | — | 12 | — |
| 4 | [A section says its read failed](phase-04-a-section-says-its-read-failed.md) | behaviour (S2) | c | 9 | — |
| 5 | [A decision on the journey sheet](phase-05-a-decision-on-the-journey-sheet.md) | surface (S1) | a | 13 | — |
| 6 | [The same block on the Médiathèque sheet](phase-06-the-same-block-on-the-library-sheet.md) | surface (S1) | b | 7 | — |
| 7 | [« Corriger » arrives with candidates](phase-07-correct-arrives-with-candidates.md) | surface (S5) | e | 15 / 12 | OPEN 7 |
| 8 | [« Corriger » on the Médiathèque sheet](phase-08-correct-on-the-library-sheet.md) | surface | e (+ hold) | 8 / 0 | OPEN 8 |
| 9 | [The continuation is seen](phase-09-the-continuation-is-seen.md) | proof | f | 5 | — |
| 10 | [The former addresses](phase-10-the-former-addresses.md) | surface (S4) | d | 15 / 13 | OPEN 9 |
| 11 | [Identification, read on the card](phase-11-identification-read-on-the-card.md) | proof (S3) | l | 4 | — |
| 12 | [A filling disk on the badge](phase-12-a-filling-disk-on-the-badge.md) | behaviour (S2) | m | 5 | — |
| 13 | [The sheet says what it is](phase-13-the-sheet-says-what-it-is.md) | proof | h | 4 | — |
| 14 | [One completeness](phase-14-one-completeness.md) | source change | i | 9 | — |
| 15 | [The ladder's words, « enrichi » unfolded](phase-15-the-ladders-words.md) | surface + proof | n | 11 | — |
| 16 | [The title alone, every card](phase-16-the-title-alone-every-card.md) | proof | g | 5 | — |
| 17 | [No destruction without consent](phase-17-no-destruction-without-consent.md) | proof | j | 5 | — |
| 18 | [The desktop is fully functional](phase-18-the-desktop-is-fully-functional.md) | proof | k | 5 | — |
| 19 | [The records](phase-19-the-records.md) | records | — | 6 | — |
| 20 | [The close](phase-20-the-close.md) | close | — | 6 | — |

**Where a reading changes the cost, both are written, larger first**, and neither is chosen. **At the larger reading
of OPEN 7, 8 and 9: 165 points over 20 phases, mean ≈ 8.3, max 15** (phases 7 and 10). At the smaller: 152 points
over 19 phases (phase 8 drops), mean 8.0, max 13. **The rulings removed** the journal's two phases (27 points) and
Système's « en ce moment » (8), and added the block on two sheets (phases 5–6) and « Corriger » on the Médiathèque
sheet under OPEN 8 A. **The desktop milestone after the drawn lots is not in this plan**: no points, no phases, its
contour the operator's (`docs/reference/frontend-architecture.md` § 4).

---

## Why this order

**The contract first** (1): `scripts/compare-contracts.py --check` refuses a demand apart from its schema. **The
seeds second** (2), **the mocks third** (3): a handler with no seed answers nothing. **Système's failed section** (4)
touches one page already drawn and one mock scenario, the smallest behaviour first. **The block before its act**
(5, 6 before 7, 8): « Corriger » is drawn in the block. **The continuation after « Corriger »** (9): its proof walks a
resolution from « Corriger » as well as from « À traiter ». **The addresses after the block** (10), because OPEN 9's
reading B lands `/media?decision=` on it. **The proofs last** (11–18), each reading surfaces already drawn; **the
records** (19) and **the close** (20) end it.

---

## Gates

Per phase: the office's phase gate (`docs/reference/implementer-office.md` § « The gate »), with divergences ONLY on
the states the phase names. Before the pull request: the office's pre-PR gate. The pull request bumps the version
(patch). **None of this applies to THIS docs pull request**, whose gate is `check-docs-cited-paths.py`,
`check-no-french.py`, `check-implementation-state.py`, `check-intent-map.py`, `check-bug-register.py` and `make
lint`.
