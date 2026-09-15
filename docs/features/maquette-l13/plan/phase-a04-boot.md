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
- **Unchanged.** `engine/seams.ts` stays until b·13, and so does its « must run first » ordering
  inside the shell.
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.
- **After this phase** (DESIGN § 4.2), product code reads no `window.__` name except what the engine
  itself still publishes.

**Amended 2026-09-13 by phase a·4, on what the move measured.**

- **The engine's own `store` binding** (`let store = null`, filled by `__startEngine`) is replaced by the import of
  `lib/store-access.ts`'s `store`, which the shell installs before anything calls the engine. Without it every engine
  read of `store` would stay `null` once the handshake is gone. Its evaluation-time reads were all optional
  (`store?.`), and the two that remain (`render()`'s `store?.touch()`, the published `store` getter) read the same object.
- **`bridge.py` (f′)**: its first hold read `typeof window.__startEngine`; it is RE-AIMED to the arrival's own entry
  (`history.state.tm === "nav"` at load), so the count is unchanged and the hold still falls if the arrival never runs.
  The « it keeps its one hold » of the proof section miscounted (f′ is two holds): both stay.
- **The arrival draws through `window.__referentiel.render()`** — the engine's own publication, the one kind of
  `window` read this phase leaves in product code — because `app/` cannot import the engine (the cycles arm).
- **`fixture-register.json` `$anonymous.count` 1 → 0**: the last pure literal inside an anonymous engine function left
  with `__startEngine` (`check-mock-seeds.py`).
- **`releasePage` is gone, and the release machinery it drove is now unreachable**: `released`, `setReleased`,
  `subscribeRelease` and the `isReleased` branch in `app/page-host.tsx` can no longer become true. Deleting them is
  « what nobody reaches » — a·5's kind of change — and they are left for a·5 rather than slipped into this commit.
- **`scripts/frame-domain-baseline.json` app 130 → 138** (steward's ruling): `INITIAL_STATE` in `app/arrival.ts`
  carries eight page-alias words the exempt engine held (`check-frame-domain.py` measured them by its own vocabulary).
- **Prose left as it stands**: `frontend/maquette/README.md` (the handover paragraph naming `window.__releasePage`) and
  `regions.json` R74's description naming `window.__startEngine` describe removed mechanisms; the README is L13c c·9's.

## Gate

Per INDEX « Gates ». In addition: the boot is proved by `boot_order.py` and `bridge.py` green with
their re-aims said, and by `startup.py` unchanged. STOP D if an arrival step turns out to depend on
engine state that no module owns.

## Commit

`refactor(maquette-l13): the arrival boots from the shell and the engine's handshake goes`
