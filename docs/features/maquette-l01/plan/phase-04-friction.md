# Phase 4 — The five friction counter-measures, each EXERCISED

## Goal

« Exercised rather than asserted » is the architecture file's wording, and it is the bulk of this
lot. A counter-measure that is merely coded is a claim. One that is demonstrated **failing
without it** is a proof.

Every counter-measure therefore ships with an escape hatch — an environment variable that
DISABLES it — so the failure it prevents can be shown on demand, in one command, forever. That is
also what keeps the proof alive: a mutation done by hand once is a proof nobody can re-run.

## Work

| # | Cause | Counter-measure | Escape hatch that proves it |
| - | ----- | --------------- | --------------------------- |
| 1 | animations, async image decode | animations off, `prefers-reduced-motion` forced, images `decode()`d before measuring, and an **explicit settle signal** replacing `open_page`'s 250 ms sleep | `TM_ORACLE_NO_SETTLE=1` → divergence on an unmodified tree (ACC-10) |
| 2 | non-deterministic data | frozen clock, frozen fixtures | `TM_ORACLE_NO_FROZEN_CLOCK=1` → at least one time-dependent state diverges (ACC-11) |
| 3 | slowness | one browser, one context, states driven in-page | wall-clock reported on every run (ACC-14) |
| 4 | unreadable diffs | sorted JSON, report grouped by state | `TM_ORACLE_UNSORTED=1` → a large diff on an unchanged tree (ACC-12) |
| 5 | false positives | allowlist, each entry carrying a **written reason** | an entry with an empty `justification` is refused (ACC-09) |

## The settle signal, in detail — it is the one with real design in it

A delay in milliseconds is a race that passes on a fast machine and fails on a loaded one. The
signal must be a **fact about the document**, not a duration:

- the engine's own load seam (`window.__loadingDone`) is already used by `open_page`;
- every `<img>` inside the frame has resolved `decode()` or failed it;
- no CSS animation or transition is running — read from `document.getAnimations()`, filtered to
  the frame;
- two consecutive `requestAnimationFrame` callbacks observe identical geometry for the regions
  about to be measured.

The last one is the actual guarantee, and it is also what L12 will need when view transitions
land: the oracle reads **at rest**, and this is the mechanism that makes « at rest » a
measurement rather than a hope.

## Done when

- ACC-09 through ACC-12 and ACC-14 all produce their expected output.
- Each escape hatch is documented in `oracle.py`'s docstring, with the failure it demonstrates.
- The wall-clock of a full run over 82 states is recorded in `DESIGN.md`.

## Traps

- **An escape hatch is not a feature.** Each must be inert unless its variable is set, and none
  may weaken the default path. A test asserts the default is on.
- **Freezing the clock can freeze the app into a state it never reaches.** Freeze at a value the
  fixtures were built around, and record which one — a frozen clock at the wrong instant makes
  every date-relative label read « il y a 56 ans », which is deterministic and useless.
- Friction 2 is not hypothetical here: **R63 has already failed because a scheduler fired.**
