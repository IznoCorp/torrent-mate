# Phase 4 — The six words, and the reasons' sentences

**Ruled.** OPEN 5 = A and round 10 Q5 = A: the map carries SIX words, and the rule reads six. Round 9 Q10 = A:
« Cross-seed » everywhere, Réglages included.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.** `grep -n '"cross_seed"' frontend/maquette/design/src/i18n/fr.json` → lines 105 and 189, **both
  Réglages' setting label « Partage croisé »**; no `screens.*crossSeed` key. `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/i18n/fr.json` → **1 379**. `sed -n 60,80p
  frontend/maquette/design/src/ui/variants/surfaces.ts` → the `chip` tones `warning`, `success`, `danger`, `info`,
  `waiting`, `neutral`; `surfaces.ts` is **375 of 400**, and the six words map onto those tones without a new
  variant. The vocabulary arm: `for w in cross seed refused stopped engine origin reason sentence switch match
  searched; do grep -c -x $w scripts/code-vocabulary.txt; done` → 1 each; `tracker`, `torrent`, `family`, `quota`,
  `throttle`, `injected`, `rejected`, `roster`, `admin` → **0 each**, L16 adds `tracker`, `torrent`, `roster` first.
- **Points ≈ 15.** The map in `features/trackers/cross-seed-state.ts` ≈ 30 lines 3; the reason → sentence helper ≈
  25 lines 2½; `fr.json` keys ≈ 35 lines 3½; the vocabulary lines 1; the unit test ≈ 25 lines 2½; R-L17-a (its
  enumerations half) 3. **At the ceiling; cut if it opens over: the unit test moves to phase 5.**

## The contract, as phases 5–15 consume it

- **The map** (state → tone → word): `actif` → `success`, `stoppé` → `waiting`, `tracker sans cross-seed` →
  `neutral`, `erreur de cross-seed` → `danger`, `sans correspondance` → `neutral`, `pas encore cherché` → `waiting`.
- **The helper**: reason → sentence, twelve codes plus the reserved slot, three families, the counted/not-counted
  split.
- **`fr.json`** under `screens.trackers` / `screens.torrents`: six words, twelve sentences, three family names, the
  section's and the button's copy (« Chercher un cross-seed »), and Réglages' « Partage croisé » RENAMED « Cross-seed »
  through `scripts/rename-identifiers.py`.
- **R-L17-a's second half** (« every chip a surface draws reads one of the words ») is written here on the map and
  RE-AIMED at phases 5 and 6 when a surface first draws one.

## Red today

**R-L17-a — the six words, and no bare code** (DESIGN § 5): every reason code the contract's enums declare has a
sentence in `fr.json`; the map has one word per state, the operator's, six of them. Red: no sentence, no map.

## Move

1. Bind the labels — the rule numbers are the range the steward reserves in this lot's launch brief — and write the mapping (a → R…, …, k → R…)
   into the report.
2. `features/trackers/cross-seed-state.ts` (the map and the helper), the `fr.json` keys, the Réglages rename, the
   vocabulary lines the arm asks for, the unit test.
3. The rule, written first and seen red, then green.

## Mutation

Commit first: the helper returns the bare code → the rule falls; delete one sentence → it falls; add a seventh word
to the map → it falls (the set of six is the rule's data). **Register**: —. **Oracle**: none — no surface draws a
word yet.

## Gate — done when

Per INDEX « Gates »; `python3 scripts/check-no-french.py` (English identifiers, French only in `fr.json`).

## Commit

`feat(maquette-l17): the six states have their words, cross-seed is named everywhere, every refusal its sentence`
