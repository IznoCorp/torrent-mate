# Where the frontend work stands

The ORDER and each lot's Done-when live in `docs/reference/frontend-architecture.md` § 4. This file
says only where the work stands, and is rewritten at every squash. The method is
`docs/reference/method.md`; the operator's principles and rulings are
`docs/reference/operator-method.md`; defects are `BUGS.md`. History of every earlier version of this
file: `git log -- IMPLEMENTATION.md` (the last long one is `IMPLEMENTATION.md@638ebcfc`).

| | |
| --- | --- |
| **Last landed** | **L23** — § 19 point 5, the upload to a tracker, PR #665, 2026-10-01; then the register's corrections #668, #669, #670 |
| **In flight** | **The desktop milestone** — `docs/features/maquette-desktop/DESIGN.md`, `feat/maquette-desktop`, the operator's seven rulings of 2026-10-01 (DECIDED 1–7), phases 1–10 drawn: the shell (the menu pinned beside a 760 px reading column, foldable to its icons, remembered per device; the confirmation 480 px), the panel a 440 px side sheet on the right, Acquisition, Médiathèque, Découvrir, Trackers, Système / a run / Maintenance, Réglages / Classement / Comptes / Profil / the gates, the declared keys (`/`, ↑/↓, Enter, Escape) and the hover ground; R413 re-aimed at the three widths and the pinned menu. Rules R480–R488. Version 0.98.129; the lot's reader at 1280 on tm-design before the PR |
| **Then** | the backend mission, after the freeze (`docs/reference/frontend-backend-demands.md`) |
| **Landed, in order** | L01 · L02 · L03 · L04 · L05 · L06 · L07 · L08 · L09 · L10 · L15 · L11 · L12 · L14 · L19 · L21 · L13a · L13b · L20 · L13r · L13c · L22a · L22b · L16 · L16-bis · L17 · L24 · L18 · L23 (plus the correction waves L07-bis, L08-bis, L10-bis and the design phase L10-ter) |
| **Freeze** | reached at L24's close, with every case of every surface drawn as a named state |

## Designs ready, code not started

- none — the desktop milestone is in flight

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
