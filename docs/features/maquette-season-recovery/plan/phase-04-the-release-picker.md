# Phase 4 — The release picker's refusal (S5, S6's picker)

**Opening measure** (taken on `9234341fc`; re-taken at the real opening):
`grep -n "data-pick-release" frontend/maquette/design/src/features/releases/releases-screen.tsx` → **115**;
`grep -cv '^\s*$' frontend/maquette/design/src/features/releases/releases-screen.tsx` → **137**; Silo's releases after
phase 1: 4 × `S03E07` and the season pack.

## What changes

1. **The refusal** (S5): while a recovery of season N is live for the title, each release naming an episode of
   season N keeps its row, tags and score, and in its foot's place draws the chip « Couvert par la saison 3 » and
   « Voir la carte de la saison » (`actionButton({ kind: "cardFoot" })`, phase 3's pointer reused); the pack and the
   other seasons' releases keep their act.
2. **All covered**: « 4 candidats — tous couverts par la saison 3 », the empty note unchanged.
3. **The end**: before the ask and after the season reached the library, `S03E07` takes again.
4. **A film**: its release list draws no refusal — a recovery is a series' (the film / series row of DESIGN § 0.3).

## Acceptance — red first on the old code, then green

- **R-season-recovery-d** — red on `releases-season-recovering` (the act kept); a hold on a film's releases, green
  before and after; **R-season-recovery-f** (the refusal and the row's mark are the same `ui` chip; the pointer a
  panel `note` + `actions`) — red if drawn with a feature's own variant.
- Re-aimed OUT LOUD: `release_candidates.py`, `release_take_sentence.py` (a subject on Silo during the recovery moved
  to a title with none).
- Named states: every S5 id.
- Walked by finger: a covered release → « Voir la carte de la saison » → the card → Retour → the release screen.

## Commit

`feat(maquette-season-recovery): the release picker says which releases the season's recovery covers`
