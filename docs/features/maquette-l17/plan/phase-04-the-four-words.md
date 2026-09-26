# Phase 4 — The four words, and the reasons' sentences

**Reads OPEN 5 (a pair with nothing found).** OPEN 5 = A (a fifth word): one more word, one more key and one more tone in the map, the rule
reads five words — **+1 point (15)**, still at the ceiling. OPEN 5 = B: four words, as drawn. **OPEN 6 does not change this phase**: the two
words are the operator's either way; what differs is what the backend keeps (phases 1–3).

**Opening measure (2026-09-27, on `46806a88d`):**

- **Commands.** `grep -n '"cross_seed"' frontend/maquette/design/src/i18n/fr.json` → lines 105 and 189, **both Réglages' setting label
  « Partage croisé »**; no `screens.*crossSeed` key exists (`grep -n -i 'crossSeed' frontend/maquette/design/src/i18n/fr.json` → no match).
  `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/i18n/fr.json` → **1 379**. `sed -n 60,80p frontend/maquette/design/src/ui/variants/surfaces.ts` →
  the `chip` variant carries the tones `warning`, `success`, `danger`, `info`, `waiting`, `neutral`; `surfaces.ts` is **375 of 400**, and the four
  words map onto those tones without adding a variant (`actif` → `success`, `stoppé` → `waiting`, `tracker sans cross-seed` → `neutral`, `erreur de
  cross-seed` → `danger`). The vocabulary arm: `for w in cross seed refused stopped engine origin reason sentence feed switch; do grep -c -x $w
  scripts/code-vocabulary.txt; done` → 1 each; `tracker`, `torrent`, `family`, `quota`, `throttle`, `injected`, `rejected`, `roster`, `admin` →
  **0 each** — whether the arm refuses each is read by `python3 scripts/check-no-french.py` at the gate; L16 adds `tracker`, `torrent`, `roster`
  first. `grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` → **`R223`** (this is where the labels bind).
  The unit-test home: `frontend/maquette/design/src/features/media/format.test.ts` (42 lines) and `ui/variants.test.ts` (112).
- **Points ≈ 14.** The state → tone → word map in `features/trackers/cross-seed-state.ts` ≈ 25 lines new 2½; the reason → sentence helper (twelve
  codes, three families) ≈ 20 lines new 2; `fr.json` keys — four words, twelve sentences, three family names, the section's and the line's copy —
  ≈ 30 lines new 3; the vocabulary lines (≈ 8 words) 1; its unit test (≈ 25 lines) 2½; R-L17-a (the enumerations half: every reason code the
  contract declares has a sentence, none rendered bare) 3. **Drawn at 14; cut if it opens over: the unit test moves to phase 5.**
- **Found (2026-09-27).** The first half of R-L17-a needs no surface — it reads the contract's enums against `fr.json` — and is **red today**:
  no sentence exists. Its second half (« every chip a surface draws reads one of the words ») is written here on the map and RE-AIMED at
  phases 5 and 6 when a surface first draws one. **The labels R-L17-a … k bind to numbers in this phase's report.** Réglages' « Partage
  croisé » is left as it stands (DESIGN § 7.1).

## Red today

**R-L17-a — the words, and no bare code** (DESIGN § 5): every reason code the contract's enums declare has a sentence in `fr.json`; the map has
one word per state and the words are the operator's. Red: no sentence, no map.

## Move

1. Bind the labels: re-take the R-number command against `origin/main`, write the mapping (a → R…, …, k → R…) into the report.
2. `features/trackers/cross-seed-state.ts` (the map and the helper), the `fr.json` keys under `screens.trackers` / `screens.tracker`, the
   vocabulary lines the arm asks for, the unit test.
3. The rule, written first and seen red, then green.

## Mutation

With the commit made first: make the helper return the bare code → the rule falls; delete one sentence → it falls; add a fifth word to the map
→ the rule falls (under OPEN 5 = A the set of five is the rule's data and the mutation is a sixth).

## Register

—

## Oracle: states that diverge, declared by name

None — no surface draws a word yet.

## Gate

Per INDEX « Gates »; `python3 scripts/check-no-french.py` (English identifiers, French only in `fr.json`).

## Commit

`feat(maquette-l17): the four states have their words and every refusal its sentence`
