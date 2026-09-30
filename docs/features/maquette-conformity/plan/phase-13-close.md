# Phase 13 — The close

## What changes

1. **The three guard arms** of `scripts/check-component-once.py`, now that no consumer is left (L16-bis § 1.9, the
   operator's 17:17 order and order 80 — authorised despite measure 1): `role="tablist"` outside `ui/`; `<details` /
   `summary::before|after` outside `ui/`; `role="switch"` outside `ui/` — hard zero, a floor on the corpus, each arm
   read RED on a planted file then green, with its test.
2. **The tokens that remain** (D.1 #16): `rg -n 'style=\{\{' -g '*.tsx' features app ui | wc -l` counted down
   against its opening **46**; `text-<tone>` → `text-<tone>-text` on text in feature variants.
3. `git merge --no-edit origin/main`; the patch bump above `main`; the RESUME closed.

## The gate of the lot (once)

The full suite (`TM_HARNESS_JOBS=2`); `--a11y`; the full responsive sweep, Chromium × 7 widths + WebKit light and
dark, the owed list reduced to the defects fast lane's entry; `scripts/harness-hold-counts.py --compare
frontend/maquette/hold-counts-baseline.json`; `check-bug-register.py`, `check-intent-map.py`,
`check-docs-cited-paths.py`; the pre-push pytest (`-n 2`). The ten random mutations, the finger walk and the
principles check are the reader round's.

## The pull request

Title `feat(maquette-conformity): one need, one component — and every state at every width`; the §§ served (§ 12,
§ 13, § 15, § 16's tab bars); screenshots of the changed surfaces at 320, 390, 1280 px (seeded data, never
committed); READY, reported the second it exists; auto-merge NOT armed.

## Commit

`chore(maquette-conformity): the close — the guard arms, the last tokens, the version bump`
