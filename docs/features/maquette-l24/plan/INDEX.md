# L24 — the orphans: what no lot draws · PLAN

Design: `docs/features/maquette-l24/DESIGN.md`. Contract: `docs/reference/frontend-architecture.md` § 4, entry
`#### L24 — the orphans, what no lot draws`. The implementer is held to `docs/reference/implementer-office.md`; this
plan carries only what is the lot's own.

**Written 2026-09-29, on `main` at `e65130ab1`.** L24 opens after L23. Every figure below was taken by a command on
that tree; the implementer RE-TAKES each at the phase's real opening, because L16, L17, L18 and L23 land between —
a figure that moved is re-taken, a figure that no longer supports its phase's cut is STOP D.

---

## The stops

- **STOP A** — the oracle diverging on a state the phase did not name.
- **STOP B** — the pull request.
- **STOP C — LIVE.** Six questions are open (DESIGN § 5). A phase naming one is not begun before it is ruled; the
  answer is written into DESIGN § 5 and into that phase's file in ONE dated line each. Phases 1, 5, 6, 9, 10, 11,
  14 and 17 carry one; the others carry none.
- **STOP D** — a measurement that contradicts a home the design decided. Two are near already: `lib/addresses.ts`
  holds 395 non-blank lines of 400 (phases 5 and 9 add to it), and `mocks/handlers/staging.ts` holds 399 (so no
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
| 1 | [The contract](phase-01-the-contract.md) | contract | — | 9 / 7 | OPEN 3 |
| 2 | [The seeds](phase-02-the-seeds.md) | seed | — | 7 | — |
| 3 | [The mocks that move](phase-03-the-mocks-that-move.md) | mock | — | 12 | — |
| 4 | [A section says its read failed](phase-04-a-section-says-its-read-failed.md) | behaviour (S2) | c | 9 | — |
| 5 | [The journal and its exits](phase-05-the-journal-and-its-exits.md) | surface (S1) | b | 14 | OPEN 1 |
| 6 | [The journal's filter and counts](phase-06-the-journals-filter-and-counts.md) | surface (S1) | a | 13 | OPEN 1 |
| 7 | [A resolution arrives with candidates](phase-07-a-resolution-arrives-with-candidates.md) | surface (S5) | e | 10 | — |
| 8 | [The continuation is seen](phase-08-the-continuation-is-seen.md) | proof | f | 5 | — |
| 9 | [The former addresses](phase-09-the-former-addresses.md) | surface (S4) | d | 14 / 13 | OPEN 4 |
| 10 | [Identification, now](phase-10-identification-now.md) | proof or surface (S3) | + 1 | 12 / 4 | OPEN 3 |
| 11 | [A filling disk on the badge](phase-11-a-filling-disk-on-the-badge.md) | behaviour | + 1 | 5 / 0 | OPEN 2 |
| 12 | [The sheet says what it is](phase-12-the-sheet-says-what-it-is.md) | proof | h | 4 | — |
| 13 | [One completeness](phase-13-one-completeness.md) | source change | i | 9 | — |
| 14 | [The ladder's words](phase-14-the-ladders-words.md) | proof or surface | + 1 | 9 / 4 | OPEN 5 |
| 15 | [The title alone, every card](phase-15-the-title-alone-every-card.md) | proof | g | 5 | — |
| 16 | [No destruction without consent](phase-16-no-destruction-without-consent.md) | proof | j | 5 | — |
| 17 | [The desktop is fully functional](phase-17-the-desktop-is-fully-functional.md) | proof | k | 5 | OPEN 6 |
| 18 | [The records](phase-18-the-records.md) | records | — | 6 | — |
| 19 | [The close](phase-19-the-close.md) | close | — | 6 | — |

**Where a reading changes the cost, both are written, larger first**, and neither is chosen. **At the larger
reading of every open question: 159 points over 19 phases, mean ≈ 8.4, max 14** (phases 5 and 9). At the smaller:
138 points over 18 phases (phase 11 drops), mean ≈ 7.7. **OPEN 6 reading B adds three phases after 17** — a two-pane
layout for the journal, « À traiter » and the settings, ≈ 9 points each — which would read 186 over 22, mean ≈ 8.5.

---

## Why this order

**The contract first** (1): `scripts/compare-contracts.py --check` refuses a demand apart from its schema. **The
seeds second** (2), **the mocks third** (3): a handler with no seed answers nothing. **Système's failed section**
(4) comes before the journal because it touches one page already drawn and one mock scenario, the smallest
behaviour first. **The journal's rows before its filter** (5, 6): a filter has nothing to filter before
the rows exist. **S5 before the continuation** (7, 8): the continuation's proof walks a resolution from the act S5
adds as well as from « À traiter ». **The addresses after the journal** (9), because `/media?decision=` lands on it.
**The proofs last** (12, 14–17), each reading surfaces already drawn; **the records** (18) and **the close** (19)
end it.

---

## Gates

Per phase: the office's phase gate (`docs/reference/implementer-office.md` § « The gate »), with divergences ONLY on
the states the phase names. Before the pull request: the office's pre-PR gate. The pull request bumps the version
(patch). **None of this applies to THIS docs pull request**, whose gate is `check-docs-cited-paths.py`,
`check-no-french.py`, `check-implementation-state.py`, `check-intent-map.py` and `make lint`.
