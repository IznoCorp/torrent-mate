# Phase a·4 — The boot

A CONVERSION: what `__startEngine` does is the arrival, not the engine, so it becomes
`installArrival(store)` in `app/arrival.ts` (new file), and `world`, `adoptWorld` and `__releasePage` die
(DESIGN § 4.4; § 3, row 12).

## The proof FIRST

- **`boot_order.py` is RE-AIMED.** Its `BOOT_STEPS` row `^const start = window\.__startEngine;`
  becomes `^installArrival\(`. The count is unchanged, and the docstring says so.
- **`bridge.py` hold (f′) is RE-AIMED.** It keeps its one hold and now reads « the startup screen
  is hidden before any harness call », with no `typeof __startEngine` check. The count is
  unchanged, and the docstring says so.
- **Arrival readers unchanged.** `url_state.py` and `panel.py`, which read the arrival address and
  the addressed reopen, keep their counts.
- **Hold counts**: `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
- **The oracle**: zero divergence, the startup and entry states included.

## The move

- **`app/arrival.ts` (new file).** It does exactly what the engine's boot did, in the same order:
  adopt the initial state (`INITIAL_STATE` moves here), register the back handler from a·3, parse
  the arrival address, write the entry, call `__loadingDone`, push the guard entry, and reopen an
  addressed panel.
- **Where it is called.** `installArrival(store)` replaces the two lines of `start({ store })` at
  `app/shell.tsx:275–276`, so the file does not grow.
- **Deleted from `legacy.js`**: `__startEngine`, `world` and `adoptWorld`. Nothing in product code
  reads `world` except comments and the store's type (DESIGN § 4.4), so the store drops that type.
  `seedWorld` goes with `world` here (DESIGN § 2.2); its call in `__reset` (`harness/drive.ts`,
  a·1) goes in the same commit.
- **Deleted from `app/page-host.tsx`**: `__releasePage`, which no caller reads (DESIGN § 3), along
  with its type and its comment. `page_host.py` names it only in a comment.
- **Unchanged.** `engine/seams.ts` stays until b·11, and so does its « must run first » ordering
  inside the shell.
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.
- **After this phase** (DESIGN § 4.2), product code reads no `window.__` name except what the engine
  itself still publishes.

## Gate

Per INDEX « Gates ». In addition: the boot is proved by `boot_order.py` and `bridge.py` green with
their re-aims said, and by `startup.py` unchanged. STOP D if an arrival step turns out to depend on
engine state that no module owns.

## Commit

`refactor(maquette-l13): the arrival boots from the shell and the engine's handshake goes`
