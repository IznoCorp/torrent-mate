# Phase 15 — The quality profile of an acquisition

**Amended 2026-09-27** (renumbered from the first drawing's phase 14): **round 10 Q6, precised** — quality is a
ROLE right (`acquisition.quality.own`), several requesters may hold it on the same acquisition, and only THOSE
requesters' settings enter « the highest wins »; a requester without the right follows the default profile. The
first drawing's single-requester assumption is corrected. **A sibling phase (16) now carries PAUSE**, the same
shape, kept separate to hold both at ≤ 15. Re-estimated at **14** (unchanged from the first drawing — the
multi-requester comparison replaces, rather than adds to, the single-requester write).

**Opening measure (2026-09-27, on `46806a88d`) — re-take before moving anything:**

- **Commands.** `wc -l frontend/maquette/design/src/features/releases/quality-screen.tsx` → **306**; the screen writes `state.profile` with `writeUiState` (`sed -n 78,80p`) — **a client-store write, not a served one**. `python3 -c "import re;print(len(re.findall('quality',open('frontend/maquette/contract/openapi.json').read(),re.I)))"` → 0.
- `sed -n 198,212p frontend/maquette/design/src/app/history-bridge.ts` → the screen is reached through the screens door (`profile: (title, replace)` → `/quality/$name`); `frontend/maquette/design/src/lib/addresses.ts:71` maps `/quality/$name` to `acq`. The entry points are re-taken at the opening (`git grep -n "profile(" -- frontend/maquette/design/src`).
- `backend-demands-architecture.md` § 3: the override is per acquisition, never an edit of the profile, which stays the Operator's configuration.
- **Points ≈ 14.** `quality-screen.tsx` writes through the operation, ≈ 20 lines edited (4) + the `setAcquisitionQuality` handler, new (2) + the query and verb door, ≈ 10 new lines (1) + the offer gated at the screen's entry points (1) + the sentence that says « for THIS acquisition » (1) + two states — `quality-own-offered`, `quality-own-absent` (2) + R-L18-l with its mutations (3).

**DESIGN § 3.4 point 5, § 0.1 row 9.** « Régler le profil de qualité d'une acquisition » is a choice for THIS acquisition, never the edit of the profile: the screen says so, and its write becomes a served one (demand K) — until now it was the interface's own state, which is not a right that can be refused. Offered where `acquisition.quality.own` holds, on one's own acquisition only: the Member always, the guest exactly when the option is ON (**the pair of § 2.2**), the Operator on any.

## Red today

**R-L18-l — the quality choice of an acquisition**: offered on one's own acquisition for the Member, and for the guest exactly when the option is ON; absent on another's; the write is ANSWERED (demand K) and changes only THAT acquisition's choice; no act edits the profile itself.

**Red against `main`**: the screen writes the UI store for every account.

## Move

The screen's write, the handler, the gate, the sentence, the states.

## Mutation

With the commit made first: give the guest the offer without the option → R-L18-l falls; write the choice into the profile → falls.

## Register

—

## Oracle: states that diverge, declared by name

**`quality-*` states** — the screen's existing states, if any name the screen, diverge only through the sentence (« L18 § 3.4: for this acquisition »). Any other divergence is STOP A.

## Gate

Per INDEX « Gates ».

## Commit

`feat(maquette-l18): the quality choice is per acquisition, served, and offered by right`
