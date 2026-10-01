# Where the frontend work stands

The ORDER and each lot's Done-when live in `docs/reference/frontend-architecture.md` § 4. This file
says only where the work stands, and is rewritten at every squash. The method is
`docs/reference/method.md`; the operator's principles and rulings are
`docs/reference/operator-method.md`; defects are `BUGS.md`. History of every earlier version of this
file: `git log -- IMPLEMENTATION.md` (the last long one is `IMPLEMENTATION.md@638ebcfc`).

| | |
| --- | --- |
| **Last landed** | `maquette-season-recovery` — one card per whole-season recovery, « Demandée » on both sheets, a journey per acquisition, PR #659, version 0.98.120, 2026-10-01 (after `maquette-navigation` #656, L16-bis #657, main's harness reds #658, C1 #661) |
| **In flight** | L17 cross-seed — PR #660, version 0.98.121; DOIT-14 reads `partly` until L18 draws the media sheet's block · L24 orphans — PR #662 · L23 upload — building · **L18** — accounts, rights and Plex identity (§ 17), `feat/maquette-l18`, re-grouped by surface into 12 phases, 11 done (the rights model and its 403 guard, the frame, Acquisition by requester, reassign, quality and pause, the library read-only, the forbidden writes, Profil, the Plex-first gate, « Comptes »), rules R420–R428, version 0.98.118; **owed**: phase 11, the media sheet's per-tracker cross-seed block (`readMediaCrossSeed`, gated by `trackers.view`, R-L18-w), which enters L18's correction pass after the reader, on `main` with L17 |
| **Then** | the desktop milestone (to draw) |
| **Landed, in order** | L01 · L02 · L03 · L04 · L05 · L06 · L07 · L08 · L09 · L10 · L15 · L11 · L12 · L14 · L19 · L21 · L13a · L13b · L20 · L13r · L13c · L22a · L22b · L16 · L16-bis (plus the correction waves L07-bis, L08-bis, L10-bis and the design phase L10-ter) |
| **Freeze** | reached at L24's close, with every case of every surface drawn as a named state |

## Designs ready, code not started

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
  demands SR1–SR5; the medium's kind on the library membership read (B-581) and the automatic trigger's
  technical fault told from a person's stop (`watcherDown`); L16-bis's T1 (three more trackers), T2 (a failing
  tracker switched off with its reason, its re-activation refused 422) and T3 (a torrent entry's date, sources,
  volumes, rates, poster and folder); L17's cross-seed demands A, B, D, E, K, the cut, the switch's
  `stopRunningCrossSeeds`, H (active by default at the switchover) and I (the two engine events on the stream,
  plus `CrossSeedSearched`), and the engine attempting every eligible tracker (fact 16); the rest in `docs/reference/frontend-backend-demands.md`.
