# Phase 29 — « Abandonner » on a follow's card sets the release aside and searches another

**Born 2026-09-27 from M1** (the auditor's decision-coherence round, `review-archive/rulings-coherence-2026-09-27.md`),
a new integer phase — it touches no phase still to come.

**Opening measure (estimate — RE-MEASURED at the opening):**

- On a FOLLOW's card, « Abandonner » quarantines the folder (OPEN 10, unchanged) AND the release joins the releases
  already tried for that item (the engine has the list); the item goes back to « cherché » — the follow goes on (a
  series' follow never ends alone, ruling of 2026-09-15; § 14.1 « récupéré ? non → changement de release »). On a
  one-off arrival's card, the card closes (today's behaviour). The confirmation says what follows: « une autre release
  sera cherchée ». Filed in the quarantine's demand (DESIGN § 6.2).
- **Round 10 Q6 = C** is NOT built here (the mock keeps one requester per card): DESIGN carries its dated line —
  « Abandonner » withdraws the request of whoever abandons, and the quarantine happens only when the LAST requester
  abandons (L18 builds it).
- **Points ≈ 9** (the confirmation's sentence 1, the mock's follow branch 2, the demand 1, R-L22-u's hold + mutation 3,
  state 1, oracle 1).

## Red today

R-L22-u (`abandon_quarantines.py`) gains « on a follow's card: the item reads « cherché » again and the abandoned
release is not offered again ».

## Mutation

Close the follow's card like a one-off → falls.

## Commit

`feat(maquette-l22): « Abandonner » on a follow's card searches another release`
