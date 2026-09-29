# Phase 18 — One notice with a tone, adapted from `SurfaceError` (the operator's OPEN 3 = A)

**Ruled 2026-09-29** (`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` § Q3, verbatim « A »): ONE
notice component, ADAPTED from `SurfaceError` (never a new one), three tones — danger (today's error surface, the
ONLY tone with `role="alert"`), warning, info; « TMDB déconnecté », « à identifier », read-only and restart-required
move into it. It leaves the report's § D.2. **Not a pure conversion**: the visible changes are accepted BY NAME.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "surfaceError\(\)|loadError\(" -g '*.tsx' frontend/maquette/design/src` → the bare class
  repainted by inline style at `features/acquisition/discover-tab.tsx:163` (warning) and
  `features/acquisition/add-screen.tsx:215` (info), both keeping `role="alert"`; `loadError` as a banner at
  `features/settings/banners.tsx:49, 61, 70` (read-only, changed on disk, restart) — and `loadError` as a real
  « voir plus » failure at `features/library/library-list.tsx:216`, `features/settings/ranking-screen.tsx:157`, which
  stay errors; `SurfaceError` at `ui/state-surfaces.tsx:115`, fifteen callers, unchanged (tone danger by default).
- **Points ≈ 12.** `SurfaceError` gains a `tone` and a variant set, `role="alert"` on danger only (≈ 15 lines, 3);
  the two inline-styled notices onto it, their inline `style` gone (≈ 14 lines, 3); the three banners (≈ 10 lines,
  2); R-conformity-i (3); the RESUME (1).
- **Readers.** Every rule reading `surface-error` or `load-error` (`state_surfaces.py`, `discover_page.py`,
  `settings.py`, `settings_editing.py` and others) — re-read at the opening; a notice keeps a part of its own, said.

## Red today

R-conformity-i on `discover-degraded`, `acq-identify` and the settings banner states: a notice that is not an error
carries no `role="alert"` and is the `ui` notice in its tone; an error keeps both — falls.

## Mutation

Put `role="alert"` back on the warning tone → falls by name.

## Oracle: states that diverge, declared by name

`discover-degraded`, `acq-identify`, the settings banner states (built by script) — accepted by name.

## Commit

`feat(maquette-conformity): one notice, three tones — an alert only when it is one`
