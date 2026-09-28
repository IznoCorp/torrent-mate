# Phase 17 — « Suivre », proposed and never done

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** The follow act exists: `registerVerb("follow", …)` at `features/acquisition/follow-verbs.ts:311` (reads
  `data-fkind` and the element's identity), backed by `createFollow` (`mocks/handlers/acquisition.ts:102`). The card's
  markup takes an optional foot (`MediumCardFoot`, `card-markup.ts`); the media panel is DERIVED from what is true
  about the medium (README § « One card, one behaviour »: « followed, incomplete, in the library, to grab, blocked, has a
  sheet »). `python3 -c "import json;print(len(json.load(open('frontend/maquette/design/src/mocks/seeds/follows.json'))))"`
  → **14** follows (9 shows, 5 movies).
- **Points ≈ 8.** The offer as a foot on the arrival card ≈ 10 lines 2; the same act in the panel's derivation ≈ 10 lines
  2; R-L22-l with its mutations 3; one state (`acq-card-follow-offer`) 1.
- **Re-measured (2026-09-26, on `ba6a36cc9`, after the eleven rulings).** The commands above re-run: `registerVerb("follow", …)` at
  `follow-verbs.ts:311`, `createFollow` in the handlers, **14** follows in `follows.json`. **Points 8 → 8; OPEN 3 (ruled A) adds a
  hold and a mutation to R-L22-l, inside its 3, and no code**: `follows-tab.tsx` reads `useFollows` alone (line 50), so « Suivis »
  can draw no arrival card by construction, and the rule holds the absence against a later change. Its subjects are real seed
  rows: `python3 -c "import json;b='frontend/maquette/design/src/mocks/seeds/';f={x['title'] for x in json.load(open(b+'follows.json'))};print(sorted(r['title'] for n in ('moving','settled','settled-loaded') for r in json.load(open(b+n+'.json')) if r['title'].split(' (')[0] in f))"`
  → `['Furious', 'President Curtis', 'Star Trek: Strange New Worlds (2022)']`; « President Curtis » and « Star Trek: Strange New
  Worlds (2022) » are arrivals of followed series, and « Furious » (a film carrying a series' identifiers, B-549, not this lot's) is
  not used as a subject.

- **Re-measured 2026-09-27 at its opening, on `bfe7e254b`:** ≈ 10. Since 14-bis a shelved arrival is drawn nowhere in Acquisition, so the one real subject is « Les Zinzins de l'Espace » — an arrival of the dense « En vol », carrying a TVDB identifier (a series) and matched by no follow; a series is known by its TVDB identifier and a follow by any shared provider identifier (`features/acquisition/follow-offer.ts`, ONE derivation for the foot and the panel). States declared: the dense « En cours » body — `acq-now-loaded`, and `acq-card-rungs`, `acq-card-waiting` (born in L22a after this file) — « L22 § 3.5: the proposal ». Rule label l = R229.

Ruling 1: an arrival creates a PUNCTUAL acquisition, never a follow. « Suivre » is PROPOSED on the card of an unfollowed
IDENTIFIED SERIES; nothing is followed until it is tapped. **No new verb**: the foot emits the existing `data-follow`.

## Red today

**R-L22-l — « Suivre » proposed, never done**: an arrival of an identified series changes the follows list by NOTHING;
the offer is on the card and in its panel; a tap changes the list by exactly ONE follow and the offer goes; **no offer on a
film, on a card without identity (nothing to follow yet), or on a series already followed**; **and no card born of an arrival is
drawn in « Suivis », even the episode of a followed series** (OPEN 3, ruled A — « President Curtis », « Star Trek: Strange New
Worlds (2022) »).

**Red against `main`**: an arrival card carries no offer.

## Move

The foot on an arrival card of an identified, unfollowed series; the same action in its panel; the named state
`acq-card-follow-offer`. **A card born of an arrival never appears in « Suivis »** (OPEN 3, ruled A): the tap creates a follow like
any other, and « Suivis » lists follows only.

## Mutation

With the commit made first: follow on arrival → R-L22-l falls; offer it on a film → it falls; draw an arrival card in « Suivis » →
the new hold falls.

## Register

—

## Oracle: states that diverge, declared by name

`acq-now-idle`, `acq-now-loaded` (an arrival series card gains a foot) accepted with « L22 § 3.5: the proposal »; anything
else is STOP A.

## Gate

Per INDEX « Gates »; the follows rules (`acq-follows-*` readers, 37 files mention the states) are re-run by name.

## Commit

`feat(maquette-l22): a series that arrived is offered « Suivre » and never followed unasked`
