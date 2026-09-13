# Phase c·2 — A fresh add screen

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
