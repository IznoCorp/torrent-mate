# Phase b·5 — Acquisition verbs

A BEHAVIOUR move: `acqtab`, `pill`, `fmode`, `sugmode`, `sheetprim`, `complete`, `standby`, `tmdb`,
`act=add:N` with `confirmadd`, `journey` and `sheet=plus` are registered by the acquisition feature,
and their engine branches are deleted. `journey` is the last surface-opening verb, so the contract's
count reads 0 after this phase (DESIGN § 6, row b·5; § 2.3).

## The proof FIRST

- **Re-take the rows before moving anything.** The `act` span is the largest single branch (DESIGN
  § 6 method).
- **Rules green before and after, counts unchanged**:
  - `acqtab` (eight files), `pill`, `fmode` and `sugmode`;
  - `confirmadd`: `add_footer.py`, `bugs.py` and `replacement.py`;
  - `journey`: `panel_label_once.py`, `journey.py` (R82) and `exits.py` (R103).
- **Names no rule holds get their hold FIRST** (DESIGN § 6). Each is red with its engine branch
  deleted on purpose:
  - **`sheetprim`**: the panel's primary action takes the medium. The queue records the take and
    the panel closes.
  - **`complete`**: the act lands on « Maintenant », the panel is closed, and the confirmation is
    said.
  - **`standby`**: the panel closes and the act is said.
  - **`tmdb`**: the connect action marks TMDB connected, and the discover surface leaves its error.
- **Timers are kept as they are**: `sheetprim` at 240 ms, `act=add:N` at 260 ms (DESIGN § 6).
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes each registration in turn,
  and the holding rule falls, naming the act.
- **The contract's command check**: `grep -cE "closest\.dataset\.(mediasheet|journey|resolve|releases|profile)" frontend/maquette/design/src/engine/legacy.js`
  reads **0**, recorded in the report.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the four new holds named.

## The move

- **Registered with `registerVerb` in `features/acquisition/`**, imported from
  `app/feature-verbs.ts`.
- **`act=add:N` and `confirmadd` are one move.** The engine's `act` branch opens the dialog whose
  target is `confirmadd`. `searchResults()` reads the search results by import.
- **`sheet=plus` and `act=add:N` are split** into acquisition's own English names (DESIGN § 6), with
  `scripts/rename-identifiers.py` across markup, reader and rules; re-aimed rules keep their counts.
- **`journey`** produces the journey panel by import of the panel host. The forwarder `actionTake`
  dies.
- **B-340 is NOT repaired here** (c·2). `addQ`, `addMode` and `added` stay in the store's shape.
- **Deleted from `legacy.js`**: the branches, and the helpers they alone used.
  `scripts/frontend_size_ledger.py` is re-recorded DOWNWARD in the same commit.
- **Invariant 7.** The verbs open the media screen through `data-mediasheet` (b·3), never by
  importing the media feature.

## Gate

Per INDEX « Gates ». In addition, the contract's count reads 0, the oracle shows zero divergence
(STOP B otherwise), and the red readings of the four first-holds and the mutations go in the report.

## Commit

`feat(maquette-l13): the acquisition feature answers its own delegation names and the last surface opener leaves the engine`

## Amendments

- **Amended 2026-09-13 (steward, the three arms' dry read, audit order 2):** « imports the dialog host » is VOID (fan-in: `app/dialog-host.ts` is at 4 keys) — add a dialog DOOR to `lib/shell-doors.ts` (`fillDialogDoor`, a·2 R1's shape) and re-point `features/settings/panel-setting.ts` + `secret-verbs.ts` in the same commit; « by import of the panel host » → the `panel` door (`lib/shell-doors.ts`); `sheetprim` enters the vocabulary or stays a computed key never declared; carry a·2's owed removal of `features/acquisition/queries.ts` from `FAN_IN_EXEMPT` when the engine's last read of `followActions`/`suggestions` goes (ruling 10).
- **Amended 2026-09-13 (ruling 73 b):** `actionResolve` (legacy.js `act=add:N` identify branch) and `actionTake` (the `sheetprim` branch) die here with their last callers, their `lib/engine-queue.ts` type lines with them.
- **Amended 2026-09-14 (ruling 85, after the midpoint suite):** the tap registry answers in the
  CAPTURE phase, beside the long press's click-swallower, while the engine's delegation answered in
  the BUBBLE phase — so a swallower must call `stopImmediatePropagation` AND be installed first, or
  the lift fires the verb the press's own panel put under the finger. R55 fell from this phase to
  its repair (`4210f72d5`): `sheetprim` became a registered verb here, and every later phase moves
  verbs into the same registry.
