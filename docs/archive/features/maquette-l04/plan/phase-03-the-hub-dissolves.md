# Phase 3 — `data.ts` stops existing

**Arbitrated by the operator on 2026-08-22** (DESIGN § D-L04-4). The architecture file's corollary
is the instruction: « `data.ts` is not slimmed, it stops existing. »

## What the file holds, measured

**558 non-blank lines, 17 importers of 25 modules.** Three things with nothing in common:

| Part                                                                                    | Size                        | Goes to                                              |
| --------------------------------------------------------------------------------------- | --------------------------- | ---------------------------------------------------- |
| Store access — `useStoreContent`, `useUiState`, `useWorld`, `writeUiState`, `subscribe` | ~25 lines                   | `lib/store-access.ts` — domain-free, renders nothing |
| ~30 domain type declarations — `Follow`, `LibraryRow`, `Setting`, `PendingDecision`, …  | ~190 lines                  | their feature's `reference.ts`, beside the members that name them                           |
| `type Reference` + `useReference()` + the `Window` declaration                          | ~340 lines, **108 members** | cut below                                            |

## How the 108 members are cut

Measured by matching each member name over every module WITH COMMENTS STRIPPED, and
grouping modules by feature. The stripping is not a detail: a first reader counted
`actionResolve`, `actionLeave` and `secHTML` as read because they are NAMED in comments,
and putting three live-looking members into a slice nobody reads is the small end of the
same mistake that would have deleted a used one. Two readers were run and crossed.

| Bucket                                                             | Count                                                                                                                                                                                                        | Destination                                                                                                           |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Read by exactly **one** feature                                    | **73**                                                                                                                                                                                                       | that feature's own slice + accessor                                                                                   |
| Read by **no component at all** (engine-only)                      | **10** — `PENDING_DECISIONS`, `RECENT`, `SYNOPSIS`, `actionTake`, `actionResolve`, `actionLeave`, `factsListHTML`, `secHTML`, `skelCards`, `surfErr`                                                                                                     | **deleted from the type**                                                                                             |
| Shared, and **not domain** — drawing plumbing the engine publishes | `escapeHtml`, `svgIcon`, `icons`, `emptyInner`, `surfErrInner`, `skelCardsInner`, `factRowsHTML`, `cardHTML`, `tileHTML`, `secInner`, `render`, `toast`, `initials`, `baseTitle`, `posterBox`, `paintSelBar` | `lib/engine-drawing.ts` — returns strings, knows no domain, exempt from the fan-in ceiling by the guard's own wording |
| Shared with the panel, **dissolved by phase 2**                    | 8 — `seasonsOf`, `ownedFor`, `sheetFor`, `EP_LABEL`, `POSTERS`, `TODAY`, `settingId`, `fileName`                                                                                                             | the feature that took the block                                                                                       |
| Genuinely shared between two domains                               | the remainder                                                                                                                                                                                                | **arbitrated one by one, and each arbitration recorded in this file as the phase runs**                               |

**Deleting the 10 engine-only members is not a cleanup taken in passing.** They are members of a
TYPE describing a runtime object; the object keeps publishing them, and the engine keeps using
them. Removing them from the type removes a claim no component makes — and `tsc` proves the
removal is safe, because a reading site would fail.

## How the global stays typed with no hub

`window.__referentiel` is ONE runtime object, so its type is declared once — as the
**intersection of the feature slices**, in an ambient declaration under `app/`, importing each
slice with `import type` only.

```
app/reference.d.ts       declare global { Window { __referentiel: LibrarySlice & AcquisitionSlice & … } }
features/library/reference.ts    export const useLibraryReference = (): LibrarySlice => window.__referentiel
```

Three properties make this work and each one is load-bearing:

1. **A feature reads its own slice and imports nothing** — the ambient type needs no import at the
   reading site, so no shared value module exists to become the next hub.
2. **`app/` may import features.** Layering forbids it of `ui/` and `lib/`, not of `app/` — the
   router already does it.
3. **A type-only edge creates no runtime dependency**, so the cycle arm does not see one.

## Proof

- `test ! -f frontend/maquette/design/src/data.ts`.
- The duplicate-import arm reports **0** — the 6 files that imported `data` twice go with it.
- `npm run typecheck` exits 0. **This is the criterion that makes the cut a proof rather than a
  reading**: a member dropped by mistake fails at its reading site.
- **The oracle reports 0 divergence.**

## Traps met here

**A rule that greps one file greps the wrong thing.** Several tools name `data.ts` or read
`design/src` as a whole. Before the file is deleted, every reader is enumerated and moved in the
same commit; a reader left naming a deleted path must RAISE, not pass quietly — which is already
`common.py`'s behaviour for a declared source that no longer exists, and is the shape to keep.

**Renaming needs a parser, not a regex.** The same short member name (`t`, `k`, `render`) means
different things in different scopes. Every rename goes through `scripts/rename-identifiers.py`,
and the diff is re-read afterwards — the tool is not the proof.
