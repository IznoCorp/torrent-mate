# L13a — resume brief for the successor

Written by the second L13a implementer when it stood down at the a·2 boundary (gauge 57 %, a·3 too large
to finish under 60 %). Read it after `docs/features/maquette-l13/BRIEF-L13a.md`, which still governs
everything; this file only records state, rulings and traps, and it dies with the wave's folder at the
post-merge gesture.

## Exact state

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, merged with `origin/main` at
  `60530dbd8` (#595, 0.98.90). Hold-count baseline 127 rules, 2 776 holds, `failed` 0; oracle reference
  `f1e7ac66`.
- **a·1 is done** at `123816c93`. **a·2 is done** at `383c67549`, one commit,
  `refactor(maquette-l13a): product code imports the shell's seams and the harness publishes them`, pushed
  with this file (the push report carries `git ls-remote --heads origin feat/maquette-l13a`).
- a·2's gate, on the shared mutex: `run.sh --contracts` 19 rules and 27 repository guards, no violation;
  `run.sh --oracle` 87 states × 34 regions, 2 958 measurements, no divergence. Beside it: `tsc` 0 errors,
  vitest 7 files / 112 tests, the cheap guards exit 0. `--compare`, the full suite, `--a11y` and `make check`
  are NOT run: they run once, at a·19.
- **Next: a·3** (`plan/phase-a03-ladder-handler.md`), then a·4 … a·19 in order.
- Version not bumped (bump above whatever `main` reads at a·19). No pull request.

## Rulings — not to be reopened

From a·1 (unchanged, see the commit `123816c93` body for the detail):

1. `harness` is a declared bucket of `scripts/check-frontend-boundaries.py`.
2. `design/src/harness/` is in the language guard's harness scope for the STRING arm only.
3. **The product never depends on the instrument.** `applyState` and the `window.state` getter stay in the
   engine; `harness/drive.ts` imports `applyState`. **a·3 moves `applyState` with `onEngineBack`.**
4. `drivenWithoutHistory(run)` is the engine's one addition; `driven` is in the vocabulary.
5. `currentRender = null` was not carried.
6. The `window.__navEchec = false` initialisation stays in the engine.
7. `installHarness()` takes no argument; the ≡ panel is `harness/panel.ts`.
8. The named states are eleven files under `harness/states/`, composed by `harness/index.ts`.

From a·2 (the steward's rulings on STOP D, 2026-09-13):

9. **R1 — the four shell doors live in `lib/shell-doors.ts`** (`toast`, `panel`, `bridge`, `screens`, `let`
   bindings filled by their app host through `fillToastDoor`/`fillPanelDoor`/`fillBridgeDoor`/
   `fillScreensDoor`); **`store` lives in `lib/store-access.ts`** (`installStore`, called by the boot). The
   app hosts are not import owners: the fan-in arm refused them (history-bridge 1 → 9, toast-host 1 → 9,
   panel-host 1 → 7, store 3 → 7), re-runnable with `plan/fanin_projection.py`.
10. **R2 — `features/acquisition/queries.ts` is in `FAN_IN_EXEMPT`**, over by buckets (2 → 5). The L13b
    phase that deletes the engine's last read of `followActions`/`suggestions` removes the entry;
    `phase-b11` says so.
11. **The six product writes `window.__navEchec = true` stay** (a write is not a read; ruling 6 voided the
    planned home).
12. `window.__mocks` stays published by the mock layer itself: the `mocks` arm lets only `app/` import
    `mocks/`. `app/outbox-wiring.ts` imports `mockLayer` behind `__MOCKS_BUILT_IN__`; the engine's
    `resetSettings` (harness-only) keeps its `window.__mocks?.` read.

What a·2 left for the next phases to know:

- **Product code imports its seams**: `store` (`lib/store-access`), `sharedQueryClient`
  (`lib/query-client`), `addressSeam` (`lib/addresses`), the four doors, and each owner's own export
  (`dialog`, `entry`, `loadingDone`, `registeredLayers`, `navigation`, `popover`, `refillProducers`,
  `unknownPanel`, `unknownProducer`, `refillEngineData`, `outboxSeam`, `releasePage`, `shellPages`,
  `suggestions`, `refillSuggestions`, `followActions`, `followVerbs`, `discover`, `searchResults`,
  `pendingDecisions`, `libraryNextPage`, `deleteLibraryItems`, `releases`, `settingLabels`, `settingsVerbs`,
  `pressNumbers`, `pullNumbers`, `queueLists`, `queueActions`, `stackedSurfaces`, `verbNames`, `mockLayer`).
- **The engine reads them through `seam`**, a getter object in `engine/seams.ts` (twenty names; the engine
  has locals `toast`, `entry`, `suggestions`). Code that a·3 and a·4 move OUT of the engine into `app/` must
  import the owners directly, never `seam` — `app/` does not import `engine/`'s seams.
- **`harness/publish.ts` publishes, as getters, exactly the 31 seams a rule reads**; `installHarness()`
  calls `publishSeams()` first. A seam a moved module stops owning moves its getter in the same commit. A
  getter a rule reads that a·3 creates (the brief's `armedExit`, `unwinding`…) is added there.
- The served identity is a `<script type="application/json" id="served-identity">` the host writes
  (`host_identity.py`) and `lib/served-identity.ts` reads; R87 (`identity.py`) is re-aimed to it.
- The media route composes the follows: `routes/media-sheet.tsx` renders `MediaRouteScreen`, which passes
  `readFollows` to `MediaScreen`.

Readings for the pull request body, taken on a·2's head:

- § 2.4 closing pass: product outside `engine/` reads 6 names on 56 lines (the engine's six); at `79db420b3`
  27 names on 211 lines. The engine reads one `window` name, `__mocks`.
- Lift-out, mocks off: JavaScript under `dist/vite/` 1 648 113 bytes (a·1: 1 651 314); the off build boots to
  `/acquisition` with 0 page errors (the 14 console errors are the static host's 404s on `/api/*` and
  `/ws/events`); 0 files name `__etatsDetailles`, `acq-now-idle`, `hscen`, `no mock route`, `publishSeams`,
  `__relay`, `__unknownProducer`. Method: a Vite config in a scratch directory that spreads the design's config
  and sets `__MOCKS_BUILT_IN__` false, built into the worktree's `dist/`, served by `python3 -m http.server`
  on a private port, read with Playwright; `dist/` deleted afterwards.
- `engine/legacy.js` 31 208 non-blank, unchanged by a·2 (every edit in place).

## Traps met — each cost a run

The a·1 traps still hold (a `cd` persists in the Bash tool; edit the engine through Python; `vite build
--outDir` elsewhere exits 1; anything the boot reads must exist before `start()`; the pre-push suite sees
tests that name moved paths; re-aim the guards a move touches; `tsc` catches what the build does not).
New in a·2:

- **The `window.__` pass is blind to BARE globals.** The engine read `__bridge.back()` with no `window.`
  on 13 lines; a scan that strips comments and strings and lists undeclared `__name` tokens found it. Run
  it on every file a phase moves.
- **A word-boundary rename crosses import paths.** `\bqueries\b` rewrote `./queries`, `search-queries` and
  TanStack's `defaultOptions.queries`; `window.__navigation` matched inside `window.__navigationState`.
  Rename an existing identifier only with `scripts/rename-identifiers.py`; for a name the phase itself just
  introduced, replace per file and re-read the diff.
- **The fan-in arm counts BUCKETS as importers** (`harness`, `engine`, `routes`, `app`), not only features.
- **Import lines count toward the 400-line ceiling**: `discover-feed.ts` (399) and `mocks/index.ts` (397)
  went over with three added imports; the harness-only declaration moved to `harness/publish.ts` and the
  publication became a chained assignment.
- **The vocabulary arm refuses words nobody wrote down** (`model`, `measures`, `queries`, `published` are
  absent); prefer a word that is there (`seam`, `numbers`, `shared`, `written`).
- **A shell loop over `"script --flag"` passes the flag inside the file name**: three guards « failed » that
  way and were green run properly.
- **`grep -rl --include` on this machine is ugrep and miscounts on a directory**; count in Python.
- **A NEW source file under `design/src` fails the pre-push suite** until
  `python3 scripts/check-maquette-comments.py --record` re-records the corpus count
  (`comment-references-baseline.json` `read`): `test_the_floor_is_derived_from_the_record` compares the
  record with the tree, and neither the contracts tier nor the oracle runs it. a·2's first push failed
  on it (389 recorded, 391 read).
