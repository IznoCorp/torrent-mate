# Phase 4 — Motion, and the guard that reads class names

D-L07-3, arbitrated by the operator on 2026-08-24.

## What lands

The four touch-response steps become bare milliseconds at their **22 call sites**, all of which
are `transition:` shorthands:

| token | value | utility |
| --- | --- | --- |
| `--duration-1` | 0.15s | `duration-150` (3 sites) |
| `--duration-2` | 0.2s | `duration-200` (12 sites) |
| `--duration-3` | 0.3s | `duration-300` (5 sites) |
| `--duration-4` | 0.45s | `duration-450` (2 sites, one of them an `animation:`) |

**The three loop periods stay declared and are not touched.** Their 4 call sites are `animation:`
shorthands, which phase 2 moved into `--animate-*` entries carrying the whole shorthand — they
never become `duration-*` utilities at all.

<sub>`grep -nE '^\s*[a-z-]+\s*:[^;]*var\(--duration-' frontend/maquette/design/refonte.html`</sub>

## Why the guard is not optional

`check-css-tokens.py --arm scale` reads CSS *declarations*. A value living inside a class name is
invisible to it, and `duration-137` compiles without complaint — so the family L06 put on a scale
would come straight back off it, silently, with the existing guard green.

**And nothing else would catch it either**: `transition-duration` is not among the oracle's 19
measured properties. This is the one place in the wave where a wrong value produces no signal from
any existing instrument.

`--arm motion-classes` reads the class names of `design/src/**` and `index.html` and refuses any
`duration-<n>` outside {150, 200, 300, 450}.

## Mutation test

Write `duration-137` in a component → the arm exits 1 and names the file and the value. Restore,
green. Then write `duration-2` — the shape that started this — and confirm the arm refuses it too:
it is a legal Tailwind utility meaning 2 ms, which is exactly the defect.

## Gates

ACC-01, ACC-02, ACC-03, ACC-10, ACC-13.
