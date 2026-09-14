# Phase b·7 — Frame verbs

A BEHAVIOUR move: `page`, `go`, `navgo`, `drawer`, `toast`, `phase` and `panel` are registered in
`app/`, and the delegation listener itself is deleted, because no name is left in it (DESIGN § 6,
row b·7; § 2.3).

## The proof FIRST

- **Re-take the rows before moving anything** (DESIGN § 6 method). This is the heaviest batch by
  taps, and the phase records the files per name.
- **Rules green before and after, counts unchanged**:
  - `page`: seventeen files;
  - `go` and `navgo`: `back.py` (R59), `drawer.py` (R65), `url_state.py` (R69) and `pop.py` among
    them;
  - `drawer`: `drawer.py`;
  - `toast`: `audit2.py`, `said_and_done.py`, `secret_acts.py`;
  - `phase`: `priming.py`;
  - `panel`: twenty files, `panel.py` and `paths_to_sheets.py` among them.
- **No name here lacks a rule.**
- **The listener's death is proved by its absence.** After the commit,
  `grep -n "addEventListener(\"click\"" frontend/maquette/design/src/engine/legacy.js` finds no
  document click listener in bubble phase, and every rule above is green. That combination is what
  says no name was lost.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes each registration in turn:
  - `page` → `url_state.py` falls, naming the page that did not change;
  - `panel` → `panel.py` falls, naming the panel that did not open;
  - `drawer` → `drawer.py` falls.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  no movement.

## The move

- **Registered with `registerVerb` in `app/`.** These are frame verbs, not a feature's. Their module
  sits beside `app/page-switch.ts` (new file, a·3) and `app/layers.ts` (new file, a·3), and `app/panel-contributions.ts` is where
  the `panel` verb meets the producers.
- **`page`, `go` and `navgo`** call `switchPage` and `switchPageFromLayer` inside `app/`. The engine
  then has no caller of either (DESIGN § 6: this is why the frame goes last).
- **The window names they replace.** `drawer` opens through the drawer module, not `openDrawer`.
  `toast` imports the toast host. `panel` resolves its target through the producers (`openPanel`
  and `refPanel` leave the engine). `phase` writes the store.
- **Deleted from `legacy.js`**: the branches, the document click listener, `hideLayers`' last engine
  caller, and the helpers only these branches used. `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.
- **`render()` has no caller left.** The rule lines that call `render()` (DESIGN § 2.4, 23 lines in
  10 files) are RE-AIMED to `__store.touch()` in this commit (DESIGN § 3, row 4). Each keeps its
  count, said in its docstring, and each is named in the commit body. `render` dies here unless
  the phase finds a caller outside the delegation.
- **Timers are kept as they are** (DESIGN § 6); b·9 removes them.

## Gate

Per INDEX « Gates ». In addition, the oracle shows zero divergence (STOP B otherwise). The absent
listener, the `render()` re-aims and the mutations go in the report.

## Commit

`feat(maquette-l13): the frame answers its own delegation names and the engine's click listener dies`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** nothing in `app/` imports the frame-verb module back (the boot calls it — cycles arm); page-alias literals in `app/` are frame-domain cost, measured after the move; `applyState` leaves the engine here (ruling 16).
- **Amended 2026-09-14 (b·7 as landed; rulings 86 and 87, two of whose clauses the MEASUREMENTS
  correct — reported to the steward):** the phase moves SIX names, not seven, and the listener keeps
  TWO branches, not one.
  - « the delegation listener itself is deleted, because no name is left in it » is wrong as
    written: it answered EIGHT dataset keys. `pipe` was known to stay (ruling 74); `phase` stays
    too, measured — `check-state-ownership.py` classifies it as SERVER STATE and refuses a
    component (`app/` included, `COMPONENT_BUCKETS` line 55) writing such a key at a ceiling of 0,
    exactly as it refuses `pipe`. Both leave with their conversion, and the listener with them.
  - « `applyState` leaves the engine here » (ruling 16, restated as ruling 86 d) cannot hold
    either: the restore writes a patch composed elsewhere, and that same arm refuses a write whose
    argument it cannot read — « a key it cannot classify is a key that would otherwise leave the
    count meaning the ones I could read ». The engine is the one module it exempts, so the restore
    leaves when the engine does. It was moved, measured red, and moved back: `app/layers.ts` says
    why in place.
  - « `render()` has no caller left » is wrong: it has SEVEN product callers outside the delegation
    (six features' `redraw()` and `app/arrival.ts`) and it settles a page id the navigation table
    does not carry, so it stays until b·11 (ruling 57) and the frame's verbs redraw through it.
  - The rule re-aim is 43 call lines in 9 files, not « 23 in 10 ».
  - The tap registry answers the first REGISTERED dataset key in ATTRIBUTE order, so registering
    `panel` made four emitters' order load-bearing — the three the design named plus the suggestion
    tile (`features/acquisition/discover-cards.ts`), found by walking every element carrying both
    keys rather than trusting the list.
  - The acquisition page's landing dial is written by ACQUISITION, through a `landOnPage` door
    (ruling 9's shape): the frame may not name a page's dial (invariant 10), and a forwarded patch
    is what the ownership arm refuses — so the write is made where the dial is understood.
  - `check-markup-contracts.py`'s forwarded-value arm lost its subject entirely and was deleted
    with its tests (ruling 87, register row B-513).
