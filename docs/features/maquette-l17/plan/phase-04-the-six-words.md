# Phase 4 — The six words, and the reasons' sentences

**No OPEN question remains conditional.** OPEN 5 = A and round 10 Q5 = A both draw here unconditionally: the map
carries SIX words, not four, and the rule reads six. Round 9 Q10 = A (« Cross-seed » everywhere) is also drawn here,
reversing the first drawing's own choice to leave Réglages alone.

**Opening measure (2026-09-27, on `1d1282567`):**

- **Commands.** `grep -n '"cross_seed"' frontend/maquette/design/src/i18n/fr.json` → lines 105 and 189, **both
  Réglages' setting label « Partage croisé »**; no `screens.*crossSeed` key exists. `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/i18n/fr.json` → **1 379**. `sed -n 60,80p
  frontend/maquette/design/src/ui/variants/surfaces.ts` → the `chip` variant carries the tones `warning`,
  `success`, `danger`, `info`, `waiting`, `neutral`; `surfaces.ts` is **375 of 400**, and the six words map onto
  those tones without adding a variant (`actif` → `success`, `stoppé` → `waiting`, `tracker sans cross-seed` →
  `neutral`, `erreur de cross-seed` → `danger`, `sans correspondance` → `neutral`, `pas encore cherché` →
  `waiting`). The vocabulary arm: `for w in cross seed refused stopped engine origin reason sentence switch match
  searched; do grep -c -x $w scripts/code-vocabulary.txt; done` → 1 each; `tracker`, `torrent`, `family`, `quota`,
  `throttle`, `injected`, `rejected`, `roster`, `admin` → **0 each**, L16 adds `tracker`, `torrent`, `roster` first.
  `grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` → the highest number at this
  writing — re-taken against the highest of `origin/main` and every open branch (F68).
- **Points ≈ 15.** The state → tone → word map in `features/trackers/cross-seed-state.ts` ≈ 30 lines new 3; the
  reason → sentence helper (twelve codes plus the reserved slot, three families, the counted/not-counted split) ≈ 25
  lines new 2½; `fr.json` keys — six words, twelve sentences, three family names, the section's and the button's
  copy (« Chercher un cross-seed »), **and Réglages' « Partage croisé » RENAMED to « Cross-seed »** through
  `scripts/rename-identifiers.py` (round 9 Q10) — ≈ 35 lines new/edited 3½; the vocabulary lines (≈ 10 words) 1; its
  unit test (≈ 25 lines) 2½; R-L17-a (the enumerations half: every reason code the contract declares has a
  sentence, none rendered bare, and the map reads six words) 3. **Drawn at 15, at the ceiling; cut if it opens over:
  the unit test moves to phase 5.**
- **Found (2026-09-27).** The first half of R-L17-a needs no surface — it reads the contract's enums against
  `fr.json` — and is **red today**: no sentence exists. Its second half (« every chip a surface draws reads one of
  the words ») is written here on the map and RE-AIMED at phases 5 and 6 when a surface first draws one. **The
  labels R-L17-a … k bind to numbers in this phase's report.**

## Red today

**R-L17-a — the six words, and no bare code** (DESIGN § 5): every reason code the contract's enums declare has a
sentence in `fr.json`; the map has one word per state, and the words are the operator's, six of them. Red: no
sentence, no map.

## Move

1. Bind the labels: re-take the R-number command against the highest of `origin/main` and every open branch running
   beside this lot, write the mapping (a → R…, …, k → R…) into the report.
2. `features/trackers/cross-seed-state.ts` (the map and the helper), the `fr.json` keys under `screens.trackers` /
   `screens.torrents`, the Réglages rename, the vocabulary lines the arm asks for, the unit test.
3. The rule, written first and seen red, then green.

## Mutation

With the commit made first: make the helper return the bare code → the rule falls; delete one sentence → it falls;
add a seventh word to the map → the rule falls (the set of six is the rule's data and the mutation is a seventh).

## Register

—

## Oracle: states that diverge, declared by name

None — no surface draws a word yet.

## Gate

Per INDEX « Gates »; `python3 scripts/check-no-french.py` (English identifiers, French only in `fr.json`).

## Commit

`feat(maquette-l17): the six states have their words, cross-seed is named everywhere, every refusal its sentence`
