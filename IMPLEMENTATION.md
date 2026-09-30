# Where the frontend work stands

The ORDER and each lot's Done-when live in `docs/reference/frontend-architecture.md` § 4. This file
says only where the work stands, and is rewritten at every squash. The method is
`docs/reference/method.md`; the operator's principles and rulings are
`docs/reference/operator-method.md`; defects are `BUGS.md`. History of every earlier version of this
file: `git log -- IMPLEMENTATION.md` (the last long one is `IMPLEMENTATION.md@638ebcfc`).

| | |
| --- | --- |
| **Last landed** | C1 — the settings save bar and the three-choice leave confirmation, PR #661, 2026-10-01 (before it: L16-bis, PR #657, version 0.98.116) |
| **In flight** | L17 — § 19, cross-seed is seen and decided, `feat/maquette-l17`, 7 phases regrouped by surface from the plan's 18, all done: the contract, seed and mocks; the six words and each tracker's line; the torrent's cross-seed in its panel, refusals read in full, an obligation's origin; the tracker's switch and its confirmation; the cut and the exclusion memory; the badge's failure term and the stream; « Chercher un cross-seed » (panel and the card's left drawer). Version 0.98.117. Its pull request is opened by the orchestrator after the lot's one reader. DOIT-14 reads `partly` until L18 draws the media sheet's block |
| **In flight, too** | L23 — § 19 point 5, the upload to a tracker, `feat/maquette-l23`, built on L17 |
| **Next** | L18 accounts (closing) |
| **Then** | L24 orphans · the desktop milestone. The season recovery (5 phases, re-cut from 13 on 2026-09-30) is built by the next lot that touches Acquisition |
| **Landed, in order** | L01 · L02 · L03 · L04 · L05 · L06 · L07 · L08 · L09 · L10 · L15 · L11 · L12 · L14 · L19 · L21 · L13a · L13b · L20 · L13r · L13c · L22a · L22b · L16 · L16-bis · C1 (plus the correction waves L07-bis, L08-bis, L10-bis and the design phase L10-ter) |
| **Freeze** | reached at L24's close, with every case of every surface drawn as a named state |

## Designs ready, code not started

- Season recovery — `docs/features/maquette-season-recovery/DESIGN.md` (Q14–Q19 ruled; OPEN 8 ruled 2026-09-30)
- L18 — `docs/features/maquette-l18/DESIGN.md` (inherits from L17: the media sheet's cross-seed block, its route `readMediaCrossSeed`, its role gate and the `readAccount` admin fact)
- L23 — `docs/features/maquette-l23/DESIGN.md` · L24 — `docs/features/maquette-l24/DESIGN.md`

## Pages still due — no surface is out of scope

The mission of 2026-08-19 (`CLAUDE.md` § Authority): EVERY screen is redrawn. Of production's eight pages
(`frontend/src/router.tsx`), six have a maquette page and owe depth; **`/control` (« Contrôle ») and
`/pipeline` owe their page** — their panels are partly redistributed into Acquisition and Système, and what
remains, with the standalone addresses, is owned by L24 (`docs/features/maquette-l24/DESIGN.md`).

## Carried to the backend mission

- Plex deletion route; real deletion validated only after the production merge, on a named medium, with a
  `sqlite3 .backup` first.
- Synopsis absent from the read-model (`library.db`); state CODES, not words, for Système; season recovery
  demands SR1–SR4; the medium's kind on the library membership read (B-581) and the automatic trigger's
  technical fault told from a person's stop (`watcherDown`); L16-bis's T1 (three more trackers), T2 (a failing
  tracker switched off with its reason, its re-activation refused 422) and T3 (a torrent entry's date, sources,
  volumes, rates, poster and folder); L17's cross-seed demands A, B, D, E, K, the cut, the switch's
  `stopRunningCrossSeeds`, H (active by default at the switchover) and I (the two engine events on the stream,
  plus `CrossSeedSearched`), and the engine attempting every eligible tracker (fact 16); the rest in `docs/reference/frontend-backend-demands.md`.
