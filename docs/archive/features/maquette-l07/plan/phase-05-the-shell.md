# Phase 05 — The shell

The frame every page sits in: top bar and status dot, scrollport, pull-to-refresh, the floating action button, the bottom tab bar, the toast, the scrim and the navigation drawer.

## Why here, and what must survive it

It converts first because every page composes it, and because it is the one surface whose geometry other rules already pin — `--tm-bottom-bar-h` is published by the shell (L06's D-L06-4), and R84 holds it to exactly one publisher. The bar's rendered height must still equal the published value at the close of this phase; that is R84's own hold, and it is the check that a padding conversion did not move the bar by a pixel.

**And one declaration in this scope is read by a phase nine steps away.** `.port` carries
`container: port / inline-size` — it ESTABLISHES the container that the grid's three
`@container port` queries ask (phase 9). Drop it while converting the scrollport and the gallery
silently falls back to one column at every width, in a phase whose diff contains no grid at all.
Invariant 12 — a component asks the width it HAS — rests on this single line.
<sub>`grep -n 'container' frontend/maquette/design/refonte.html` → the declaration at 533, the three queries at 1345, 1351, 1357.</sub>

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `shell-chrome` | 17 | 10 |
| `scrollport` | 1 | 1 |
| `pull-to-refresh` | 6 | 4 |
| `fab` | 3 | 2 |
| `bottom-bar` | 10 | 5 |
| `toast` | 4 | 2 |
| `drawer` | 14 | 10 |
| **total** | **55** | **34** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P05'])"`</sub>

The classes this phase owns: `.armed`, `.avatar`, `.bottombar`, `.brand`, `.burger`, `.chip`, `.count`, `.dh`, `.drawer`, `.fab`, `.grp`, `.ic`, `.lb`, `.loading`, `.mk`, `.navbadge`, `.open`, `.port`, `.ps-dot`, `.ps-dot__d`, `.ps-dot__label`, `.ptr`, `.sect`, `.selecting`, `.show`, `.sp`, `.spin`, `.toast`, `.topbar`, `.vc`, `.ver`, `.vt`, `.vv`, `.wm`.

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
