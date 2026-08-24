# Phase 14 — Configuration — the panel and its eight field kinds

The settings rows, the panel that opens on top of them, the eight field kinds, the modified marker and the save bar.

## Why here, and what must survive it

A settings row is a LIST ROW, not a form field — the control lives in the panel that opens over it, deliberately, because a screen of live inputs on a phone is a screen where every scroll risks changing something. The eight field kinds are eight named states with recorded oracle measurements; each converts as a variant of one field component, and the eight states are the proof. `.loginfield input` reads 16px for the same reason `.search input` does (D-L06-6), and that is not a style choice: below it, iOS zooms a focused field.

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `settings` | 34 | 25 |
| **total** | **34** | **25** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P14'])"`</sub>

The classes this phase owns: `.active`, `.field`, `.fieldinput`, `.fieldknob`, `.fieldlabel`, `.fieldtoggle`, `.fieldunit`, `.ladd`, `.list`, `.litem`, `.lremove`, `.modified`, `.mono`, `.readonly`, `.rf`, `.rl`, `.rn`, `.rs`, `.rt`, `.rulenote`, `.rv`, `.savebar`, `.settingrow`, `.sn`, `.topic`.

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
