# Phase 14 — The live preview

The editor's live preview, through `POST /api/acquisition/ranking/preview` (phase 12's operation): `RankingPreviewResponse.ranked`, sorted, excluded rows flagged and sunk last — and still
visible. With it the promise B-298 names is kept.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['RankingPreviewResponse']['properties']))"` → `known_trackers`,
  `ranked`. The backend's own docstring says a live preview must never silently drop a row (DESIGN § 2.1). `git grep -n rankingWeights -- frontend/maquette/design/src` → the profile key the quality screen
  already reads; `grep -n '^| B-298' BUGS.md` → `open`. The preview panel's analogue is `features/system/run-list.tsx` (176 non-blank lines) for a sorted list of rows with a flag.
- **Points ≈ 9.** The preview panel (≈ 50 new; each row: the release, its total, its `excluded` flag) 5; **one new rule, R-L16-f** with its two mutations 3; `fr.json` (the preview's labels) 1. The
  states `ranking-editor` and its twins are phase 13's — the preview enters `ranking-editor`'s reading, not a new state.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (the preview half of its phase 7) → this phase **9**: moved by **the scale**; no ruling touched it.

A BEHAVIOUR change: the preview did not exist; it calls the operation and draws the answer.

## The proof FIRST

Its label R-L16-f is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From `/settings/ranking`, change a criterion's weight.
- **What it reads.** The criteria POSTed to `ranking/preview` (`window.__mocks.answered()`); the rows drawn compared against `RankingPreviewResponse.ranked`, with the `excluded` flag honoured
  (sunk last, still visible).
- **Red today.** The preview does not exist to read — fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` makes the preview draw a constant ranking regardless of the POSTed criteria — the comparison must fall. A second mutation hides `excluded` rows instead of sinking
  them — the visibility hold must fall too (a live preview must never silently drop a row).

## The move

- **The preview panel** in the editor (`data-part="ranking/preview"`), reading the operation and drawing `ranked`, the excluded rows sunk last and flagged.
- **`i18n/fr.json`** — the preview's labels.

## Mutation

Two mutations, as above, each committed and restored separately.

## Register

**B-298 closes** — both symptoms named in its text resolve to the same screen, with its preview (`python3 scripts/check-bug-register.py` read by OUTPUT, B-346). § 18's ranking clause reads `served` for
the WEIGHTS half; the ratio-aware criterion itself (phase 12's demand row) stays a filed demand until the backend answers it — the design draws the editor so that field slots in without a second wave
once it does (D7).

## Oracle: states that diverge, declared by name

**None expected on other states.** `ranking-editor`'s own recorded reading (phase 13: the criteria alone) grows by the preview — accepted, named, with the reason « L16 phase 14: the editor draws its
live preview ». Any divergence elsewhere is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `ranking-editor`; `python3 scripts/check-bug-register.py` read by OUTPUT.

## Commit

`feat(maquette-l16): the ranking's live preview, and B-298's promise is kept`
