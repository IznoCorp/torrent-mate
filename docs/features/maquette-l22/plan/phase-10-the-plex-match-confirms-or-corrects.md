# Phase 10 — The Plex match is confirmed or corrected

**Opening measure (2026-09-26, on `ba6a36cc9`; a phase born of the round-5 rulings, cut out of the first drawing's phase 9 by
OPEN 9):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`
  → **63** operations before this phase (64 after); `sed -n 20,29p docs/reference/frontend-backend-demands.md` → required and
  missing **16** (17 after). `git grep -w -i -c plex -- frontend/maquette/contract/openapi.json frontend/maquette/design/src/mocks`
  → **no match** (`-w`, because the bare substring also matches « Duplex » and « décomplexé » in the media seeds): nothing in the
  contract or the mocks names a Plex match. The patterns to follow: `git grep -n 'requeueJourney' -- frontend/maquette/design/src/mocks/handlers`
  → `acquisition-verbs.ts:242` (a handler that moves the queue); `features/acquisition/follow-verbs.ts:311`
  (`registerVerb("follow", …)`, a verb that reads the element's `data-*`). `todo-tab.tsx` exists after phase 9 with two sections.
- **Points ≈ 13.** The demand E operation declared new 2; its mock route new 2 (the answer MOVES the card); the seed row or its
  `x-unseeded` marker 1; `todo-tab.tsx`'s third section ≈ 12 lines written 1; the two verbs (« Confirmer », « Corriger ») ≈ 30
  lines written 3; the words as `fr.json` keys 1; the new rule with its mutations 3. **If the steward's STOP D word is a new
  seed row rather than a derivation or a marker, the seed costs 2 and the phase 14 — still under the ceiling.**
- **Found (2026-09-26) — STOP D at this opening.** DESIGN § 3.3 draws a section for « un match Plex à confirmer »; **no seed
  names a Plex mismatch** (the command above, no match). The phase reports it to the steward with the command and does NOT
  improvise a seed (§13): (a) a derivation shown as one, or (b) the section drawn from its state with the seed marked
  `x-unseeded`. The contract's own word applies: « nothing was invented here » and « nobody looked » are different things.

OPEN 9 (ruled B, 2026-09-26): the « match Plex à confirmer » card offers « Confirmer » and « Corriger » ON THE PLEX MATCH ITSELF,
and a FIFTH demand row — the confirm/correct verb on the match — is proposed in DESIGN § 6.2 (E). **This phase files it, as its
first act**: a demand is filed by editing the contract, and phase 1 could not carry it (12 + a declared operation and a mock
route is 16, over the ceiling).

## Red today

**R-L22-t — « Confirmer » / « Corriger » on the Plex match** (DESIGN § 5), on `acq-todo-loaded`:

- the Plex-match card offers « Confirmer » and « Corriger » on the match itself;
- a tap on « Confirmer » is ANSWERED on the network (`window.__mocks.answered()`, the operation of demand E) and the card leaves
  « À traiter »; the same for « Corriger », through its own answer;
- R-L22-h is re-read with the third kind: the card is `blocked`, and it is in « À traiter » and in no other tab.

**Red against `main`**: no such card, no such verb, no such operation.

## Move

1. **The contract first** (D7): declare demand E in `frontend/maquette/contract/openapi.json` (`POST
   /api/acquisition/journeys/{infoHash}/plex-match`, `resolvePlexMatch` — the path and the id are proposals and adjust), then
   `python3 scripts/compare-contracts.py --write`, `--check`, and `npm --prefix frontend/maquette/design run generate-contract-types`.
   **Read the counters and put them in the report, before and after** (« required and missing » moves 16 → 17).
2. The mock route answers it and MOVES the card off « À traiter » (D7: a mock that answers without moving certifies nothing);
   the seed per the steward's STOP D word, with `python3 scripts/check-mock-seeds.py` in the same commit.
3. `todo-tab.tsx` draws the third section; the two verbs are registered as the follow verb is, reading the card's identity from
   the element. **How « Corriger » names the right match is the drawing's, made here against the mock and the row; it is not
   decided in the design** (DESIGN § 3.3), and it adjusts.
4. The card names the match Plex made and the identity the pipeline holds (DESIGN § 3.3); the words live in `fr.json`.

## Mutation

With the commit made first: make the verb toast without calling → the network hold falls; leave the card in the tab after the
answer → it falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-todo-loaded` — recorded at phase 9, it gains its third section — accepted with « L22 § 3.3: the Plex-match section and its
two verbs ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `python3 scripts/check-mock-seeds.py`; `python3 scripts/compare-contracts.py --check`.

## Commit

`feat(maquette-l22): a Plex match is confirmed or corrected on its card`
