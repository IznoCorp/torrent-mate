# Phase 15 — « Suivre », proposed and never done

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** The follow act exists: `registerVerb("follow", …)` at `features/acquisition/follow-verbs.ts:311` (reads
  `data-fkind` and the element's identity), backed by `createFollow` (`mocks/handlers/acquisition.ts:102`). The card's
  markup takes an optional foot (`MediumCardFoot`, `card-markup.ts`); the media panel is DERIVED from what is true
  about the medium (README § « One card, one behaviour »: « followed, incomplete, in the library, to grab, blocked, has a
  sheet »). `python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/follows.json'))))"`
  → **14** follows (9 shows, 5 movies).
- **Points ≈ 8.** The offer as a foot on the arrival card ≈ 10 lines 2; the same act in the panel's derivation ≈ 10 lines
  2; R-L22-l with its mutations 3; one state (`acq-card-follow-offer`) 1.

Ruling 1: an arrival creates a PUNCTUAL acquisition, never a follow. « Suivre » is PROPOSED on the card of an unfollowed
IDENTIFIED SERIES; nothing is followed until it is tapped. **No new verb**: the foot emits the existing `data-follow`.

## Red today

**R-L22-l — « Suivre » proposed, never done**: an arrival of an identified series changes the follows list by NOTHING;
the offer is on the card and in its panel; a tap changes the list by exactly ONE follow and the offer goes; **no offer on a
film, on a card without identity (nothing to follow yet), or on a series already followed**.

**Red against `main`**: an arrival card carries no offer.

## Move

The foot on an arrival card of an identified, unfollowed series; the same action in its panel; the named state
`acq-card-follow-offer`. Whether the arrival's card also shows in « Suivis » is OPEN 3 and is not decided here: the tap
creates a follow like any other, and « Suivis » lists follows.

## Mutation

With the commit made first: follow on arrival → R-L22-l falls; offer it on a film → it falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded` (an arrival series card gains a foot) accepted with « L22 § 3.5: the proposal »; anything
else is STOP A.

## Gate

Per INDEX « Gates »; the follows rules (`acq-follows-*` readers, 37 files mention the states) are re-run by name.

## Commit

`feat(maquette-l22): a series that arrived is offered « Suivre » and never followed unasked`
