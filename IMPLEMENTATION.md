# Where the frontend work stands

The ORDER and each lot's Done-when live in `docs/reference/frontend-architecture.md` § 4. This file
says only where the work stands, and is rewritten at every squash. The method is
`docs/reference/method.md`; the operator's principles and rulings are
`docs/reference/operator-method.md`; defects are `BUGS.md`. History of every earlier version of this
file: `git log -- IMPLEMENTATION.md` (the last long one is `IMPLEMENTATION.md@638ebcfc`).

| | |
| --- | --- |
| **Last landed** | L16 — § 18, the ratio (the Trackers page), PR #634, version 0.98.106, 2026-09-29. `main` is at version 0.98.113 |
| **In flight** | the conformity train — `feat/maquette-conformity`, pushed head `6152a9740`, NOT merged: 13 phases, 1–12 done, 13 (the close) partly done. Resumed by the new steward after the method reset merges. Owed: the full harness once on the final head, rows B-576/578/580/583/584/585/591 marked fixed, a patch version bump, PR READY. Resume notes: `docs/features/maquette-conformity/RESUME-maquette-conformity.md` on that branch |
| **Next** | `maquette-navigation` (B-577, § 16 by destination, 4 phases) — `docs/features/maquette-navigation/DESIGN.md`; opens once the train merges |
| **Then** | L16-bis (Trackers correction, 5 phases) · C1 settings save bar (micro-wave, beside or before L17) · L17 cross-seed · L18 accounts · L23 upload · L24 orphans · the desktop milestone. The season recovery (5 phases, re-cut from 13 on 2026-09-30) is built by the next lot that touches Acquisition |
| **Landed, in order** | L01 · L02 · L03 · L04 · L05 · L06 · L07 · L08 · L09 · L10 · L15 · L11 · L12 · L14 · L19 · L21 · L13a · L13b · L20 · L13r · L13c · L22a · L22b · L16 (plus the correction waves L07-bis, L08-bis, L10-bis and the design phase L10-ter) |
| **Freeze** | reached at L24's close, with every case of every surface drawn as a named state |

## Designs ready, code not started

- Navigation — `docs/features/maquette-navigation/DESIGN.md`
- L16-bis — `docs/features/maquette-l16bis/DESIGN.md` (all OPEN ruled 2026-09-29 but OPEN 10; code waits for the train)
- Season recovery — `docs/features/maquette-season-recovery/DESIGN.md` (Q14–Q19 ruled; OPEN 8 left)
- L17 — `docs/features/maquette-l17/DESIGN.md` · L18 — `docs/features/maquette-l18/DESIGN.md`
- L23 — `docs/features/maquette-l23/DESIGN.md` · L24 — `docs/features/maquette-l24/DESIGN.md`

## Pages still due — no surface is out of scope

The mission of 2026-08-19 (`CLAUDE.md` § Authority): EVERY screen is redrawn. Of production's eight pages
(`frontend/src/router.tsx`), six have a maquette page and owe depth; **`/control` (« Contrôle ») and
`/pipeline` owe their page** — their panels are partly redistributed into Acquisition and Système, and what
remains, with the standalone addresses, is owned by L24 (`docs/features/maquette-l24/DESIGN.md`).

## Open questions for the operator (one round, 8)

1–3. The conformity train's phase 5 vocabulary: « joignable » as the one word of the reachable code; the pause
   reading « actif » when engaged; the stopped processing drawn in danger.
4. L16-bis OPEN 10 — what « passer » does on the data side (recommended A).
5. Season recovery OPEN 8 — where the card carries the « auto » word (drawn: in its subtitle, « S03 · auto »).
6. Navigation OPEN 1 — coming back to a page already on the trail (recommended A: stack again).
7. Navigation OPEN 2 — a screen that takes another's place, S2/S3 (recommended A: they stack).
8. Navigation OPEN 3 — leaving Réglages/Maintenance by the menu with a rubric open (recommended B).

## Carried to the backend mission

- Plex deletion route; real deletion validated only after the production merge, on a named medium, with a
  `sqlite3 .backup` first.
- Synopsis absent from the read-model (`library.db`); state CODES, not words, for Système; season recovery
  demands SR1–SR4; the rest in `docs/reference/frontend-backend-demands.md`.
