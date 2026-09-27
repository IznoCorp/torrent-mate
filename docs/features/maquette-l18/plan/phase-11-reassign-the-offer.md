# Phase 11 — The reassign gesture — the offer

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `wc -l frontend/maquette/design/src/features/acquisition/panel-journey.ts frontend/maquette/design/src/features/acquisition/panel-follow.ts frontend/maquette/design/src/features/acquisition/journey-verbs.ts frontend/maquette/design/src/features/acquisition/card-gestures.ts frontend/maquette/design/src/features/acquisition/card-markup.ts frontend/maquette/design/src/lib/verbs.ts` → **112, 172, 116, 226, 109, 128**. `panel-journey.ts` offers **three acts** (`requeue`, `rescrape`, `seeSheet`); the descriptor form is `ui/panel/contract` (`registerProducer`, `blocs`, `actions`).
- `git grep -ci requester -- frontend/maquette/design/src` → no match today. **L22 phase 7 draws the requester line** (« ajouté par Izno, dans qBittorrent ») on `card-markup.ts`; L22's OPEN 11 = B sent the gesture here.
- **Reads OPEN 5**: A — an act « Réaffecter… » in the journey sheet and the follow's (no mark on the card, so every existing state is unmoved); B — the requester line is the control (a mark on the card: the states that draw a card diverge and are named in the oracle section).
- **Points ≈ 15.** the chooser panel descriptor, ≈ 55 new lines (6) + its verb, registered, ≈ 8 lines (1) + the entry point (OPEN 5): A — an act in two panels, ≈ 12 lines / B — the line becomes a control, ≈ 15 lines (1) + three sentences (title, the current requester, the confirmation naming the medium and the two accounts) (3) + one state, `acq-reassign-chooser` (1) + R-L18-i with its mutations (3).
- **What to cut if the opening measure exceeds 15.** At 15. Cut: the confirmation's sentence and the confirmation itself go to phase 12.

**DESIGN § 3.5.** The chooser lists the accounts by name, role and Plex link, the current requester marked, and a confirmation in the panel's idiom that names the medium and both accounts. **Absent for every account but the Operator, on its own cards too** (§ 17: the Member pilots, does not reassign). This phase draws the OFFER; the answer that moves the card is phase 12.

## Red today

**R-L18-i — the reassign offer**: on the Operator's card the gesture is offered and the chooser lists the accounts with the current requester marked; on every other identity, **on its own card too**, no trace of it in the DOM.

**Red against `main`**: no gesture exists.

## Move

The panel, the verb, the entry point, the state.

## Mutation

With the commit made first: offer it on the Member's own card → R-L18-i falls; drop the current-requester mark → falls.

## Register

—

## Oracle: states that diverge, declared by name

**None under reading A. Under reading B**: the states that draw a card (`acq-now-idle`, `acq-now-loaded` and the L22 states that draw a requester line) — « L18 § 3.5: the line is a control ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the Operator is offered the reassignment of a request`
