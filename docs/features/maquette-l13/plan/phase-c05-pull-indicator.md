# Phase c·5 — The pull indicator

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands.** `git grep -n '1100\|1_100' -- '*.ts'` → `design/src/app/pull-indicator.ts:18`
  (`const REFRESH_MILLISECONDS = 1100`), NOT `lib/pull-gesture.ts` as the phase text names it —
  `pull-indicator.ts`'s own header comment splits the two files itself ("the GESTURE is
  `lib/pull-gesture.ts`'s… What is here is the other half"). `git grep -n installPullIndicator` →
  wired ONCE at boot in `app/shell.tsx:250` (`installPullIndicator(port, document.getElementById("ptr"))`),
  both `#port` and `#ptr` declared once in the static `design/index.html` shell — the indicator is a
  single frame-level singleton over the app's one scrollport, not a per-page or Settings-specific
  binding. `grep -ln 'ptr\b' harness/*.py` → 8 files; `harness/press.py` alone carries ≥7 existing
  holds driving a REAL pull and reading `#ptr`'s `getBoundingClientRect().height` timing
  (`drive_pull`, `hold_the_pull_threshold`, `hold_a_cancelled_mouse_pull_is_released`); `harness/
  touch.py`'s R55 drives the pull on seven surfaces. Neither file is named in the phase. No named
  state opens the pull at rest. `grep -n B-331 BUGS.md` → `open`, 1×.
- **Points ≈ 9.** Sites (the indicator's own file, a new "current refetch" door the settings surface
  fills, the settings binding) ≈ 8 site-lines → 2; the new rule with its two mutations (fixed timeout
  restored, centring removed) ≈ 3; `harness/press.py` and `harness/touch.py`'s R55, both real readers
  of `#ptr`'s timing that the switch from a fixed delay to a refetch-settlement close can move, are
  counted as 2 found re-aims worth watching, not yet confirmed broken ≈ 2 (provisional pending the
  refetch mechanism's actual shape).
- **Found (2026-09-15).** The move's file citation is wrong: the fixed timer and the centring both
  live in `app/pull-indicator.ts` (the frame's own affordance), not `lib/pull-gesture.ts` (the
  gesture's vocabulary only — axis, damping, arming distance). The indicator is wired globally at
  boot on the app's single `#port`/`#ptr`, not per-surface, so "the settings surface's binding" names
  a wiring that does not exist yet — REFERENCING it as if hooked up already understates the work: a
  door letting the CURRENT page hand over its own refetch promise has to be built, not merely wired.
  `harness/press.py` (≥7 holds) and `harness/touch.py` (R55) already drive real pulls against `#ptr`
  and are not named among the phase's readers, though neither is proven broken without running them
  (forbidden in this session).
- **Landed (2026-09-16).** The sampling reads the spinner CENTRED at rest, armed, loading and closing
  on this machine (offset 0): the centring half is unreproduced here and stays the operator's device
  reading, its mechanism proved by the mutation that removes `place-items-center` (x = 0, the
  screenshot). The move is the closing: `refetchQueries({ type: "active" })` in `app/pull-indicator.ts`
  (not `lib/pull-gesture.ts`), no per-surface door needed. R199, 5 holds; `press.py` and R55 re-aimed
  with a scenario answer time, set AFTER the driven state (the driver's reset puts the scenario back).

A BEHAVIOUR change: « Réglages »' pull-to-refresh indicator is centred, and it is gone when the
refresh is, not after a fixed 1 100 ms (DESIGN § 10, B-331). It relies on the pull block having
moved out of the engine in b·8.

## The proof FIRST

- **Take the reading B-331 leaves open first.** The entry asks whether the spinner is off-centre
  ONLY while `.loading` is on. Sample the pull itself in the harness at 390 px: read the spinner's
  x, y and width at rest, armed, loading, and closing. The report records which moment is
  off-centre, and on the Mac, not the operator's phone.
- **The rule.** Its label is bound to the next free number. It drives a real pull on « Réglages »
  and reads:
  1. while loading, the spinner's centre is within 1 px of the viewport's centre, and it is not cut
     by the scrollport's edge;
  2. the indicator's height returns to 0 WHEN the refresh settles, meaning the query refetch the pull
     triggers, not after a fixed delay;
  3. « Actualisé. » is said after the indicator has closed, never while it is still open.
- **Red today**: reading 2, because of the fixed timer, and reading 1 if the sampling above shows
  the loading state off-centre.
- **Mutations.** With the commit made first, `scripts/mutate.sh`:
  - restores a fixed timeout: reading 2 falls, naming the delay;
  - removes the centring: reading 1 falls, naming the x offset.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on the pull states**, each accepted with « B-331 » (D8).

## The move

- **The indicator follows the refresh.** Its open/close block, moved by b·8 to `lib/pull-gesture.ts`
  and the settings surface's binding, closes on the refresh's settlement. The settings surface
  hands over its query's refetch promise, and `lib/` stays domain-free.
- **The centring** is repaired where the sampling locates it: in the variant `#ptr` wears, or in the
  spinner's transform while loading. The phase names which. If the sampling finds no off-centre
  moment on the Mac, the entry's centring half is reported as unreproduced there, and the device
  reading stays the operator's.

## Gate

Per INDEX « Gates ». In addition, B-331 closes, or has its centring half re-owned, with the
sampling and the rule's readings in the report.

## Commit

`fix(maquette-l13): the pull indicator is centred and closes when the refresh settles`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** `refetch`, `spinner`, `indicator`, `centre`/`center`, `settle` are not vocabulary words — add what the phase declares in the same commit, or name from words already there.
