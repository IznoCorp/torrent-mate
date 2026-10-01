# Where the frontend work stands

The ORDER and each lot's Done-when live in `docs/reference/frontend-architecture.md` § 4. This file
says only where the work stands, and is rewritten at every squash. The method is
`docs/reference/method.md`; the operator's principles and rulings are
`docs/reference/operator-method.md`; defects are `BUGS.md`. History of every earlier version of this
file: `git log -- IMPLEMENTATION.md` (the last long one is `IMPLEMENTATION.md@638ebcfc`).

| | |
| --- | --- |
| **Last landed** | **L18** — accounts, rights and Plex identity (§ 17), PR #663, version 0.98.123, rules R420–R430, 2026-10-01: the rights model and its 403 guard, the frame, Acquisition by requester, reassign, quality and pause, the library read-only, the forbidden writes, Profil, the Plex-first gate, « Comptes », the media sheet's per-tracker cross-seed block (after L24 #662, L17 #660, `maquette-season-recovery` #659, C1 #661) |
| **In flight** | **L23** — § 19 point 5, the upload to a tracker, `feat/maquette-l23`, merged with L18: the contract, seed and mock (`uploadCrossSeed`, `creation_failed` / `publish_failed`, a pair's `via` and the tracker's reason, a tracker's « accepte les uploads », an entry's provenance); « Créer et publier un torrent » offered where nothing cross-seeds, confirmed, « en file », read on its row, counted by the badge; the tracker panel's « accepte les uploads » switch; the third origin mark « Publié par vous »; the gesture held by its right `trackers.upload` (DESIGN § 0.2, R-L23-f). Rules R450–R457. Version 0.98.125 |
| **Then** | the desktop milestone (to draw) |
| **Landed, in order** | L01 · L02 · L03 · L04 · L05 · L06 · L07 · L08 · L09 · L10 · L15 · L11 · L12 · L14 · L19 · L21 · L13a · L13b · L20 · L13r · L13c · L22a · L22b · L16 · L16-bis · L17 · L24 · L18 (plus the correction waves L07-bis, L08-bis, L10-bis and the design phase L10-ter) |
| **Freeze** | reached at L24's close, with every case of every surface drawn as a named state |

## Designs ready, code not started

- L23 — `docs/features/maquette-l23/DESIGN.md` · L24 — `docs/features/maquette-l24/DESIGN.md`

## Pages still due — no surface is out of scope

The mission of 2026-08-19 (`CLAUDE.md` § Authority): EVERY screen is redrawn. Of production's eight pages
(`frontend/src/router.tsx`), six have a maquette page and owe depth. **`/control` (« Contrôle ») and
`/pipeline` are settled by L24, with no page of their own** (`docs/features/maquette-l24/DESIGN.md`): « Santé »
is Système's, each section saying its own read failed and a filling disk counted on the menu's badge; the
scraping activity reads on each card; a settled decision reads on its medium's journey and Médiathèque sheets,
« Corriger » sending it back to arbitration; every former production address answers not-found (no
backward compatibility, OPEN 9).

## Carried to the backend mission

- Plex deletion route; real deletion validated only after the production merge, on a named medium, with a
  `sqlite3 .backup` first.
- Synopsis absent from the read-model (`library.db`); state CODES, not words, for Système; season recovery
  demands SR1–SR5; the medium's kind on the library membership read (B-581) and the automatic trigger's
  technical fault told from a person's stop (`watcherDown`); L16-bis's T1 (three more trackers), T2 (a failing
  tracker switched off with its reason, its re-activation refused 422) and T3 (a torrent entry's date, sources,
  volumes, rates, poster and folder); L17's cross-seed demands A, B, D, E, K, the cut, the switch's
  `stopRunningCrossSeeds`, H (active by default at the switchover) and I (the two engine events on the stream,
  plus `CrossSeedSearched`), and the engine attempting every eligible tracker (fact 16); L24's demands — a
  settled decision's id, candidates' count and author (an identification the engine made alone written as a
  decision row), `reopenDecision` (re-open a settled decision, a shelved medium's included), the follow
  completeness read in the contract's names; the rest in `docs/reference/frontend-backend-demands.md`.
