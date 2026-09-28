# Phase 16 — « Ce n'est pas un média »

**Amended 2026-09-28 (L22b phase 43, F53):** the game folder was « autre » for the sort, never an acquisition card; it left `stuck.json`, and this phase's rule and state now read « Backrooms.2026.MULTi.2160p.WEB-DL » in the dense world.

**Opening measure (2026-09-26, on `94a369879`):**

- **Commands.** The exits of the candidates screen today (`resolution-screen.tsx`, after phase 2 in Acquisition): pick,
  manual search (`data-manual`), « Laisser tel quel » (`data-leave`) — `git grep -c 'sheetActions\|data-leave\|data-manual' -- frontend/maquette/design/src/features/acquisition/resolution-screen.tsx`
  at the opening. The real case: `python3 -c "import json;print([c['title'] for c in json.load(open('frontend/maquette/design/src/mocks/seeds/stuck.json'))])"`
  → `['Top Chef Le Concours Parallèle (2026)', 'Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto']` — the second's reason is
  « Aucun fichier vidéo dans le dossier : c'est un jeu, pas un média » and its `ids` are `null`. The destinations: the five
  non-media staging directories of `config.example/patterns.json5` (phase 1 seeds the read). The verb registry
  (`lib/verbs.ts`) holds one handler per `data-*` name; the resolve verb's undo window is `lib/held-actions.ts`'s
  (`UNDO_WINDOW_MILLISECONDS`).
- **Points ≈ 13.** A new exit in the screen (a button and the choice sheet, ≈ 40 lines written) 4; the verb (≈ 20 lines
  written) 2; the choice's words as `fr.json` keys (≈ 6) 1; the reclassify held action with its undo window 2; R-L22-j with
  its mutation 3; one state (`acq-resolution-not-media`, composed on the seed's game folder — no new seed row) 1.

- **Re-measured 2026-09-27 at its opening, on `79c4309a7`:** ≈ 14. `reclassifyStagedMedia` AND its inverse `restoreReclassifiedMedia` are declared and mocked, and no client read the destinations; the « Annuler » calls the inverse, as DESIGN § 3.4 says (« demand C carries its inverse »), rather than the held send this file's Move describes; the choice is a panel kind `not-media`, the return one settlement (`panel.close(true)` + `bridge.rewind`, the identification's own); rule label j = R228 (R227 is 15b's).

Ruling 5: the candidates screen offers « Ce n'est pas un média ». The folder is reclassified « other » and filed where the
sort files that category; **its card leaves the acquisitions and he does not see it again**. The choice among the
destinations is configuration, never hard-coded (DESIGN § 3.4).

## Red today

**R-L22-j — « Ce n'est pas un média »**, walked on the game folder: the choice offers the sort's non-media destinations; the
reclassification is ANSWERED on the network (`window.__mocks.answered()`); the card leaves the acquisitions and is in
NEITHER « À traiter » nor « En cours »; the « Annuler » window brings it back; the landing is « À traiter » (R-L22-d's
family).

**Red against `main`**: the exit does not exist.

## Move

The exit and its choice sheet (a transient layer: no URL, Back closes it — D1's transient tier); the verb calls
`reclassifyStagedMedia` through the layer's held-action machinery (the same shape as a pick: the folder leaves at once,
the send waits out the undo window — B-393's inverse, asked of every resolve by `backend-demands-architecture.md` § 9).

## Mutation

With the commit made first: make the verb toast without calling → the network hold falls.

## Register

—

## Oracle: states that diverge, declared by name

Only the state this phase adds; `acq-resolution-none` and `acq-resolution-tie` gain an exit button and diverge on
`screen-resolution/body` (a new element under the manual search), accepted with « L22 § 3.4: a new exit ». Any other
divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` over the new state.

## Commit

`feat(maquette-l22): the candidates screen can reclassify a folder that is not a medium`
