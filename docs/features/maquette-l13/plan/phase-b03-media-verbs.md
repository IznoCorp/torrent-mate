# Phase b·3 — Media verbs

A BEHAVIOUR move: `mediasheet` (a surface-opening verb) and `ep` (DATA: the episode the popover
opens on) are registered by the media feature, and their engine branches are deleted (DESIGN § 6,
row b·3; § 2.3).

## The proof FIRST

- **Re-take the rows before moving anything** (DESIGN § 6 method). The emitters are:
  - panel targets in `features/acquisition/panel-journey.ts`, `panel-suggestion.ts`, `panel-add.ts`
    and `follow-actions.ts`;
  - `features/acquisition/discover-cards.ts`;
  - the card and tile components that replaced the engine builders (a·9–a·11).
- **Rules green before and after, counts unchanged.** Every rule tapping `data-mediasheet`: the
  sixteen files the design counts, `screen_addresses.py`, `transition.py` (R115),
  `followed_sheet_act.py` and `audit.py` among them. `pop.py` taps `ep`.
- **No name here lacks a rule.**
- **B-290's reading does not change.** « Voir la fiche » still closes the panel inside the
  navigation's commit and keeps its entry: `history.state.__TSR_index` goes 3 → 1 across Back, as
  B-290 measures. The phase reads it before and after. A changed reading is the shape b·9 decides,
  arriving early, which is STOP B.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes the `mediasheet`
  registration: `screen_addresses.py` falls, naming the screen that did not open. Then it removes
  the `ep` registration: `pop.py` falls, naming the popover that did not open.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  no movement.

## The move

- **Registered with `registerVerb` in `features/media/`**, imported from `app/feature-verbs.ts`.
- **`mediasheet`** reads the title from `data-mediasheet` and the provider identity from the list's
  `ids` (a·14), and calls the screens crossing by import.
  - The acquisition markup EMITS the attribute and never imports the media feature: a `data-*` name
    is the contract between them (invariant 7).
- **`ep`** becomes the popover's opening verb. `openPopEp` leaves the engine, and the episode wording
  and the popover open are imports of their owners, not `__episodeSaying` and `__popover`. Those
  window names stay in `harness/publish.ts` (new file, a·2) only while a rule reads them.
- **Deleted from `legacy.js`**: the two branches, and the popover helpers they alone used.
  `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in the same commit.
- **The contract's count moves.** `grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)"`
  over `legacy.js` loses the `mediasheet` lines.

## Gate

Per INDEX « Gates ». In addition, the oracle shows zero divergence (STOP B otherwise), and the B-290
before/after reading goes in the report.

## Commit

`feat(maquette-l13): the media feature opens its sheet and its episode popover itself`

## Amendments

- **Amended 2026-09-13 (ruling 70):** `screen_addresses.py` opens the sheet by ADDRESS and cannot witness a tap; the `mediasheet` witnesses are `transition.py` (R115) and `paths_to_sheets.py`.
- **Amended 2026-09-13 (ruling 70-bis):** `paths_to_sheets.py` reads reachability in markup and cannot witness a tap either; `transition.py` is the named witness.
