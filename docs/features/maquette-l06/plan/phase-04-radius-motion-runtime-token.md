# Phase 4 — Radius, motion, and the runtime token's home

Two folds and one move. The folds finish the scale — 16 radii to 5 steps, 14 durations and
6 easings to 4 + 2 + 3 loop periods. The move is D-L06-4: `--tm-bottom-bar-h` stays a runtime
value and stops being published by the engine.

## 4.1 — Radius

**Files touched**: `frontend/maquette/design/refonte.html`.

1. The 108 `border-radius` declarations read the five steps of phase 1 § 1.1.
2. **`99px`, `9999px` and `50%` are one intent — a pill — written three ways**, and they all become
   `--radius-full` (999px). The 50 % case is a square element, where a pill and a circle are the
   same thing; if any of the 37 sites is NOT square, the fold changes its shape and the oracle says
   so, which is precisely why this is checked against the divergence list rather than assumed.
3. The two composite values keep their shape and read a step per corner:
   `border-radius: 14px 14px 0 0` → `var(--radius-4) var(--radius-4) 0 0`.
4. `inherit` stays — a keyword, exempt by name in the arm.

**The hold**: `--arm scale` reports `radius 0`; the baseline records it.
**The mutation**: `border-radius: 11px` anywhere in BLOCK 2 — refused, named.

## 4.2 — Motion

**Files touched**: `refonte.html`.

1. The transitions read `--duration-1` … `--duration-4` and one of the two easings. **A
   transition written as a bare duration reads one too**: eight rules named no easing at all, so
   they were running the browser's initial `ease` — a curve nobody chose, and one no arm can name,
   because there is no literal in the file to count. The fold writes `--ease-standard` in, so the
   interface speaks one easing language rather than two.
2. **The three loop periods keep their own tokens** and stay `linear`. A spinner that eases
   stutters; the keyword is exempt by name, and the tokens are named `loop` so a later pass does
   not fold them into the transition ramp.
3. `0s` delays stay `0s`.

**The hold**: `--arm scale` reports `motion 0`.
**The mutation**: `transition: opacity 0.24s ease` — refused for the duration AND for the easing,
in one message naming both.

## 4.3 — `--tm-bottom-bar-h` moves publisher

**Files touched**: `frontend/maquette/design/src/engine/legacy.js` (removal),
`frontend/maquette/design/src/app/bar-height.ts` (new), `frontend/maquette/design/src/app/shell.tsx`
(the call), `frontend/maquette/harness/runtime_tokens.py` (new),
`frontend/maquette/hold-counts-baseline.json`.

**What is NOT changing, and why it is worth a sentence.** The value stays a runtime measurement.
It is the drawn bar's real height including safe areas, so folding it into the scale replaces a
measurement with a hope, and the 8 `var()` uses keep their `, 0px` fallback exactly as they are —
`check-css-tokens.py`'s existing arm holds that, and this phase must leave it green.

1. `publishBarHeight()` leaves `legacy.js` (~11 760–11 780) for
   `design/src/app/bar-height.ts` — an application-level DOM concern, beside `app/focus.ts` which
   is already exactly that. The logic is carried across unchanged: measure `.bottombar`, round up,
   write `--tm-bottom-bar-h` on the document element only when it differs, and observe the bar with
   a `ResizeObserver`.
2. `shell.tsx` calls it. **The engine keeps no copy** — the point of the move is that L13 inherits
   nothing, and a second publisher would make the subtraction unprovable.
3. **`harness/runtime_tokens.py`**, a new rule, holding:
   - `--tm-bottom-bar-h` is set on `:root` after a cold load, and equals the bottom bar's measured
     height;
   - it follows the bar: force the bar to a different height and the value follows;
   - **exactly one publisher exists in the source tree** — a search over
     `frontend/maquette/design/src/` for a write of a `--tm-` property finds one file, and it is
     under `app/`. Not a grep of `legacy.js`: § 6's trap is a rule that greps one file while the
     evidence moves to another.
4. `python3 scripts/harness-hold-counts.py --record frontend/maquette/hold-counts-baseline.json`,
   with the new rule and its count named in the phase report.

**The mutations**, both run and restored:

| Mutation                                               | It must say                                                                                 |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| delete the `publishBarHeight()` call in `shell.tsx`    | `--tm-bottom-bar-h` is never published; everything above the bar is sitting on its fallback |
| re-add the publisher to `legacy.js` beside the shell's | the runtime token has two publishers, and the engine is the one that dies                   |

## 4.4 — The divergences are reviewed, and the reference re-recorded

The index's oracle protocol, once more. **The shapes to distrust in this phase**: a corner that
became a circle on a non-square element (the `50%` fold), and any state whose bottom-anchored
content moved — that is the runtime token, not the radius fold, and it means the publisher move
changed the timing at which the value first lands.

## Gates before each commit in this phase

```bash
cd frontend/maquette/design && npx tsc -b && npm run build \
  && cp dist/index.html /tmp/tm-refonte/wrapped.html \
  && rm -rf /tmp/tm-refonte/vite \
  && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
python3 scripts/check-css-tokens.py            # the runtime-fallback arm included
python3 scripts/check-no-french.py
python3 frontend/maquette/harness/runtime_tokens.py
frontend/maquette/harness/run.sh
```

**`npx tsc -b` is in this phase's gate and not in the others'**: TypeScript moves here.

## Done when

- `--arm scale` reports `radius 0` and `motion 0` — every family but the ones already at zero.
- ACC-06 holds: `0` publishers in `legacy.js`, exactly one file under `src/app/`.
- ACC-07 holds: the 8 `var()` uses keep `, 0px`, and `check-css-tokens.py` is green.
- ACC-08 — `runtime_tokens.py` — is green, and both of its mutations have fallen.
- Every divergence is accepted with a reason and the reference re-recorded.
