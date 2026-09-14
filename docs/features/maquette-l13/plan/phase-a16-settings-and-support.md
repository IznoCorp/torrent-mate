# Phase a·16 — « Configuration », and the engine's support

A CONVERSION: `allSettings` becomes `flattenSettings` over the cache; `field`, `readonly` and
`rulenote` become variants; `SETTINGS` dies; and the React-side support for the engine dies with
its last reader: `engine-shape.ts`, `engine-data.ts`, `engine-redraw.ts`, `lib/engine-drawing.ts`
and `__referentiel` (DESIGN § 2.5, § 5.1; § 3, rows 17–19).

## The proof FIRST

- **The oracle**: zero divergence on every settings state, including search, the field editors and
  the read-only field. Any other divergence is STOP B.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
  - `settings.py` and `page_host.py` are RE-AIMED where they read `SETTINGS` or `SETTINGS_STATE`:
    they now read the settings query's cache or its seed. Each keeps its count, said in its
    docstring.
  - `settings_editing.py` (R166) and `seeds_at_rest.py` (R128) keep their counts.
- **Fixture checks.** `python3 scripts/check-mock-seeds.py` exit 0 with `SETTINGS` marked
  `converted`.
- **The readonly margin, measured.** `.field.readonly .rulenote { margin: 0 }` overrides the
  variant's bottom margin today. The readonly variant must carry that zero, and the oracle on the
  read-only field is the proof.

## The move

- **`allSettings` becomes `flattenSettings`.** It is `flattenSettings(cache)`, using the existing
  `features/settings/catalog.ts` function over the settings query's data.
  - `features/settings/page.tsx` reads it directly.
  - The engine's field branches (`field`, `deletefield`, `addfield`) read it through that same
    function until b·1 moves them.
  - `harness/states/settings.ts` (new file, a·1), the table's former `states.js` reader, reads it too.
- **Variants.** `field`, `readonly` and `rulenote` become variants in
  `features/settings/variants.ts`, and their rules are deleted.
- **Deleted from `legacy.js`**: `SETTINGS`, `resetSettings` and the engine's `allSettings`, once
  nothing calls them.
- **The React-side support dies here, because its last reader is converted.**
  - Deleted: `engine/engine-shape.ts` and its test, `app/engine-data.ts`, `app/engine-redraw.ts`,
    `lib/engine-drawing.ts`, and `__referentiel`.
  - Readers of `__referentiel` import per feature instead: `features/settings/topic-verb.ts`,
    `features/settings/panel-secret.ts` and `app/history-bridge.ts`.
- **Guard exemptions lose their subject in this commit.** In
  `scripts/check-frontend-boundaries.py`, `FAN_IN_EXEMPT` loses `engine/engine-shape.ts`, and
  `OUTSIDE_IMPORTS_ALLOWED` loses `engine/engine-shape.ts` and its test.
- **`render()`, re-taken.** `render` survives while a delegation branch calls it (until L13b), so the
  rule lines that call `render()` are re-aimed to `__store.touch()` only if this commit removes
  their subject (DESIGN § 3, row 4). The phase re-takes the callers first and names each re-aim.
- **The seam count, re-taken.** The seven `dangerouslySetInnerHTML` sites of DESIGN § 2.5 are
  re-counted, and the reading, expected to be none, goes in the report.
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition: `python3 scripts/check-frontend-boundaries.py` exits 0 with the
two exemptions gone, and `check-mock-seeds.py` exits 0. STOP D if a feature still needs an engine
helper that no component replaces.

## Commit

`refactor(maquette-l13): settings read the served catalogue and the engine's drawing bridge dies`

## Amendment — 2026-09-13, ruling 57 (the steward, on the implementer's STOP D re-take)

**VOID in this file**: « The React-side support dies here, because its last reader is converted », with its
two sub-bullets; « Guard exemptions lose their subject in this commit »; the gate's « with the two exemptions
gone ». Measured at the opening of a·16 on `9c083a9b7`:

- `engine/engine-shape.ts`: 40 `toEngineShape` call sites in 13 files, 23 families still projected
  (`grep -rhoE 'toEngineShape(Entry)?<[^>]*>\("[A-Z_]+"' --include='*.ts' --include='*.tsx' frontend/maquette/design/src | sort | uniq -c`).
  No surface phase switched its components to the contract's names, and `LIBRARY`/`INCOMPLETE` are b·10-bis's.
- `window.__referentiel`: 40 product files read about 22 members — `render` (b·7), `addVerb` (b·5),
  `INCOMPLETE`/`stFraction` (b·10-bis), the settings field verbs `SETTINGS_STATE`, `changeSetting`, `settingId`,
  `typedValue`, `rawValue`, `changedFiles`, `fileName` (b·1), and interface constants the engine holds. The three
  readers this file named were not the list: `app/history-bridge.ts` reads it zero times.
- `lib/engine-drawing.ts`: 24 importers. `app/engine-redraw.ts` exists to call `__referentiel.render`;
  `app/engine-data.ts` prefetches through `toEngineShape`.
- The seam re-count: 2 `dangerouslySetInnerHTML` sites (`ui/icon.tsx`, `ui/markup.tsx`); the other four
  grep lines are comments.

**WHERE IT WENT: b·11**, with `legacy.js`, its last publisher — `engine/engine-shape.ts` and its test,
`lib/engine-drawing.ts`, `window.__referentiel` with `app/reference.d.ts` and the `*Reference` slices,
`app/engine-data.ts`, `app/engine-redraw.ts`, the `FAN_IN_EXEMPT` and `OUTSIDE_IMPORTS_ALLOWED` engine entries,
and the reference-slice arm of `scripts/check-frontend-boundaries.py`, whose `text.index("window.__referentiel = {")`
raises the day the object goes.

**PLAN GAP, for the steward's L13b brief**: b·11 needs HOMES for the interface constants the engine holds and
nothing else holds today — `icons` (27 sites; `app/icons.ts` exists, and no feature imports an `app/` module but
`dialog-host`), `EP_LABEL`, `TODAY`, `REASON_LABEL`, `REASON_DETAIL`, `REASON_TONE`, `ST_TONE`, `stLabel`,
`MAINT_TOPICS`, `SERVICES_PANNE`, `AUDIOS`, `RESOLUTIONS`.

**What a·16 lands**: `allSettings` is gone — the page reads `flattenSettings` over its query's data, the engine's
field verbs read `heldSettings()` (`features/settings/queries.ts`, the same function over the cache), and the
named field states read the seed the served read answers from (`window.__mocks.settings()`). `SETTINGS` dies;
`resetSettings` stays (b·1's). `readonly` is a variant of `panelField`, and it carries the note's zero margin
(`[&_.rulenote]:m-0`), measured: without it the oracle diverged on `settings-field-structure`,
`shell/sheet-content` 14 px taller.

