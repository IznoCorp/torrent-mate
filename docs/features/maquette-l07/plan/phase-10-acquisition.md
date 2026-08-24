# Phase 10 — Acquisition — the deck and the follows

The Découvrir deck: one card at a time with the next stacked behind, the swipe feedback under the thumb, the suggestion card and the poster format.

## Why here, and what must survive it

The deck's height is MEASURED from the scrollport rather than derived, and the swipe verb appears on the side the card is going. Both are behaviours the conversion must not flatten into a static rule. `deck.py`, `drag.py` and `touch.py` all drive this surface; a synthetic event is not a finger, so the gesture holds are the ones to re-run by hand.

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `discover-deck` | 24 | 18 |
| **total** | **24** | **18** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P10'])"`</sub>

The classes this phase owns: `.body`, `.cap`, `.crating`, `.dcard`, `.deck`, `.deckbody`, `.dhint`, `.dragging`, `.gone`, `.l`, `.m`, `.out`, `.p`, `.r`, `.sugback`, `.sugwrap`, `.t`, `.why`.

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
