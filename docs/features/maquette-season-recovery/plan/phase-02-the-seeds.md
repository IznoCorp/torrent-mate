# Phase 2 — The seeds

**No STOP C.**

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.**
  `python3 -c "import json;s='frontend/maquette/design/src/mocks/seeds/';print(json.load(open(s+'seasons.json'))['Silo'][2]);print(len(json.load(open(s+'in-flight.json'))));print([r['name'] for r in json.load(open(s+'releases.json')) if r['name'].startswith('Silo')])"`
  → `{'season': 3, 'aired': 7, 'owned': 6}`; **3** in-flight cards, none of Silo; **4** Silo releases, all `S03E07`.
  `grep -n '"title": "Silo"' frontend/maquette/design/src/mocks/seeds/follows.json` → line **145**, `status`
  `pending`.
- **Points ≈ 7.** The season card « Silo » · `S03` (requester `follow`, strip at « téléchargement ») 2; the episode
  card « Silo » · `S03E07 · 1080p · MULTi` (strip at « téléchargement », `season` 3, `episode` 7, `absorbedBy` the
  season card) 2; the season pack `Silo.S03.MULTi.1080p.WEB-DL.DDP5.1.H264-FRATERNITY` in `releases.json` 1; the
  three rows declared in `frontend/maquette/fixture-register.json` 1; `python3 scripts/check-mock-seeds.py` by
  OUTPUT, the report 1.
- **Readers.** `harness/now_holds_in_flight.py` (R224) holds that « En cours » counts what « En vol » draws and that
  no two cards name one medium — both stay true: « S03 » and « S03E07 » are two media until phase 5 absorbs one.
  Nothing hard-codes the dense list's length (`grep -n "== 3\|len(.*) == " frontend/maquette/harness/now_holds_in_flight.py`
  read at the opening).

## Red today

None — seeds have no rule; `check-mock-seeds.py` is the guard.

## Move

1. Add the two cards to `in-flight.json` (the DENSE list; the reel list stays empty — the real world's rule) and the
   pack to `releases.json`, from the shapes already there.
2. A value the engine does not give stays `null` — never a plausible one (§ 13).

## Mutation

None.

## Register

The fixture register: the three rows « composé — récupération de saison, dessin DESIGN § 2 », their date.

## Oracle: states that diverge, declared by name

Every state drawing the DENSE « En cours » list or Silo's sheet, declared by script (`scen: "loaded"` with
`acqTab: "now"`, and every media state on « Silo »). Until phase 5 the episode card is DRAWN beside the season's —
expected, and said in the report.

## Commit

`feat(maquette-season-recovery): the seeds of a season under recovery and of the episode it covers`
