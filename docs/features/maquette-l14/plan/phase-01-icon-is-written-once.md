# Phase 1 — `Icon` is written once · **conversion**

**Owns**: D-L14-1, D-L14-2. **Constitution**: §15.

## What changes

1. `features/media/media-screen.tsx`, `features/arrivals/resolution-screen.tsx` and
   `features/releases/releases-screen.tsx` lose their private `function Icon` and import
   `{ Icon } from "../../ui/icon"`. Nothing else in those files moves in this phase — the two
   grandfathered files shrink by 14 lines each and keep their entries (still over 400).
2. `ui/panel/index.tsx`'s private `ActionButton` becomes `PanelActionButton`, through
   `scripts/rename-identifiers.py` (never by hand). The diff is re-read after the tool reports.
3. **`scripts/check-component-once.py`** — a guard of its own, NOT an arm of
   `check-frontend-boundaries.py` as the design first wrote: that file stands at **952** non-blank
   lines against `check-module-size.py`'s hard ceiling of 1 000, and L07-bis split guards on a
   SUBJECT rather than on a line count. The subject here is one sentence, « a component is written
   once ». Every `.ts`/`.tsx` under `design/src` outside `engine/` and `mocks/` is read for
   top-level `function <PascalCase>(` declarations (exported or not); a name declared in more than
   one file is a violation. Hard zero, no allow-list. The guard prints how many declarations it
   read over how many files and holds a floor on both (a reader that read nothing reports « no
   duplicate »). Wired into `run.sh`'s `REPOSITORY_GUARDS` and `make check`; the CI `maquette`
   filter's `scripts/check-*.py` glob names it.

## Definition of done

- `grep -rn -E '^(export )?function Icon\b' --include='*.tsx' frontend/maquette/design/src` → **one**
  line, `ui/icon.tsx`.
- `python3 scripts/check-component-once.py` → clean, printing its corpus figures.
- **Mutation by hand** (a guard, B-273): re-add a `function Icon` to `releases-screen.tsx`, run
  the arm, read exit **1** naming `Icon` and both files; restore with `git checkout --`.
- The oracle: zero divergence. `run.sh --contracts`: green. `npm run check`: green.
- One commit: `refactor(maquette-l14): Icon is written once — three copies deleted, the twice arm`.
