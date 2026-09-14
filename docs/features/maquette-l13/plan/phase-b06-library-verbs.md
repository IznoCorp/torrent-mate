# Phase b·6 — Library verbs

A BEHAVIOUR move: `lens`, `cat`, `lmode`, `sort`, `setsort` with `reversed`, `clearq`, `selmode`,
`delsel`, `tile` with `selectedTitle`, `del` and the `.act` class branch are registered by the
library feature. `mediaNamedBy` and `openDeleteDialog` leave the engine for the feature (DESIGN § 6,
row b·6; § 2.2).

## The proof FIRST

- **Re-take the rows before moving anything** (DESIGN § 6 method).
- **Rules green before and after, counts unchanged**:
  - `lens`, over seven files;
  - `cat`: `page_host.py` and `filters.py`;
  - `lmode`, `sort`, and `setsort` with `reversed` (`library_sort.py`);
  - `selmode`, `delsel`, `tile`, `del` (`page_host.py`);
  - `clearq`.
- **The name no rule holds gets its hold FIRST**: `selectedTitle`, which is DATA riding with `tile`.
  - In selection mode, tapping a tile ticks the medium NAMED by `data-selected-title`: the selection
    bar counts it, and the delete dialog names that title.
  - **Red first**: with the `tile` branch deleted on purpose, the hold falls, naming the title that
    was not ticked.
- **B-312 does NOT change.** A lens change still drops the selection, as the moved `lens` verb writes
  it, and c·1 carries the ruling. The phase reads it before and after.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes each registration in turn,
  and the holding rule falls, naming the act. For `setsort`: `library_sort.py` names the order that
  did not change.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new hold named.

## The move

- **Registered with `registerVerb` in `features/library/`**, imported from `app/feature-verbs.ts`.
- **`clearq` is split** (DESIGN § 6): `lib` becomes the library's own English name, `foll`
  acquisition's, with `scripts/rename-identifiers.py` across markup, reader and rules. Neither feature
  imports the other.
- **`.act` takes no new name** (DESIGN § 6). The class branch dies: a follow's swipe actions emit
  `data-pause` and `data-remove` (already registered, L21) and a library row's removal emits
  `data-del` (registered here).
- **`mediaNamedBy` and `openDeleteDialog`** move to `features/library/`, reading the library query's
  cache (a·10), with the delete dialog opened through the dialog host by import.
  **Amended 2026-09-13 by phase a·10 (the steward's ruling 41):** « reading the library query's cache (a·10) » is
  VOID. The paged listing has no exact answer. `mediaNamedBy` moves with the verb and reads `window.LIBRARY`, as
  `follow-facts.ts:103` does, and `openDeleteDialog` reads `window.INCOMPLETE`. Both switch in b·10-bis, where the
  two fixtures die.
- **`paintSelBar`**, the empty function, dies. With the `tile` branch goes the comment B-465 names
  (« paintSelBar() below draws the bar directly »), and **B-465 closes** because its subject is
  deleted.
- **Deleted from `legacy.js`**: the branches and helpers. `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition, the oracle shows zero divergence (STOP B otherwise), and B-465's
closing reading is in the report: `grep -n "paintSelBar" frontend/maquette/design/src/engine/legacy.js`
returns nothing.

## Commit

`feat(maquette-l13): the library feature answers its own delegation names and owns its delete dialog`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** the same dialog-door amendment as b·5 (the library never imports `app/dialog-host.ts`); `mediaNamedBy` reads `window.LIBRARY` until b·10-bis (ruling 41).
- **Amended 2026-09-14 (ruling 79):** `tile` is NOT registered — the registry answers the first registered dataset key in attribute order and a tile emits `data-tile` before `data-mediasheet`; the library registers `selected-title` (selection mode only) and `data-tile` stays the rules' index. `.act`: pause/remove emit `data-pause`/`data-remove`, the three verbs call `window.collapseCard?.()` until b·8, « chercher » emits `data-toast`; the followed warning reads a `followedTitles` door in `lib/shell-doors.ts`; `clearq` → `data-clear-search` / `data-clear-filter`.
- **Amended 2026-09-14 (rulings 81, 82, 84):** `clear-filter` and `search-again` had no tapping rule — their holds went first (`follows.py`, `pause_verb.py` R132); the fan-in arm refused `app/page-switch.ts` at 5 → a `replaceAddress` door; R164 fell twice under the 28-named gate load and is filed as B-512 with its capture armed; the gate on `e4a16d970` is green.
