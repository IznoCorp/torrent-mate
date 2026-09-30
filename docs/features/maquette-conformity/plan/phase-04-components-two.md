# Phase 4 — Components II, in `ui/`: the tones, the notice, the legend, the topic row

## What changes

1. **An `upcoming` tone on `chip` and `statusDot`** (D.1 #7, OPEN 9 = A), from the existing `--color-upcoming`;
   `chip`'s text uses the contrast token family (`--color-*-text`) as its five other tones do.
2. **The notice: `SurfaceError` adapted to three tones** (OPEN 3 = A) — `danger` (today's drawing, the default, the
   ONLY tone carrying `role="alert"`), `warning`, `info`; its fifteen callers keep `danger` untouched.
3. **The legend moves to `ui/`** (D.1 #9, L16-bis S3): `legend` / `legendSwatch` (`features/media/variants.ts:346–369`)
   into a `ui/` module of their own (never `surfaces.ts`, **373 / 400**), imported back by `panel-seasons.tsx`.
   **Said**: L16-bis's plan phase « the legend moves to ui » loses its subject — reported at this gate, L16-bis's
   plan not edited here.
4. **`ui` `TopicRow`** (D.1 #11): title, subtitle, a trailing value, the tap — the inner layout the six hand
   compositions re-type (`rg -n "minWidth: 0, flex: 1" -g '*.tsx' frontend/maquette/design/src` → **5** lines). No
   consumer yet: Système (5) and Réglages & Maintenance (6) convert.

## Acceptance

- The four exist in `ui/`, each with a `variants.test.ts` case; `check-component-once.py` clean.
- The oracle: no divergence (the legend's move draws the same; the tones and the notice have no new caller yet).
- `run.sh --rules follow_seasons.py state_surfaces.py` green.

## Commit

`feat(maquette-conformity): components II — an upcoming tone, the toned notice, the legend and the topic row in ui`
