# Phase 09 — Médiathèque — tiles, selection, filters

The view tabs, the filter zone, the grid tiles, and the selection mode that is invisible at rest.

## Why here, and what must survive it

The selection surface is where D-L07-9's third kind concentrates: the engine toggles `selecting` and `sel` on nodes components render. Each of those becomes a `data-*` variant, and the engine's write moves in the same step. `.grid` carries the maquette's only container queries — three of them, `@container port` at 460, 620 and 820px. The container they ask is established by `.port`, which phase 5 converted: this phase must confirm that line survived before trusting a column count, and must not quietly turn any of the three into a media query. A media query answers for the window, so a 390px frame on a 1280px desktop is told it has room for six columns it does not have — invariant 12, and a trap the architecture file names against this very lot.

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `view-tabs` | 7 | 4 |
| `filter-zone` | 23 | 10 |
| `grid-tiles` | 13 | 6 |
| `grid-selection` | 16 | 11 |
| **total** | **59** | **28** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P09'])"`</sub>

The classes this phase owns: `.c`, `.countline`, `.csub`, `.danger`, `.filters`, `.fr`, `.grid`, `.linkbtn`, `.more`, `.n`, `.nm`, `.off`, `.p`, `.pill`, `.pillbar`, `.pillscroll`, `.poster`, `.rowtxt`, `.search`, `.searchclear`, `.seg`, `.sel`, `.selbar`, `.selrow`, `.tile`, `.viewtabs`, `.vsw`, `.vswwrap`.

## The three-way sort comes first (D-L07-9)

Before a utility is written, every class above is sorted: **drawn** by a component (converts),
**engine-drawn** (moves to the residue, untouched), **engine-toggled** (the look becomes a
`data-*` variant and the engine's write moves in the same step). The third kind is the one with no
natural warning — the build passes, the component renders, and the state simply stops painting.

## The recipe

1. Sort the classes three ways.
2. Write the CVA variant table **before** placing a utility — a variant discovered while
   converting is a variant nobody designed.
3. Convert and delete in the SAME commit. Leaving the old rules behind means both sheets are in
   the document and the oracle cannot tell which one painted.
4. Read every shorthand twice: `padding: 8px 12px` → `px-6 py-4`, and a dropped side is a defect
   the oracle sees as a changed rectangle. This is the single most valuable thing it does here.
5. Re-run the named states this surface owns, by hand, at 390×844.

## Gates

ACC-01, ACC-02 (zero divergence, or a divergence read and named in `ACCEPTED-DIVERGENCES.md`),
ACC-03. Plus the harness rules that drive this surface, re-run and unchanged.
