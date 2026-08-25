# Phase 11 — Acquisition — the add screen, releases, quality

The « + » add screen with its search results and its by-id path, and the « choose another release » screen with its quality groups.

## Why here, and what must survive it

Search results are a card LIST like any other — the gap comes from the section, not from the list — so this phase reuses phase 8's card rather than re-deriving it. The « Chercher » button keeps its own width because it shares its line with the type segment: a full-width variant applied here is a visible regression the oracle will catch as a rectangle.

## Scope, from the manifest

| surface | rules | classes |
| --- | --- | --- |
| `add-screen` | 20 | 11 |
| `release-screen` | 13 | 9 |
| **total** | **33** | **20** |

<sub>`python3 -c "import json;m=json.load(open('docs/features/maquette-l07/plan/surface-manifest.json'))['surfaces'];print([k for k,v in m.items() if v['phase']=='P11'])"`</sub>

The classes this phase owns: `.addfoot`, `.addform`, `.addrow`, `.best`, `.btnprimary`, `.byid`, `.byidin`, `.kv`, `.qgroup`, `.rel`, `.rescount`, `.reslist`, `.rn`, `.rt`, `.sc`, `.segmini`, `.setting`, `.sugg`, `.switch`, `.whyoff`.

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
