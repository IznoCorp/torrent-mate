# Phase 24 — One status dot, with an « upcoming » tone (D.1 #7, the operator's OPEN 9 = A)

**Ruled 2026-09-29** (`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` § Q9, « A »): an
« upcoming » tone is added to `statusDot` and `chip` (the existing `--color-upcoming`); the places drawing it apart
(`panel-seasons`, `season-list`, `media/variants`) are rewired to it; the veille's running dot becomes `liveDot`
inside `liveStrip`, as the report says. The veille's dot becoming visible is the one visible change, accepted BY NAME.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "episodeDot|upcoming" -g '*.ts' frontend/maquette/design/src/features/media/variants.ts` →
  `episodeDot` **:283** (its own six-state map), `text-upcoming` / `bg-upcoming` at **:287, 303, 335**, `upcomingMark`
  **:213**; `rg -n 'live-dot' -g '*.tsx' frontend/maquette/design/src` → an unstyled `<span>` at
  `features/system/watch.tsx:81` (invisible); `ui/variants/surfaces.ts` **373 / 400** (the tone adds two lines).
- **Points ≈ 11.** The `upcoming` tone on `statusDot` and `chip` (2); `episodeDot` → `statusDot` at its sites (≈ 12
  lines, 3); the veille's dot → `liveStrip` + `liveDot` (1); R-conformity-r, a VISIBLE dot on `watch-running`
  (non-zero box, painted) and every season dot the `ui` part (3); mutation (1); the RESUME (1).
- **Readers.** `season_family.py`, `follow_seasons.py`, `watch_run.py` — the parts are kept.

## Red today

R-conformity-r on `watch-running` (the dot has no box) and `followsheet-gaps` (the episode dots are not `statusDot`)
— falls.

## Mutation

Remove the class from the veille's dot → falls by name.

## Oracle: states that diverge, declared by name

`watch-running`, and every media and follow sheet state with episode dots (built by script).

## Commit

`refactor(maquette-conformity): one status dot, an upcoming tone, and the veille's dot drawn`
