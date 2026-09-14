# Phase a·3 — The ladder's handler

A CONVERSION: the back handler and its rungs, the page switch, and the addressed-panel table leave the engine for three
`app/` modules, with no change in behaviour (DESIGN § 4.3; § 3, rows 9–11; § 9.2).

## The proof FIRST

- **Hold counts unchanged.** Run `python3 scripts/harness-hold-counts.py --compare` and read `failed` first. These counts
  must not move:
  - R59 `back.py`, R65 `drawer.py`, R69 `url_state.py`, R82 `journey.py` and R94 `scroll_memory.py` (DESIGN § 3);
  - `pop.py` and `panel.py`.
- **RE-AIMED rules.** `drawer.py` and `exits.py`, where they read `__layers`: the registry folds into `app/layers.ts` (new
  file) and keeps its published name. Each keeps its count, said in its docstring.
- **The oracle**: zero divergence.
- **The defects this phase must NOT touch read the same after the move.**
  - Run B-290's recipe before and after: « Voir la fiche » from an open panel, then `page.go_back()`, reading
    `history.state.__TSR_index` (3 → 1).
  - Run the settings walk of `settings_editing.py` (B-397's extra Back).
  - Run B-275's flow (Back lands on `/` with the panel shut).

  An identical reading is the proof that nothing moved. A changed one means the edit was hidden inside the move, which is
  STOP B.

## The move

- **`app/layers.ts` (new file)**:
  - the ranked registrations — dialog > drawer > sheet, plus the `#screen` rung until a·5 deletes it;
  - the back handler (the engine's `onEngineBack`);
  - `closeLayers` (the engine's `__closeLayers`) and `hideLayers`;
  - `unwindLayer` with its latch (the engine's `__derouler`), and `__announcePops`.

  `app/layer-registry.ts` folds into it and is deleted. The SHEET registers as a rung from `app/panel-host.ts`.
- **`app/page-switch.ts` (new file)**: `navigationState`, `recordPath`, `replacePath`, `switchPage`,
  `switchPageFromLayer`, the floor flags and the exit guard. `drivenWithoutHistory` (a·1) moves here with its three readers.
- **`app/addressed-panels.ts` (new file)**: `REOPEN` and `reopenAddressedPanel`. `knownMedium` moves here too and
  asks the cache (DESIGN § 3).
- **Why three files and not one.** « One `app/layers.ts` (new file) » cannot hold all three halves under the 400-line
  ceiling (DESIGN § 9.2). Each file stays under 400 non-blank lines, and the handler keeps the name.
- **Imports replace the window reads**:
  - of `__closeLayers`: `ui/sheet.tsx`, `app/focus.ts`, `app/drawer-gesture.ts`;
  - of `__derouler`: `app/dialog-host.ts`, `app/drawer.tsx`, `app/panel-host.ts`;
  - of `__navigationState`: `app/entry.ts` and the two `topic-verb.ts` files;
  - of `__announcePops`: `app/history-bridge.ts`.

  `ui/` importing `app/` carries shape, not domain (invariant 10). The layering arm is read before the commit.
- **The getters that leave with these modules** (DESIGN § 6): `unwinding`, `unwindInProgress`,
  `armedExit`, `currentRender`. `armedExit` is read by 25 rule lines (`journey.py`, `panel.py`,
  `url_state.py`) and is published by `harness/publish.ts` (new file, a·2) from `app/page-switch.ts`,
  under the same name, counts unchanged.
- **The engine's delegation keeps calling** `switchPage` and `switchPageFromLayer`, now BY IMPORT, until L13b.
  `__bridge.onBack(onEngineBack)` also stays inside `__startEngine`, calling the imported handler, until a·4.
- **Out of scope.** B-229 is already closed (`fixed #528`). B-290, B-397 and B-275 are NOT touched here: their shape is
  L13b's (DESIGN § 8).
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in the same
  commit.

**Added 2026-09-13 by phase a·1's amendment.** `applyState` did not leave the engine in a·1: `onEngineBack` restores a page through it, so it moves HERE, with the handler, into the ladder's modules under `app/`, and `harness/drive.ts` re-points its import. The product never imports the harness.

**Amended 2026-09-13 by phase a·3, on the steward's two rulings of that day (STOP D) and what the move measured.**

- **`knownMedium` does NOT ask the cache in this phase**, and the line above that says it does is VOID. Its answer is
  `follows() ∪ INCOMPLETE ∪ LIBRARY`; the last two are engine fixtures (345 and 12 rows), and the cache's library
  listing is PAGED (`/api/library/items`, 24 per page, queried on `/media` only), so a cache reading would narrow a
  typed `?panel=follow:<title>` to the pages a surface happened to load — a behaviour change. `app/addressed-panels.ts`
  exports `installKnownMedium(answer)` and the engine hands its fixture-reading predicate in at evaluation. The cache
  reading lands with the phase that kills `LIBRARY` (a·10 says so); that phase decides whether the narrowed resolution
  is a behaviour change to file or whether a·6's `ids` makes the predicate unnecessary.
- **`navigationState` lives in `lib/navigation-entry.ts`, not in `app/page-switch.ts`** — that half of the move's
  second bullet is VOID. Measured: `check-frontend-boundaries.py` refused `app/page-switch.ts imported by 5 features:
  app, engine, harness, maintenance, settings` (ceiling 4). The shape of a navigation entry is a pure read of the store,
  and `lib/` is where ruling 9 of a·2 put the seams several buckets read.
- **`unwinding` and `currentRender` stay in the engine** beside `closeScreen`, whose locals they are; a·5 deletes the
  three. No rule reads either getter. The « getters that leave » bullet is VOID for those two; `unwindInProgress` leaves
  unpublished (no reader) and `armedExit` is published by `harness/publish.ts` from `walk.armedExit`.
- **The `#screen` rung is registered by the engine** beside `closeScreen` (`registerLayer("screen", …)`), because
  `closeScreen` stays until a·5; nothing opens `#screen` (`grep -rn "#screen" design/src`).
- **`window.__closeLayers`** is read by `audit2.py`, `press.py` and `stacking.py`, so `harness/publish.ts` publishes it
  from `app/layers.ts`, same name. `__derouler`, `__navigationState` and `__announcePops` had no rule reader and are
  published nowhere; the latch's multi-entry verb is `announceEntries` (`pops` is not in the vocabulary).
- **The entry's dials are written ONCE** (`ENTRY_DIALS` + `entryPatch` in `lib/navigation-entry.ts`): the entry is
  written from them and the handler restores the page from them, same keys, order and values. Measured:
  `check-frame-domain.py` counts the page aliases inside the dial names once they leave the exempt engine — the
  literal move read lib/ 28 and app/ 146; written once, lib/ 23 — and `scripts/frame-domain-baseline.json`'s lib/
  ceiling is raised 18 → 23 with its reason (steward's ruling). app/ reads 130, unchanged, once `applyState` stays in
  the engine (next bullet).
- **`applyState` STAYS IN THE ENGINE**, beside the `render()` and the `port` it uses, and the addition of phase a·1's
  amendment below that moves it HERE is VOID. Measured: `check-state-ownership.py` refused `app/layers.ts: a write
  whose argument is not a literal (patch…)` — the page restore forwards a patch it did not compose, which the arm
  refuses in `app/` and reads only as the engine's. The engine hands it to the ladder through
  `installPageRestore(applyState)` (the `knownMedium` shape), the handler calls `restorePage(entryPatch(entry))`, and
  `harness/drive.ts` keeps importing it from `legacy.js`. It leaves at **b·7**, the phase where `render()` has no
  caller left (DESIGN § 3, row 4) (steward's ruling).
- **The exit warning's words** (« Encore un retour pour quitter TorrentMate. ») move to `fr.json` as
  `message.oneMoreBack`: the language rule forbids them in `app/`. Same text on screen.

## Gate

Per INDEX « Gates ». In addition, the three before/after readings above go in the report. STOP D if one of the three modules
cannot stay under 400 non-blank lines.

## Commit

`refactor(maquette-l13): the ladder's handler, the page switch and the addressed panels leave the engine`
