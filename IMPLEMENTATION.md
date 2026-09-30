# Where the frontend work stands

The ORDER and each lot's Done-when live in `docs/reference/frontend-architecture.md` § 4. This file
says only where the work stands, and is rewritten at every squash. The method is
`docs/reference/method.md`; the operator's principles and rulings are
`docs/reference/operator-method.md`; defects are `BUGS.md`. History of every earlier version of this
file: `git log -- IMPLEMENTATION.md` (the last long one is `IMPLEMENTATION.md@638ebcfc`).

| | |
| --- | --- |
| **Last landed** | the conformity train — one need, one component, every state at every width, PR #655, version 0.98.114, 2026-09-30 |
| **In flight** | L16-bis — the Trackers page's correction and Découvrir, `feat/maquette-l16bis`, 5 phases, all done (the torrent card, the « Torrents » tab, the « Trackers » tab, Découvrir's header and swipe, the close), version 0.98.115; its pull request is opened by the orchestrator after the lot's one reader at 390 px on tm-design, and a follow-up commit writes its number here and on the register rows B-595–B-597 |
| **Next** | `maquette-navigation` (B-577, § 16 by destination, 4 phases) — `docs/features/maquette-navigation/DESIGN.md`, in flight beside L16-bis |
| **Then** | C1 settings save bar (micro-wave, beside or before L17) · L17 cross-seed · L18 accounts · L23 upload · L24 orphans · the desktop milestone. The season recovery (5 phases, re-cut from 13 on 2026-09-30) is built by the next lot that touches Acquisition |
| **Landed, in order** | L01 · L02 · L03 · L04 · L05 · L06 · L07 · L08 · L09 · L10 · L15 · L11 · L12 · L14 · L19 · L21 · L13a · L13b · L20 · L13r · L13c · L22a · L22b · L16 (plus the correction waves L07-bis, L08-bis, L10-bis and the design phase L10-ter) |
| **Freeze** | reached at L24's close, with every case of every surface drawn as a named state |

## Designs ready, code not started

- Navigation — `docs/features/maquette-navigation/DESIGN.md` (OPEN 1–3 ruled 2026-09-30; OPEN 1 by his own reading)
- Season recovery — `docs/features/maquette-season-recovery/DESIGN.md` (Q14–Q19 ruled; OPEN 8 ruled 2026-09-30)
- L17 — `docs/features/maquette-l17/DESIGN.md` · L18 — `docs/features/maquette-l18/DESIGN.md`
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
  volumes, rates, poster and folder); the rest in `docs/reference/frontend-backend-demands.md`.
