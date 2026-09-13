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

## Gate

Per INDEX « Gates ». In addition, the three before/after readings above go in the report. STOP D if one of the three modules
cannot stay under 400 non-blank lines.

## Commit

`refactor(maquette-l13): the ladder's handler, the page switch and the addressed panels leave the engine`
