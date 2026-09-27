# Phase 25 — The Plex match waits on a disagreement, and each answer does what it says

**Born 2026-09-27 from the coherence triage's F3** (review-archive `coherence-2026-09-27.md` § F3), a new integer phase
after the paused follows' fold and before the menu button's badge. It repairs what L22a's phase 10 drew against
OPEN 9 = B, ruling 7 and ruling 3.

**Opening measure (estimate — RE-MEASURED at the opening; > 15 → cut):**

1. **Only a disagreement waits.** The mock files a card `blocked` on its Plex match only when Plex's match DIFFERS from
   the identity held (today `mocks/handlers/staging.ts` files any `plexMatch`). The card names BOTH sides (today the
   sentence only asks « est-ce bien lui ? »). **Star Trek's seed is re-derived as a real disagreement**; if that costs
   § 13 fidelity, **STOP D** (RULINGS 6 is the ruling it would revise).
2. **« Corriger » acts on Plex's match through demand E** and does not open the candidates screen
   (`features/acquisition/plex-verbs.ts`); the card STAYS in « À traiter » until the correction is answered, and the rung
   stays not done until Plex's corrected match is checked.
3. **« Confirmer » lays « vérifié dans Plex » DONE**, so a followed film leaves « Suivis » (ruling 3; `isVerifiedInPlex`
   needs the last rung done). R230 walks that confirmation, not only the `confirmInPlex` hook.
- Amends, in the same move: DESIGN § 2.2, § 3.3, R-L22-t, demand E, RULINGS 6 (a dated line), and
  `resolvePlexMatch`'s description (« Either answer takes the card off « À traiter » » is no longer true of « Corriger »).
- **Points ≈ 14** (seed re-derivation 2, the card's two-sided sentence 1, « Corriger » re-wired 3, the confirm rung 2,
  R-L22-t's new hold with mutation 3, R230's walk 1, the contract description 1, docs 1).

## Red today

**R-L22-t** gains « Corriger, then Back → the card is still in « À traiter » », and « a match that agrees with the
identity is not in « À traiter » ». **R230** gains « Confirmer on the followed film → it leaves « Suivis » ».

## Mutation

With the commit made first: file any `plexMatch` again → the agreement hold falls; « Corriger » takes the card off at the
tap → the Back hold falls; « Confirmer » leaves the rung pending → R230's walk falls.

## Oracle

`acq-card-blocked` / `acq-todo-loaded` (the two-sided sentence) and any state drawing Star Trek's card — named at the
opening.

## Commit

`fix(maquette-l22): the Plex match waits on a disagreement, and « Corriger » corrects it`
