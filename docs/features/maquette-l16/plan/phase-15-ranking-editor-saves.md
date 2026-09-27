# Phase 15 — The ranking editor saves (F16)

The editor's SAVE, corrected against F16: the prior reading never wrote a change back anywhere. This
phase calls `updateConfigurationFile` on `ranking.json5` — the SAME write mechanism the tracker policy
(phase 4) and Réglages already use — carrying its own `SHA-256` precondition, with the hold that a
save answers before the operator can believe it landed, and that the NEXT read reflects it.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(d['paths']['/api/config/files/{name}']['put'])"`
  → `updateConfigurationFile`, the SAME operation `mocks/handlers/configuration.ts:71` already mocks;
  `grep -n 'restartRequired\|conflict' frontend/maquette/design/src/features/settings/queries.ts` →
  the operation answers `{restartRequired, conflict}` on `200`, and production's own `RankingPanel.tsx`
  reads a `412` conflict from `ApiError` — the settings feature's OWN conflict copy this phase reuses,
  never a second one invented for the ranking screen alone. `grep -n '^| B-298' BUGS.md` → `open`.
- **Points ≈ 10.** The save call, wired to the editor's own « Enregistrer » control (≈ 15 new,
  reusing the settings feature's existing write helper) 1½; the rubric's own path and the quality
  screen's toast are phase 14's, untouched here (≈ 0); **R-L16-f re-aimed** — its save half, a new
  hold (« a save calls the operation, and the NEXT read answers the saved weights ») with its
  mutation, priced as a new rule fragment given the genuinely new behaviour it proves 3; two states
  — `ranking-editor-saving` (re-using phase 14's seed) 1, `ranking-editor-save-conflict` (needing a new
  seed row — a `412` scenario) 2; `fr.json` (the save's own confirmation and the conflict copy, reusing
  the settings feature's existing wording where it already fits) 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** No row of the prior re-reads: this phase is entirely new,
  born of F16 alone. It did not exist because the prior reading never noticed the save was missing —
  splitting the read (13) from the save (14) is the cost of correcting a gap that the prior reading's
  own single « editor » phase would have hidden inside a screen that only LOOKED complete.

A BEHAVIOUR change: no save exists anywhere in this domain; this phase is the first to call one from
the ranking editor.

## The proof FIRST

R-L16-f re-aimed (its label was bound in phase 14).

- **What it drives.** From `/settings/ranking`, change a criterion's weight, save; reload the screen.
- **What it reads.** The save calling `updateConfigurationFile` (`window.__mocks.answered()`); the
  RELOAD answering the SAVED weights, never the pre-save ones — the read (13) and the write (this
  phase) agreeing, exactly as phase 4's tracker policy already proves for its own three fields.
- **Red today.** No save exists — the network hold fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` makes the save button message success without calling the
  operation. The hold must fall, naming the operation. A second mutation answers the save but leaves
  the NEXT read's mock seed unchanged — the reload hold must fall too, naming the disagreement.

## The move

- **The save**, wired to the editor's « Enregistrer » control: `updateConfigurationFile` on
  `ranking.json5`, carrying the file's `SHA-256` precondition already declared (phase 14's read
  answers it).
- **The conflict read**: a `409` / `412` answer re-reads the file and reports, through the settings
  feature's own EXISTING conflict copy — never invented twice.
- **`harness/states/settings.ts`** — `ranking-editor-saving`, `ranking-editor-save-conflict`.
- **`i18n/fr.json`** — the save's own confirmation copy, reusing the settings feature's conflict
  wording where it already fits.

## Mutation

Two, as above — each committed and restored separately.

## Register

B-298 does not close here: the promise it names is « the editor WITH its preview », and the preview
is phase 16's. This phase closes the SAVE half F16 found missing — § 18's ranking clause reads
`served` for the read-and-save half, reported precisely by phase 17; the ratio-aware criterion itself
(phase 13's demand row) stays a filed demand until the backend answers it.

## Oracle: states that diverge, declared by name

**None expected on other states.** `ranking-editor-saving` and `ranking-editor-save-conflict` are NEW,
entered from `ranking-editor`'s own recorded reading (phase 14) — accepted, named, with the reason
« L16 phase 15: the editor's save enters its own transient states ». Any divergence elsewhere is
**STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for both new states; `python3
scripts/check-bug-register.py` read by OUTPUT.

## Commit

`feat(maquette-l16): the ranking editor saves its weights`
