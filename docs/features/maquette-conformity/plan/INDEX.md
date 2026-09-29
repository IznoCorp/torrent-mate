# maquette-conformity — one need, one component; every state at every width · PLAN

Design: the conformity reading, `/Users/izno/dev/review-archive/conformity-80/REPORT.md` — § B (the deviations, B.5
the responsive risks), § D.1 (the sixteen conversions, their files and their oracle), § D.2 (what is NOT a
conversion). It is cited, never copied. The implementer is held to `docs/reference/implementer-office.md`; this plan
carries only what is the train's own. Orders served: 80 (one need, one component) and 85 (the responsive rule, which
replaces order 60).

**Written 2026-09-29, on `main` at `660049325`** (#640). Every figure below was taken by a command on `660049325`;
each phase RE-TAKES its figures at its real opening — a figure that moved is re-taken, a figure that no longer
supports its phase's cut is STOP D.

## The stops

- **STOP A** — the oracle diverging on a state the phase did not name.
- **STOP B** — the pull request.
- **STOP C — the operator's round.** RULED 2026-09-29 and in this plan: D.1 #2 (OPEN 1 = A) → phase 12, the state
  words (OPEN 2 = A) → phase 13, the notice (OPEN 3 = A) → phase 16, D.1 #14 (OPEN 4 = A) → phase 22, D.1 #15
  (OPEN 8 = A) → phase 23, D.1 #7 (OPEN 9 = A) → phase 25; the operator's poster defect → phase 24, « Récents » filtered → phase 8, the raw log (OPEN 10 = A) → phase 6. OPEN 7
  (Découvrir's swipe) goes to L16-bis, not here. Nothing of D.1 waits any more. Reaching them first is a STOP, said.
- **STOP D** — a measurement that contradicts a home. Near already (non-blank lines, `grep -cv '^\s*$'`, ceiling
  400): `ui/variants/controls.ts` **397**, `ui/variants/frame.ts` **397**, `ui/variants/surfaces.ts` **373**,
  `features/media/season-list.tsx` **390**. A phase landing in one of them moves lines OUT in the same commit or
  lands in a module of its own.
- Anything outside this plan and the report's § D.1: STOP, and ask the orchestrator first.

**Rules** are lettered `R-conformity-a` … in birth order (the RESUME maps letter → file); a hold on a surface an
existing rule owns is a HOLD in that rule's file (office, order 52).

## Points, and the mean

L23's scale (`docs/features/maquette-l23/plan/INDEX.md` « Points »): a line edited 1 per 5, written new 1 per 10; a
new rule with its mutation 3; a rule re-aimed 1; a guard arm with its test 3; a sentence rewritten 1.

| # | Phase | Kind | D.1 | Rule / arm | Points |
| ---: | --- | --- | --- | --- | ---: |
| 1 | [The responsive rule](phase-01-the-responsive-rule.md) | rule | — (order 85) | a | 14 |
| 2 | [The runs list](phase-02-the-runs-list.md) | conversion | #13 | a green on `runs-list` | 9 |
| 3 | [The requester line](phase-03-the-requester-line.md) | defect | found by a | a | 8 |
| 4 | [The bar's label at 320 px](phase-04-the-bar-label.md) | defect | found by a | a | 7 |
| 5 | [The card's title](phase-05-the-card-title.md) | defect, § 12 | B.5 R2 | a | 12 |
| 6 | [The raw log](phase-06-the-raw-log.md) | defect, ruled | B.5 R13, OPEN 10 | a | 7 |
| 7 | [The tabs](phase-07-the-tabs.md) | conversion | #1 | b + tablist arm | 14 |
| 8 | [« Récents » filtered](phase-08-recents-filters.md) | behaviour, decided | the operator's | s | 10 |
| 9 | [The fold chevron](phase-09-the-fold-chevron.md) | conversion | #3 | chevron arm | 12 |
| 10 | [The switch](phase-10-the-switch.md) | conversion | #4 | c + switch arm | 11 |
| 11 | [The status chip](phase-11-the-status-chip.md) | conversion | #5 | d | 12 |
| 12 | [« actif / inactif »](phase-12-the-on-off-pair.md) | behaviour, ruled | #2 | e | 13 |
| 13 | [The state words](phase-13-the-state-words.md) | behaviour, ruled | OPEN 2 | f | 14 |
| 14 | [A fact with its state](phase-14-a-fact-with-its-state.md) | conversion | #6 | g | 8 |
| 15 | [The empty surface](phase-15-the-empty-surface.md) | conversion | #10 | h | 7 |
| 16 | [The notice](phase-16-the-notice.md) | behaviour, ruled | OPEN 3 | i | 12 |
| 17 | [The back control](phase-17-the-back-control.md) | conversion | #12 | j | 6 |
| 18 | [The count badge](phase-18-the-count-badge.md) | conversion | #8 | k | 10 |
| 19 | [The legend](phase-19-the-legend.md) | conversion | #9 | l | 10 |
| 20 | [The topic row](phase-20-the-topic-row.md) | conversion | #11 | m | 11 |
| 21 | [The tokens](phase-21-the-tokens.md) | conversion | #16 | n | 13 |
| 22 | [The segmented choice](phase-22-the-segmented-choice.md) | conversion | #14 | o | 9 |
| 23 | [The primary buttons](phase-23-the-primary-buttons.md) | conversion, ruled | #15 | p | 8 |
| 24 | [The candidate's poster](phase-24-the-candidate-poster.md) | defect | the operator's | q | 13 |
| 25 | [The status dot](phase-25-the-status-dot.md) | conversion, ruled | #7 | r | 11 |
| 26 | [The close](phase-26-the-close.md) | close | — | — | 6 |

`python3 -c "print(14+9+8+7+12+7+14+10+12+11+12+13+14+8+7+12+6+10+10+11+13+9+8+13+11+6)"` → **267 points over 26 phases, mean ≈ 10.3, max 14**.
**The midpoint** — `--contracts` and the full suite, its real falls repaired before phase 14 opens — sits after
phase 13. **The responsive full sweep** runs at phase 1 (its cost measured there), at the close and in CI; between,
each phase runs it on the states of the surfaces it touches (phase 1 fixes the flag that selects them).

## Why this order

The brief's, which is the operator's: **the rule first** (1), read RED on the runs list, so every later phase is
measured at every width; **the runs list** (2) is that red's own repair and the operator's 17:04 report; **the three defects**
the rule's first pass found (3, 4, 5 — § 12's title — and 6, the raw log) are the train's own, by the orchestrator's ruling; **the tabs** (7) are the operator's 17:17 order (« un seul composant qu'on adapte ») and the component L16-bis waits for
(DECIDED 7); **the chevron and the switch** (9, 10) carry the two guard arms L16-bis § 1.9 specified for this train;
then the conversions by how many surfaces they touch. One kind of change per phase: a conversion proves « nothing
observable changed » through the oracle's region comparison, except the ONE visible change the report names for it.

## What this train does not do

Report § D.2 in full (the silent loading / error drawings, every missing case, the notice component, Découvrir's
swipe, NAVIGATION, the season recovery; § 12's card title, ruled the train's own, is phase 5); « Found in passing » except L16-bis DESIGN
§ 1.7 / § 1.8's switch, corrected in phase 5; production `frontend/src`; the backend. A named state the report's
oracle names but the tree lacks (`acq-add-by-id`, `mediasheet-season-not-detailed`) is the case catalogue's
(#35, #76): the hold drives the case by finger inside its rule instead.
