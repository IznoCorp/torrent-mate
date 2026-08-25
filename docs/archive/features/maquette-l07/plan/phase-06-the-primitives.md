# Phase 06 — The shared primitives, and the first typed variants

`ui/`: the body and section rhythm, the screen layer, the bottom sheet, the ONE action-button system, the form controls, the dialog, the empty and surface states, and the skeletons.

## Why here, and what must survive it

This is the phase that decides the API the rest of the wave writes against, and it is the largest single scope of the lot. The action-button system is the one to get right: the stylesheet already calls it « ONE ACTION-BUTTON SYSTEM », so the variants are being read off an existing decision rather than invented. `ui/` never imports a feature (invariant 7), and that is checkable here for the first time.

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `body-sections` | 12 | 12 |
| `screens` | 6 | 5 |
| `bottom-sheet` | 26 | 22 |
| `action-buttons` | 4 | 3 |
| `form-controls` | 13 | 8 |
| `dialog` | 16 | 9 |
| `empty-note` | 2 | 1 |
| `surface-states` | 4 | 2 |
| `skeletons` | 16 | 8 |
| **total** | **99** | **66** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P06'])"`</sub>

The classes this phase owns: `.addrow`, `.avatar`, `.big`, `.body`, `.btnprimary`, `.check`, `.danger`, `.dlg`, `.dlgacts`, `.dlgbtn`, `.dragging`, `.dryrun`, `.empty`, `.endmark`, `.fback`, `.ghost`, `.grid`, `.info`, `.k`, `.lb`, `.loaderr`, `.loadfoot`, `.manifest`, `.mark`, `.mediaadd`, `.neutral`, `.noinfo`, `.open`, `.opt`, `.optkind`, `.optlist`, `.pip`, `.port`, `.primary`, `.qhint`, `.quota`, `.radio`, `.row`, `.rulenote`, `.sact`, `.screen`, `.screenbar`, `.scrim`, `.sec`, `.sechead`, `.secondary`, `.sheet`, `.sheetacts`, `.sheetgrab`, `.sheethead`, `.sheetid`, `.sheetin`, `.sheetmeta`, `.sheetsub`, `.sheettitle`, `.sk`, `.skcard`, `.soon`, `.success`, `.surferr`, `.t`, `.tile`, `.waiting`, `.warnbox`, `.warning`, `.withposter`.

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
