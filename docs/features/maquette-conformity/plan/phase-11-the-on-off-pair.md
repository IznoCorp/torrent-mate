# Phase 11 — « actif / inactif », one row per mechanism (D.1 #2, the operator's OPEN 1 = A)

**Ruled 2026-09-29** (`/Users/izno/dev/review-archive/conformity-80/rulings-2026-09-29.md` § Q1, verbatim « A »): the
watcher switch (`pipeline.watcherEnabled`) is KEPT and RENAMED by what it does — the word in `fr.json`, never
« pipeline » nor « passage » —, ONE row in the levers block with the « actif / inactif » chip at the row's end
beside its button; the locks' row goes; « actif / inactif » (success / danger) for the seven on/off pairs of the
report's B.4; « en pause » kept for the paused pipeline. **Not a pure conversion** (a rename and a removed row are
visible): the oracle accepts those changes BY NAME.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `grep -n "trigger\|watcher" frontend/maquette/design/src/features/system/levers.tsx` → the bare word at
  **:101**, the button at **:105–108**; `grep -n "watcher" frontend/maquette/design/src/features/system/locks.tsx` →
  the second row at **:96–102**; the seven pairs read in `fr.json` (`screens.system.triggerOn/Off` « actif / coupé »,
  `watcherOn/Off`, `sentinelOn/Off`, `settings.field.enabled/disabled`, `panels.maintenance.dryRunOn/Off`,
  `screens.media.followActive/followInactive`, and L16-bis's `disabledByOperator`, not yet drawn).
- **Points ≈ 13.** The levers row → `FactRows` with the chip and its button (≈ 15 lines, 3); the locks' watcher row
  removed (1); the rename, one `fr.json` key (1); the pairs onto ONE pair of keys at `settings/panel-field.tsx:82–84`,
  `maintenance/panel-action.ts:85`, `media/media-library-facts.tsx` (≈ 12 lines, 3); dead keys removed (1);
  R-conformity-e (3); the RESUME (1).
- **Readers.** `levers.py`, `locks.py`, `levers_stay_live.py`, `machine.py` read `levers/watcher*` and
  `locks/watcher-sentinel` — the removed row's hold names its successor (the levers row), said out loud.

## Red today

R-conformity-e on `levers-idle` and `levers-trigger-off`: the watcher row's state is a chip « actif » / « inactif »
at the row's end, read from the chip (never the text span), and the page draws the fact ONCE — falls.

## Mutation

Put the bare word back → falls by name; restore the locks' row → the « once » hold falls by name.

## Oracle: states that diverge, declared by name

Every Système state drawing the levers or the locks, the settings boolean states, `maintenance-topic`, the media
sheet states drawing « suivi » (built by script) — the rename and the removed row accepted by name.

## Commit

`feat(maquette-conformity): one on/off pair, « actif / inactif », and the watcher named by what it does`
