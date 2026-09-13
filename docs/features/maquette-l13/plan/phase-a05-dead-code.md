# Phase a·5 — What nobody reaches

A CONVERSION by deletion: `#screen`, its readers and the mount-node placement that depends on it,
four dead delegation branches, three dead helpers, `__seamsInstalledProbe`, and the dead `quota`
rule (DESIGN § 4.5; § 3, rows 13–14).

## The proof FIRST

- **The oracle**: zero divergence. Document order is unchanged, so the paint order `bridge.py`
  relies on is unchanged too.
- **Hold counts**: `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST.
- **Harness readers of `#screen`, each RE-AIMED to `[data-part="screen"][data-open]`** (Q4). Each
  keeps its count, said in its docstring.
  - These would throw on a missing node: `bridge.py:278`, `audit.py:63,303`, `audit2.py:50`,
    `back.py:61`, `ident.py:36`, `dest.py:35`, `states.py:31`.
  - These are selector-only: `scroll.py:20`, `audit2.py:262,305,334`.
- **`bridge.py:278`, said out loud.** Its hold « the legacy mediaSheet is gone » passes trivially
  today, because nothing ever sets `data-open` on `#screen`. Its docstring and the commit body say
  it was vacuous, and say what the re-aimed hold reads now. It is not kept green in silence.
- **The `.screen.open` CSS rule is NOT dead** (DESIGN § 2.6). It makes the five React screens
  visible. It stays, and converts in a·7.

## The move

- **`#screen` goes**:
  - the node (`index.html:520`) and its paragraph at the head of that file;
  - its rung in `app/layers.ts` (new file, a·3), registered in a·3;
  - `closeScreen`, `screenStack` and `window.__close`. The comments naming them in
    `features/acquisition/add-screen.tsx` and `app/scroll-restoration.ts` are re-taken and
    rewritten so they name no dead symbol.
- **The mount-node placement** in `app/shell.tsx` becomes
  `device.insertBefore(mountNode, <the node that followed #screen>)`.
- **Dead delegation branches** (DESIGN § 2.3): `dismiss`, `sug`, the generic `sheet` →
  `openDetailSheet`, and the second `resolve`.
- **Dead helpers**: `sheetSeasonsHTML`, `epState` and `seasonsOf`, with `__seamsInstalledProbe`.
  `features/media/reference.ts` still types `seasonsOf`, and `features/media/panel-seasons.tsx`
  derives a type from it. The phase re-takes both and replaces them with the type they name, and
  the change is type-only.
- **B-232's other half**: the page-render `else` branch of `render()`. The phase re-takes it: if it
  is still unreachable, it goes here, because B-232 closes in this phase.
- **`quota`**: its rule leaves `styles/legacy.css`. The residue ceiling in
  `frontend/maquette/legacy-css-residue.json` is re-recorded after the shrink, in the same commit.
- **The size ledger.** `legacy.js` only subtracts, and `scripts/frontend_size_ledger.py` is
  re-recorded DOWNWARD in the same commit.

## Gate

Per INDEX « Gates ». In addition, `python3 scripts/check-legacy-css-residue.py` exits 0 against the
lowered ceiling. B-232 is closable, and the reading goes in the report.

## Commit

`refactor(maquette-l13): the dead screen layer and the code nobody reaches are deleted`
