# Phase 07 — Arrivées, and its resolution screen

The live strip: the pilot's bar with the pipeline's state and the one control it takes, the gauge, and the last run told as its nine steps.

## Why here, and what must survive it

The first page, and the first one carrying a control that WRITES. Its three states include DOIT-4's queue. `arrivals.py` holds R66 against the run `library.db` really recorded and is deliberately outside the `--contracts` tier — it runs in the full suite, on this machine.

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `live-strip` | 24 | 18 |
| **total** | **24** | **18** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P07'])"`</sub>

The classes this phase owns: `.d`, `.fblocked`, `.fclick`, `.fempty`, `.fk`, `.flux`, `.fn`, `.fr`, `.fs`, `.fw`, `.fx`, `.gauge`, `.live`, `.pacts`, `.ph`, `.pipeline`, `.pq`, `.pt`.

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
