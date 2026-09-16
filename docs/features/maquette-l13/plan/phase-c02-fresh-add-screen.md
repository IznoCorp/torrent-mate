# Phase c·2 — A fresh add screen

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands.** `grep -cw -e addQ -e addMode -e added <file>` per file: `action-button.tsx` 1,
  `history-bridge.ts` 5, `arrival.ts` 3 (the initial store shape), `add-screen.tsx` 10,
  `add-label.ts` 6, `add-verbs.ts` 7, `panel-add.ts` 3, `harness/drive.ts` 1, `routes/add.tsx` 2 — 38
  site-lines across 9 files. `grep -ln 'addQ\|addMode\|"added"\|.added\b' harness/*.py` → 3 rule
  files: `add_footer.py` (named in the phase), `bugs.py`, `replacement.py` (neither named in the
  phase). No tsc probe: no contract type changes. `grep -n B-340 BUGS.md` → `open`, 1×. Named states:
  `acq-add-empty`, `acq-add-results`, `acq-identify` already exist and drive the screen through
  `window.__screens.add(q, mode)`, not through a raw store write.
- **Points ≈ 13.** 38 site-lines ≈ 8; the new rule (from B-340's expectation, two mutations — the
  stale query, `added` kept across openings) ≈ 3; three re-aimed rule files (`add_footer.py`,
  `bugs.py`, `replacement.py`) ≈ 3 (rounded down from 3+1 for the shared docstring cost). Under 15,
  no cut.
- **Found (2026-09-15).** `harness/bugs.py:154` (`chk("10. a real add brings the screen's footer into
  being", …)`) and `harness/replacement.py` (R121, DOIT-8, three reads of
  `window.__store.read().state.added`) read the global `state.added` set DIRECTLY — neither is named
  in the phase's "readers re-taken" list, and both silently break once `added` leaves the store for
  `add-screen.tsx`'s local, visit-scoped state. `app/history-bridge.ts`'s `add()` opener already
  writes `store.write({ addQ, addMode })` "kept in sync… before navigating" for `addVerb` and the
  cross-world `add:N` panel act (per its own comment) — those two readers, not named in the move
  either, are what actually still needs the legacy fields once `add-screen.tsx` stops reading them.
- **Landed (2026-09-15).** R196, 7 holds; `add-visit.ts`; the identity key carries the kind (the
  search seed gives a film its series' identifiers); R121 and bugs.py re-aimed; B-340 `to confirm`.

A BEHAVIOUR change: « + » opens the add screen empty (query empty, mode `follow`, nothing added),
while the identify path keeps seeding the folder's name. `addQ`, `addMode` and `added` leave the
store's legacy shape (DESIGN § 10, B-340).

## The proof FIRST

B-340's entry states the expectation but names no rule, so the rule is written from that
expectation. Its label is bound to the next free number.

- **What it drives.** Search, then add a result, then leave the add screen, then tap « + ».
- **What it reads**:
  1. the query field is empty;
  2. the mode is `follow`;
  3. no « 2 médias ajoutés » strip is shown, and no result carries « ✓ Ajouté »;
  4. separately, « Identifier » from a resolution opens the add screen with the folder's name seeded,
     unchanged.
- **Red today** on readings 1–3. The floating action button hands the last entry query back in, and
  `added` is cleared only by named states and the initial store.
- **Mutation.** With the commit made first, `scripts/mutate.sh` makes the button pass the stored
  query again. Reading 1 falls, naming the stale query. A second mutation keeps `added` across
  openings, and reading 3 falls.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on add-screen states reached from « + »**, each accepted with
  « B-340 » (D8).

## The move

- **The button opens a fresh screen.** `app/action-button.tsx` opens the add screen with an empty
  query and mode `follow`, through the screens crossing by import.
- **The add screen owns its own state.** `addQ`, `addMode` and `added` leave the store and belong
  to `features/acquisition/add-screen.tsx`. The query comes from the router's `q` (the file's own
  comment calls the store copy « stale by construction »). The added set is scoped to one visit
  and keyed by the result's IDENTITY (`ids`, a·6), never by its position.
- **The identify path is unchanged.** It seeds the folder's name through the screens crossing,
  exactly as today.
- **Readers re-taken.** The harness's named states that wrote `added` or `addQ` into the store
  (`harness/states/acquisition.ts` (new file, a·1)) and `add_footer.py` are re-taken, and each re-aim is said.
- **B-339's « ✓ Ajouté » on a result never added** is this defect seen from the panel. The phase
  reads whether it is gone and says so, without repairing the drawing (c·3).

## Gate

Per INDEX « Gates ». In addition, B-340 closes with the rule's red reading and its mutations.

## Commit

`fix(maquette-l13): the add button opens a fresh add screen and identify still seeds the folder`
