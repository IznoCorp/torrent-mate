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
