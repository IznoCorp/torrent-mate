# Phase b·1 — Settings verbs

A BEHAVIOUR move: the settings feature registers its delegation names, and each engine branch is
deleted in the same commit (DESIGN § 6, row b·1; § 2.3). This batch goes first, because five of its
names are pure forwarders to `__settingsVerbs`, which makes it the cheapest proof that a move is
mechanical.

## The proof FIRST

- **Re-take the rows before moving anything.** Brace-match each branch inside the delegation span,
  and grep `data-<name>` and `dataset.<name>` over `design/src` and over the harness (the method of
  DESIGN § 6).
- **The rules that already hold these names run green BEFORE the move and green AFTER it, with
  counts unchanged:**
  - `settings_editing.py` (R166), `seeds_at_rest.py` (R128), `journey.py`, `page_host.py`,
    `secret_acts.py` and `settings.py`;
  - the taps per name are recorded in the report.
- **Names no rule holds get their hold FIRST** (DESIGN § 6): `to`, `deletefield` and `addfield`.
  `index` is DATA, and it rides with `deletefield`.
  - For each, a hold in the rule that reads the settings editor (the phase names which) drives the
    field from the panel. It reads the value after the act: a boolean flipped by `to`, a list entry
    removed at `index`, and a list that gained an entry.
  - **Red first**: the engine branch is deleted on purpose, before the verb is registered, and the
    hold falls naming the unchanged value. Then the verb is registered and the hold goes green.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes each `registerVerb` call in
  turn. The rule that holds that name must fall and must name the act that did not happen.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  The only movement is the new holds, each named.

## The move

- **Registered with `registerVerb` in `features/settings/`, one verb module beside the block and
  never a growth of a producer.** The names: `setting`, `secret`, `field` (with `to`), `deletefield`
  (with `index`), `addfield`, `cancelsetting`, `save`, `reloadsettings`, `restart`, `confirmrestart`
  and `qsettings`.
- **Import.** `app/feature-verbs.ts` imports the module, one import per feature.
- **The five forwarders** (`cancelsetting`, `save`, `reloadsettings`, `restart`, `confirmrestart`)
  call the feature's own verbs directly. The `__settingsVerbs` window seam then loses its product
  subject, and it stays in `harness/publish.ts` (new file, a·2) only if a rule reads it.
- **The field verbs.** They read `flattenSettings` over the cache (a·16). `changeSetting` and
  `rawValue` leave the engine for the feature.
- **`qsettings`** writes the store, and the store's own touch replaces the engine's `render()`.
- **Deleted from `legacy.js`**: the eleven branches and the settings helpers they alone used.
  `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in the same commit.
- **Invariant 7.** The verbs import no other feature.

## Gate

Per INDEX « Gates ». In addition: the oracle diverges on no state, because a moved verb draws the
same thing; any divergence is STOP B. Each new hold's red reading and each mutation go in the
report.

## Commit

`feat(maquette-l13): the settings feature answers its own delegation names`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** the store is written through `lib/store-access.ts` (a·2 R1), never `app/store.ts`; prefer the side-effect line in `app/panel-contributions.ts` (frame-domain cost 0) over a named import in `app/feature-verbs.ts`; where a call is forced, measure and raise `app.ceiling` in the same commit with the reason (a·4 precedent).
