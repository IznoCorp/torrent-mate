# Phase 2 — The panel splits in three

**Arbitrated by the operator on 2026-08-22** (DESIGN § D-L04-3). It comes before the `data.ts` cut
because it REMOVES work from it: 8 of the 28 shared `Reference` members are shared only because
one file holds two domains.

## What is in the file today

`components/panel.tsx`, **628 non-blank lines**, holding three things that change for three
different reasons:

| Piece                                                                                                                  | Reads                                                               | Changes when                         |
| ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------ |
| `RichText`, `Chip`, `Poster`, `ActionButton`, `ActionsBlock`, `NoteBlock`, `FactsBlock`, `PanelContent`, `refuseBlock` | nothing domain-specific                                             | the panel's own presentation changes |
| `SeasonDetails`, `SeasonsBlock`, `epState`, `catalogFor`, `EP_ORDER`, `EP_SWATCH`                                      | `seasonsOf`, `ownedFor`, `sheetFor`, `EP_LABEL`, `POSTERS`, `TODAY` | a season or an episode changes       |
| `FieldBlock`, `fileName`                                                                                               | `Setting`, `settingLabel`, `unitOf`, `settingId`                    | a setting changes                    |

Five surfaces open panels through it.

## The change

```
ui/panel/descriptor.ts     the PanelDescriptor and PanelBlock types   (phase 1 put it here)
ui/panel/index.tsx         PanelContent, the five generic blocks, refuseBlock, the registry
features/acquisition/panel-seasons.tsx   SeasonsBlock + epState + catalogFor, registering "saisons"
features/settings/panel-field.tsx        FieldBlock + fileName, registering "field"
```

`ui/` imports no feature. Each domain block **registers its kind** with the renderer; `BlockView`
dispatches through the registry instead of a closed switch.

## What must be proved, because an indirection can fail silently

A registry that is not filled draws nothing — the exact failure shape this architecture exists to
kill. Two things hold it:

1. **`refuseBlock` keeps its existing job.** A block kind the registry does not know **throws**,
   where the producer wrote it. It never draws nothing. This is unchanged behaviour, and it is why
   the registry is safe: the failure is loud and local.
2. **A rule holds the registration** — every kind a descriptor may declare is registered before
   the first panel opens. Registration happens at module evaluation of the feature that owns the
   block, and the boot order that guarantees it is the same one `shell.tsx` already documents.

**Mutation for the rule**: remove one registration, confirm the rule falls and NAMES the missing
kind, restore. A rule that reported « a panel is empty » without naming the kind would not be
worth writing.

## What this phase does NOT change

- **No block's markup, no class, no attribute.** The blocks move; they are not rewritten. The
  oracle is the proof, and it reads rectangles and computed style — a rewritten block would show.
- **No descriptor shape.** A producer calls `window.__panel.open(descriptor)` exactly as before;
  the five declared kinds stay five.
- **`components/sheet.tsx`** stays a separate component, and moves in phase 4 with the rest.

## Proof

- `python3 scripts/check-frontend-boundaries.py --arm layering` reports 0 imports from `ui/` into
  `features/`.
- The panel rule exits 0, and is seen RED with one registration removed.
- `npm run typecheck` exits 0.
- **The oracle reports 0 divergence** — a split that moved no pixel.

## Trap met here

**A rule can certify the defect.** The panel rule (R56) states « exactly one constructor, every
declared block draws, an undeclared one is refused ». Extending it to the registry must assert the
behaviour that is WANTED — every declared kind registered — not merely describe the registry that
now exists.
