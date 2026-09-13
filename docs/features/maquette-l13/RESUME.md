# L13a — resume brief for the successor

Written by the third L13a implementer when it stood down at the a·4 boundary (gauge past 50 %, the steward's call). Read it after
`docs/features/maquette-l13/BRIEF-L13a.md`, which still governs everything; this file only records
state, rulings and traps, and it dies with the wave's folder at the post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at
  `60530dbd8` (#595, 0.98.90). Oracle reference `f1e7ac66`.
- **a·1** `123816c93`, **a·2** `383c67549`, **a·3** `40fc7b785`, **a·4** `ad4d3096a`
  (`refactor(maquette-l13a): the arrival boots from the shell and the engine's handshake goes`), then `4918abe65` (`fix(maquette-l13a): url_state.py drives the sign-in gate through the entry seam a·1 left it`).
- a·3's gate (on `40fc7b785`, shared mutex): `run.sh --contracts` 19 rules and 27 guards, no violation;
  `run.sh --oracle` 87 states × 34 regions, 2 958 measurements, no divergence. Beside it: `tsc` 0 errors, vitest
  7 files / 112 tests, every cheap guard exit 0. Before/after readings byte-identical (B-290/B-275 walk index
  2 → 3 → `/` index 1, panel shut; `settings_editing.py` 15 holds).
- a·4's gate (on `4918abe65`, shared mutex): `bridge.py` 10, `startup.py` 28, `panel.py` 51, `url_state.py` 99 —
  each alone, each its baseline count, no violation; `run.sh --contracts` 19 rules and 27 guards, no violation;
  `run.sh --oracle` 2 958 measurements, no divergence. `tsc` 0, vitest 7 / 112, every cheap guard exit 0.
- `engine/legacy.js` 30 276 non-blank (31 208 at the wave's base), ledger re-recorded. `--compare`, the full
  suite, `--a11y` and `make check` are NOT run: they run once, at a·19.
- **Next: a·5** (`plan/phase-a05-dead-code.md`) — include the release machinery `app/page-host.tsx` can no longer reach (phase-a04's amendment).
- Version not bumped. No pull request.

## Rulings — not to be reopened

1–12: see the a·2 RESUME rulings (in git: `git show 36cc38a4c:docs/features/maquette-l13/RESUME.md`), carried
over unchanged, except 3's « a·3 moves `applyState` with `onEngineBack` », voided by 16.

From a·3 (the steward's rulings on four STOP D, 2026-09-13; all written into `phase-a03`, one into `phase-a10`):

13. **`knownMedium` stays fixture-backed** (`follows() ∪ INCOMPLETE ∪ LIBRARY`) and is handed in through
    `installKnownMedium` (`app/addressed-panels.ts`); the cache reading lands with the phase that kills
    `LIBRARY` (a·10), which decides whether the narrower answer is a behaviour change to file. `INCOMPLETE` has no
    phase naming its death.
14. **`navigationState` lives in `lib/navigation-entry.ts`** (fan-in refused `app/page-switch.ts` at 5); the
    entry's dials are written ONCE (`ENTRY_DIALS`, `entryPatch`).
15. **`scripts/frame-domain-baseline.json` lib 18 → 23** for those dial names; app stays 130.
16. **`applyState` stays in the engine** beside `render()`/`port`, handed in through `installPageRestore`;
    `harness/drive.ts` imports it from `legacy.js`; it leaves at b·7.
17. `unwinding`/`currentRender` stay with `closeScreen` until a·5; the `#screen` rung is registered by the engine.
18. `harness/publish.ts` publishes `__closeLayers` and `armedExit`; `__derouler`, `__navigationState`,
    `__announcePops` are published nowhere (no rule reader). `BACK_WINDOW` is `converted` in
    `fixture-register.json`.

From a·4:

19. **`app/arrival.ts`** holds `INITIAL_STATE` and `installArrival(store)`; the engine's `store` is the
    `lib/store-access` import; the arrival draws through `window.__referentiel.render()`.
20. **`frame-domain-baseline.json` app 130 → 138** for INITIAL_STATE's eight page-alias words.
21. **`fixture-register.json` `$anonymous.count` 1 → 0**; `boot_order.py` and `bridge.py` (f′) re-aimed, counts unchanged.

## A defect of a·1 found at a·4's gate

`url_state.py` crashed since a·1 (`123816c93`) on `window.hideSignIn()` at lines 299, 328 and 345 — the engine
forwarder a·1 removed without re-aiming them. Ruled and fixed at `4918abe65`: the three calls go through
`window.__entry.hideSignIn()`, count unchanged (99). No other rule read one of the nine forwarders.
Lesson: a rule outside the contracts tier and the oracle is read by NO per-phase gate — when a phase removes a
`window` name, grep every `harness/*.py` string for it, not only the rules the phase names.

## What a·3 left for the next phases to know

- The walk's facts are ONE exported object, `walk` in `app/page-switch.ts` (`driven`, `homeFloorExists`,
  `arrivalWithoutFloor`, `armedExit`, `afterUnwind`); the engine's boot still writes three of them — a·4's
  `app/arrival.ts` takes those writes.
- The ladder walks `RANK = dialog, drawer, screen, sheet` over registrations; a·5 deletes the screen rung with
  `closeScreen`.
- The exit warning's words are `message.oneMoreBack` in `fr.json`.

## Traps met — each cost a run

**RULE FOR EVERY LATER PHASE (steward's ruling, 2026-09-13).** Before a phase's gate, run
`grep -nE "window\.<name>\b" frontend/maquette/harness/*.py` — and the bare `=><name>(` form — for EVERY name the
phase removes or stops publishing, and replay each rule that reads one, wrapped, alone. The per-phase gate
(contracts + oracle) does not run those rules, and the full suite only runs at a·19: that is how a·1's hole in
`url_state.py` stayed invisible through three gates.

The a·1 and a·2 traps still hold. New in a·3:

- **A move out of the engine is read by guards the engine was exempt from**: `check-state-ownership`
  (non-literal store writes), `check-frame-domain` (page aliases inside identifiers — `acqTab`, `libLens`),
  `check-mock-seeds` (the fixture register lists engine constants such as `BACK_WINDOW`). Run all three on the
  working tree BEFORE the first browser run; the contracts tier runs them and costs a build to learn it.
- **`ENGINE_OWNED` does not cover an unreadable write**: the arm records unreadable sites before it tests the
  exemption.
- **`json.dumps` must keep the file's indent** (`frame-domain-baseline.json` is 2 spaces); check with
  `git diff --numstat` against the base.
- **Playwright from a scratch probe needs `channel="chrome"`** — the bundled headless shell is not installed.
- **`heavy.sh --class browser` can hold off for many minutes on the 4096 MB floor** with nothing of the wave
  running; a Bash call past 600 s is moved to the background — do not relaunch it.
- **vitest here has no `--minWorkers`**; `--maxWorkers=2` alone.
- **A scripted scan of `window` names read by the rules missed a known reader twice**; a plain
  `grep -nE "window\.NAME\(|=>NAME\("` over `harness/*.py` found it. Prove a scanner on a known case first.
