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
