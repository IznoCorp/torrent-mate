# L16-bis — the Trackers page's correction, and Découvrir's header · PLAN

Design: `docs/features/maquette-l16bis/DESIGN.md`. The implementer is held to `docs/reference/implementer-office.md`;
this plan carries only what is the lot's own.

**Written 2026-09-29, on `main` at `f3d8fed01`** (L16 merged, #634). L16-bis opens BEFORE L17. Every figure below was
taken by a command on `f3d8fed01`; the implementer RE-TAKES each at the phase's real opening — a figure that moved is
re-taken, a figure that no longer supports its phase's cut is STOP D.

---

## The stops

- **STOP A** — the oracle diverging on a state the phase did not name.
- **STOP B** — the pull request.
- **STOP C — LIVE for nine questions.** DESIGN § 5's OPEN 1–9 are the operator's, ruled in one round before the lot
  opens. A phase naming one is not begun before it is ruled; the answer is written into DESIGN § 5 and into that
  phase's file in ONE dated line each. Phases 1, 5, 7, 10, 11, 14, 15 and 17 carry one; the others none.
- **STOP D** — a measurement that contradicts a home the design decided. Near already: `ui/variants/controls.ts`
  holds **397** non-blank lines of 400 (phase 5 moves the tab floor INTO `segmentTab`, never a new factory there);
  `ui/variants/surfaces.ts` holds **373** (phase 6's legend lands in its own `ui/` module, not there).

Anything outside this plan and its design: STOP, and ask the orchestrator first.

---

## Points, and the mean

The scale is L23's (`docs/features/maquette-l23/plan/INDEX.md` « Points »): a line edited 1 per 5, written new 1 per
10; a new rule with its mutation 3; a rule re-aimed 1; a named state 1 (re-using a seed) or 2 (a new seed row); an
operation declared new 2, edited 1; a mock route new 2, re-answered 1; a sentence rewritten 1; a documentation row 1.

A phase whose re-measure at its opening exceeds 15 is cut there, never begun, and the orchestrator told.

| # | Phase | Kind | Rule | Points | STOP C |
| ---: | --- | --- | --- | ---: | --- |
| 1 | [The contract](phase-01-the-contract.md) | contract | — | 9 / 8 | OPEN 1 |
| 2 | [The seeds](phase-02-the-seeds.md) | seed | — | 12 | — |
| 3 | [The mocks that move](phase-03-the-mocks-that-move.md) | mock | — | 12 | — |
| 4 | [« Torrents » first](phase-04-torrents-first.md) | behaviour (S1) | a | 5 | — |
| 5 | [One tab component](phase-05-one-tab-component.md) | component (S1) | j | 11 / 0 | OPEN 7 |
| 6 | [The legend moves to ui](phase-06-the-legend-moves-to-ui.md) | move | — | 4 | — |
| 7 | [The legend on Trackers](phase-07-the-legend-on-trackers.md) | surface (S3) | c | 9 | OPEN 5 |
| 8 | [The torrent card](phase-08-the-torrent-card.md) | surface (S4) | d | 14 | — |
| 9 | [The card's facts](phase-09-the-cards-facts.md) | surface (S4) | d (+ holds) | 11 | — |
| 10 | [The poster and the panel](phase-10-the-poster-and-the-panel.md) | surface (S4, S5) | e | 14 / 12 | OPEN 2 |
| 11 | [The swipe](phase-11-the-swipe.md) | gesture (S6) | f | 11 / 8 | OPEN 9 |
| 12 | [The tracker selector](phase-12-the-tracker-selector.md) | surface (S2) | b | 13 | — |
| 13 | [The switch, one write two doors](phase-13-the-switch.md) | surface (S7) | g | 12 | — |
| 14 | [A failing tracker says why](phase-14-a-failing-tracker-says-why.md) | behaviour (S7) | h | 13 / 10 | OPEN 6 |
| 15 | [The tracker row and the one chevron](phase-15-the-tracker-row.md) | surface (S7) | — (re-aims) | 13 / 5 | OPEN 3, 4 |
| 16 | [The design system, swept](phase-16-the-design-system-swept.md) | refactor | i | 7 | — |
| 17 | [Découvrir's header](phase-17-discovers-header.md) | surface (S8) | k | 12 / 9 | OPEN 8 |
| 18 | [The records](phase-18-the-records.md) | records | — | 7 | — |
| 19 | [The close](phase-19-the-close.md) | close | — | 6 | — |

**Where a reading changes the cost, both are written, larger first**, and neither is chosen. **At the larger readings:
195 points over 19 phases, mean ≈ 10.3, max 14** (phases 8 and 10). **At the smaller: 164 points over 18 phases**
(phase 5 moves to the conformity train under OPEN 7 B), **mean ≈ 9.1, max 14.** OPEN 4 costs the same either way.
**The midpoint** — the full suite, its falls repaired before the next phase — is after phase 10.

---

## Why this order

**The contract first** (1): `scripts/compare-contracts.py --check` refuses a field apart from its schema. **The seeds
second** (2), **the mocks third** (3): a handler with no seed answers nothing. **The landing** (4) is the smallest
behaviour and the operator's first point; **the tab component** (5) follows on the same strip. **The legend is moved
before it is drawn** (6, 7): a move is its own kind. **The card before its facts, its facts before its taps** (8, 9,
10), and **the taps before the swipe** (11), which opens the same confirmation the panel does. **The selector** (12)
reads the card list already redrawn. **The roster's switch** (13) before **its failure** (14) and **its form** (15).
**The sweep** (16) deletes what phases 5–15 left unused. **Découvrir** (17) touches another page and comes last of the
surfaces; **the records** (18) and **the close** (19) end it.

---

## Gates

Per phase: the office's phase gate (`docs/reference/implementer-office.md` § « The gate »), with divergences ONLY on
the states the phase names. The harness budget (≤ 0.6 × product lines) is read at the midpoint and the close. Before
the pull request: the office's pre-PR gate; the pull request bumps the version (patch). **None of this applies to
THIS docs pull request**, whose gate is `check-docs-cited-paths.py`, `check-no-french.py`,
`check-implementation-state.py`, `check-intent-map.py` and `make lint`.
