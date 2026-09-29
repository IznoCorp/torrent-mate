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
- **STOP C — the operator's round, CLOSED 2026-09-29.** In this plan: D.1 #2 (OPEN 1 = A) → phase 13, the state
  words (OPEN 2 = A) → 14, the notice (OPEN 3 = A) → 17, D.1 #14 (OPEN 4 = A) → 23, D.1 #15 (OPEN 8 = A) → 24,
  D.1 #7 (OPEN 9 = A) → 25, the raw log (OPEN 10 = A) → 7, « Récents » and « Incomplets » filtered (Q20) → 9, the
  WebKit pass (auditor's order 89) → 2. OPEN 7 (Découvrir's swipe) went to L16-bis. The operator's own defects
  (the iPhone hamburger, the Appearance selector, the candidate's poster) went to the **defects fast lane**, a wagon
  with its own pull request (the steward's decision, 2026-09-29) — the hamburger's red stays in the rule's owed list
  with that owner.
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
| 2 | [The WebKit pass](phase-02-the-webkit-pass.md) | rule | order 89 | a | 12 |
| 3 | [The runs list](phase-03-the-runs-list.md) | conversion | #13 | a green on `runs-list` | 9 |
| 4 | [The requester line](phase-04-the-requester-line.md) | defect | found by a | a | 8 |
| 5 | [The bar's label at 320 px](phase-05-the-bar-label.md) | defect | found by a | a | 7 |
| 6 | [The card's title](phase-06-the-card-title.md) | defect, § 12 | B.5 R2 | a | 12 |
| 7 | [The raw log](phase-07-the-raw-log.md) | defect, ruled | B.5 R13, OPEN 10 | a | 7 |
| 8 | [The tabs](phase-08-the-tabs.md) | conversion | #1 | b + tablist arm | 14 |
| 9 | [« Récents », « Incomplets » filtered](phase-09-recents-filters.md) | behaviour, decided | the operator's, Q20 | s | 13 |
| 10 | [The fold chevron](phase-10-the-fold-chevron.md) | conversion | #3 | chevron arm | 12 |
| 11 | [The switch](phase-11-the-switch.md) | conversion | #4 | c + switch arm | 11 |
| 12 | [The status chip](phase-12-the-status-chip.md) | conversion | #5 | d | 12 |
| 13 | [« actif / inactif »](phase-13-the-on-off-pair.md) | behaviour, ruled | #2 | e | 13 |
| 14 | [The state words](phase-14-the-state-words.md) | behaviour, ruled | OPEN 2 | f | 14 |
| 15 | [A fact with its state](phase-15-a-fact-with-its-state.md) | conversion | #6 | g | 8 |
| 16 | [The empty surface](phase-16-the-empty-surface.md) | conversion | #10 | h | 7 |
| 17 | [The notice](phase-17-the-notice.md) | behaviour, ruled | OPEN 3 | i | 12 |
| 18 | [The back control](phase-18-the-back-control.md) | conversion | #12 | j | 6 |
| 19 | [The count badge](phase-19-the-count-badge.md) | conversion | #8 | k | 10 |
| 20 | [The legend](phase-20-the-legend.md) | conversion | #9 | l | 10 |
| 21 | [The topic row](phase-21-the-topic-row.md) | conversion | #11 | m | 11 |
| 22 | [The tokens](phase-22-the-tokens.md) | conversion | #16 | n | 13 |
| 23 | [The segmented choice](phase-23-the-segmented-choice.md) | conversion | #14 | o | 9 |
| 24 | [The primary buttons](phase-24-the-primary-buttons.md) | conversion, ruled | #15 | p | 8 |
| 25 | [The status dot](phase-25-the-status-dot.md) | conversion, ruled | #7 | r | 11 |
| 26 | [The close](phase-26-the-close.md) | close | — | — | 6 |

`python3 -c "print(14+12+9+8+7+12+7+14+13+12+11+12+13+14+8+7+12+6+10+10+11+13+9+8+11+6)"` → **269 points over 26 phases, mean ≈ 10.3, max 14**.
**The midpoint** — `--contracts` and the full suite, its real falls repaired before phase 15 opens — sits after
phase 14. **The responsive full sweep** runs at phase 1 (its cost measured there), at the close and in CI; between,
each phase runs it on the states of the surfaces it touches (phase 1 fixes the flag that selects them).

## Why this order

The brief's, which is the operator's: **the rule first** (1), read RED on the runs list, so every later phase is
measured at every width; **its WebKit pass** (2) reads the iPhone's engine; **the runs list** (3) is the first red's
own repair and the operator's 17:04 report; **the defects the rule found** (4, 5, 6 — § 12's title — and 7, the raw
log) are the train's own, by the orchestrator's ruling; **the tabs** (8) are the operator's 17:17 order (« un seul
composant qu'on adapte ») and the component L16-bis waits for (DECIDED 7), and « Récents » filtered (9) rebuilds the
same head; **the chevron and the switch** (10, 11) carry the two guard arms L16-bis § 1.9 specified for this train;
then the conversions by how many surfaces they touch. One kind of change per phase: a conversion proves « nothing
observable changed » through the oracle's region comparison, except the ONE visible change the report names for it.

## What this train does not do

Report § D.2 in full (the silent loading / error drawings, every missing case, the notice component, Découvrir's
swipe, NAVIGATION, the season recovery; § 12's card title, ruled the train's own, is phase 6); « Found in passing » except L16-bis DESIGN
§ 1.7 / § 1.8's switch, corrected in phase 11; production `frontend/src`; the backend. A named state the report's
oracle names but the tree lacks (`acq-add-by-id`, `mediasheet-season-not-detailed`) is the case catalogue's
(#35, #76): the hold drives the case by finger inside its rule instead.
