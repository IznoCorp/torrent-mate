# Phase 14 — Own tunnel, read-only on the others

**Amended 2026-09-27** (renumbered from the first drawing's phase 13): **F27** — the guard now checks MEMBERSHIP
in the target's `requesters[]` list, never equality with a single requester field. `acquisition.pilot.own`'s acts
are offered where the caller is AMONG the requesters; absent, and refused `403`, otherwise; `acquisition.pilot.any`
(Admin) on every card regardless. Re-estimated at **14** (unchanged).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `grep -c "translate(" frontend/maquette/design/src/features/acquisition/panel-journey.ts` and `sed -n 84,100p frontend/maquette/design/src/features/acquisition/panel-journey.ts` → the journey sheet's acts (`requeue`, `rescrape`, `seeSheet`); `panel-follow.ts` (172 lines) draws the follow's acts.
- The operations behind the acts (`git grep -n -E "requeueJourney|rescrapeJourney|takeQueued|grabForFollow|searchForFollow|grabSeasonForFollow" -- frontend/maquette/design/src/features`): six operations of `acquisition.pilot.own` (DESIGN § 1.2).
- **Does not exist on this head**: the requester line (L22 phase 7); the target's requester is what the guard of phase 4 must now look up — the guard was right-only until this phase.
- **Points ≈ 14.** `panel-journey.ts`: the acts by ownership, ≈ 8 lines (2) + `panel-follow.ts`: the same, ≈ 8 lines (2) + `card-gestures.ts` / the card's foot, ≈ 6 lines (1) + the read-only line (markup and its sentence) (2) + the guard resolves the target's requester, ≈ 25 new lines in the mock (3) + R-L18-k with its mutations (3) + one state, `acq-card-read-only` (1).

**DESIGN § 3.4 points 3 and 4.** The acts of `acquisition.pilot.own` are offered on a card the account requested and ABSENT on the others'; on another's card one line says the card is read-only for this account — **§ 17 point 2 applied to a card: hiding the acts would mislead, they exist for the requester**. The Operator holds `acquisition.pilot.any`. The guard's ownership check is the one place the mock resolves « own ».

## Red today

**R-L18-k — own tunnel, both sides**: on the Member's own card the acts are offered and answer; on another's card (option ON) they are absent, the line says the card is read-only, and the same operations forced answer `403`; the Operator holds them on both.

**Red against `main`**: every account is offered every act.

## Move

The acts' filter, the line, the ownership resolution, the state.

## Mutation

With the commit made first: offer an act on another's card → R-L18-k falls; make the guard right-only again → the forced-call hold falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-card-read-only` is new. The Operator's card states diverge only if the read-only line reaches them — it must not. Any divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): a card's tunnel is piloted by its requester and read-only for the others`
