# Phase 08 — Médiathèque — the card

The media card and its cross-reference: the largest single section of the stylesheet, the poster anatomy, the chip, the reason line, the annotations.

## Why here, and what must survive it

**§12's engraved composition is the contract here**: line 1 is the title alone across the full width, line 2 is the numeric progress then the state, and there is no type label because the active tab already carries it. A card that puts anything on the title's line is non-conforming — so this phase's rule reads the composition, not the class names. And « the reason NEVER truncates » is a layout promise the conversion must keep: the card's own comment says so.

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `card` | 57 | 46 |
| `crossref` | 3 | 1 |
| **total** | **60** | **47** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P08'])"`</sub>

The classes this phase owns: `.act`, `.actions`, `.blocked`, `.cadence`, `.cannotations`, `.caption`, `.card`, `.cbody`, `.ccol`, `.cfoot`, `.chip`, `.cmeta`, `.cov`, `.creason`, `.crossref`, `.csub`, `.ctitle`, `.ctop`, `.d`, `.danger`, `.deck`, `.dlabel`, `.done`, `.dragging`, `.folder`, `.frac`, `.freshtag`, `.info`, `.l`, `.now`, `.owned`, `.pause`, `.pfall`, `.poster`, `.remove`, `.resume`, `.right`, `.side`, `.solid`, `.st`, `.strip`, `.success`, `.swipe`, `.tile`, `.tilebadge`, `.waiting`, `.warning`.

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
