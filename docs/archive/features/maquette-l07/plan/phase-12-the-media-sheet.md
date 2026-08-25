# Phase 12 — Média — the sheet, the matrix, the popover

The media sheet as ONE template for every medium, its melting hero header, the season matrix of the follow detail, and the air-date popover on an episode cell.

## Why here, and what must survive it

The second-largest scope. « ONE template for every medium » is the decision the conversion has to preserve: a variant per medium would be a redesign. The expand affordance must stay VISIBLE — a 9px chevron went unnoticed once and was made bigger on purpose. The hero's gradient and the `heroin` keyframe are in the base layer since phase 2, so `animation` stays byte-identical.

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `media-sheet` | 48 | 25 |
| `season-matrix` | 26 | 19 |
| `airdate-popover` | 5 | 3 |
| **total** | **79** | **40** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P12'])"`</sub>

The classes this phase owns: `.acquiring`, `.announced`, `.ca`, `.cast`, `.done`, `.ed`, `.en`, `.ep`, `.epdot`, `.eppop`, `.eprow`, `.eps`, `.et`, `.hero`, `.herobg`, `.herowrap`, `.hm`, `.hn`, `.ht`, `.in_library`, `.legend`, `.mediaadd`, `.miss`, `.missing`, `.noposter`, `.pending`, `.pl`, `.season`, `.sfr`, `.sheetposter`, `.sw-info`, `.sw-muted`, `.sw-success`, `.sw-upcoming`, `.sw-waiting`, `.sw-warning`, `.to_grab`, `.trailer`, `.tsrc`, `.unverified`.

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
