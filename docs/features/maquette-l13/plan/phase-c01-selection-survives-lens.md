# Phase c·1 — The selection survives the lens

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands.** `git grep -n -w lens -- design/src/features/library/` → 4 real sites (the write in
  `verbs.ts:38-40`, two reads in `library-head.tsx`, a comment in `library-list.tsx`); the same walk
  over `verbs.ts` shows FOUR registered verbs writing `selected: new Set()` on a narrowing change —
  `lens` (39), `cat` (45), `setsort` (56), `clear-search` (65) — the phase names only `lens` and the
  search clear. `grep -ln 'data-lens\|selection/bar\|selmode\|delsel' harness/*.py` → 15 files touch
  the surface; `selection.py`, `selection_survives_the_tab.py` (R164, B-395's own rule — a TAB-change
  sibling, not this ruling's lens-change subject), `virtual.py`, `actions.py`, `page_host.py`,
  `stacking.py`, `desktop_frame.py` read `selected`/`selmode`/`delsel` directly. No tsc probe: the
  phase changes no type. `grep -n B-312 BUGS.md` → `open`, 1×.
- **Points ≈ 6.** 2 in-scope write sites (`verbs.ts`'s `lens` verb, `library-head.tsx`'s search
  clear) ≈ 1; one new rule (the bar's count + the dialog's titles, both read against a lens change)
  with its mutation ≈ 3; one new named state (ticking under one lens, switching to another, kept)
  ≈ 2. Mean stated once in `plan/INDEX.md`'s L13c section.
- **Found (2026-09-15).** `selection-bar.tsx`'s count (`state.selected.size` / `state.selectedMedia`)
  and `delete-dialog.ts`'s `openDeleteDialog(null, [...ticked()])` already read the FULL stored set,
  never the visible rows — the move's own words ("the selection bar counts the selected set itself,
  not the visible rows") describe a repair the READ side does not need; the whole defect is on the
  WRITE side (the four verbs above dropping the set). `cat` (category change) and `setsort` (sort
  change) drop the selection on the same "narrows what's on screen" premise as `lens` but are named
  nowhere in the move — a filter change by category is the same defect class B-312 rules on. R164
  (`selection_survives_the_tab.py`) is the closest existing precedent (reads `state.selected` across
  a page change, same `open_page`/`Journal` harness helpers) but answers a different question (tab
  survival, not lens survival) and is not itself re-aimed.
- **Amended (2026-09-15, ruling 115).** The phase covers the four verbs `lens`, `cat`, `setsort`,
  `clear-search` and `library-head.tsx`'s search commit — one hold per writer.
- **Landed (2026-09-15, rulings 116, 117).** R195, 14 holds; new state `lib-selection-filtered`; the
  driver's reset gains `libCat` and the sort; B-312 `to confirm`, B-548 filed.

A BEHAVIOUR change: the operator's ruling of 2026-09-05, « La sélection doit survivre au changement
des filtres », lands with its two guard-rails (DESIGN § 10, B-312). It relies on the `lens` verb
being the library feature's since b·6.

## The proof FIRST

The rule the repair lands with is the one B-312's entry names. Its label is bound to the next free
number, re-taken against `origin/main`.

- **What it drives.** Tick media under « Tout », then switch to « Films ».
- **What it reads**:
  1. the selection bar's count, which counts every ticked MEDIUM, including those the lens hides;
  2. the delete dialog's titles, which NAME every ticked title, including the hidden ones.
- **Red today.** Both writers drop the set on a lens change: the `lens` verb (b·6) and
  `features/library/library-head.tsx`. The count falls to what is visible, and the dialog names
  fewer titles.
- **Mutation.** With the commit made first, `scripts/mutate.sh` puts back the lens write that
  re-drops the set. The rule must fall, naming the lost titles.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on states showing a selection across a lens change**, each accepted
  with « B-312 » (D8). Any other divergence is STOP B.

## The move

- **The lens stops dropping the selection.** Both writers stop clearing it on a lens change: the
  `lens` verb in `features/library/`, and `features/library/library-head.tsx`. Clearing the search
  is re-taken against the same ruling, and the phase says whether it still clears.
- **The selection bar** (`features/library/selection-bar.tsx`) counts the selected set itself, not
  the visible rows.
- **The delete dialog** (`openDeleteDialog`, in the library feature since b·6) lists every selected
  title.
- **Invariant 7.** Nothing leaves the library feature.

## Gate

Per INDEX « Gates ». In addition, B-312 closes with the rule's red reading and its mutation.

## Commit

`fix(maquette-l13): a library selection survives a change of lens and the bar and dialog name all of it`
