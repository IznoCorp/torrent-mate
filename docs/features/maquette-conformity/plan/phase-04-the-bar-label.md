# Phase 4 — The bottom bar's label cut at 320 px (a responsive defect, owned by this train)

**Found 2026-09-29** by R-conformity-a's first full pass: `cut · shell/tab-bar`, box **[86, 154]**, at **320 px**
on every state — a label of the bottom bar ellipsised. Owner: this train, the orchestrator's ruling of 2026-09-29.
**Kind: defect.**

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `grep -n "tabBarLabel\|tabBarButton" frontend/maquette/design/src/ui/variants/frame.ts` →
  `tabBarLabel` **:128** (`overflow-hidden text-ellipsis whitespace-nowrap max-w-full`), `tabBarButton` **:111**
  (`flex-1 basis-0`, `text-3`); `grep -cv '^\s*$' frontend/maquette/design/src/ui/variants/frame.ts` → **397 / 400**
  (STOP D near: a class edit only). Which label, and by how much, is read at the opening.
- **Points ≈ 7.** The repair — the label fits at 320 px by the scale's own steps, never by a smaller-than-scale
  size (≈ 3 lines, 1); `BUGS.md` line per order 57 (2); the red read before, green after (1); the family: every
  bar label at 320 / 360 / 369 (1); mutation (1); the RESUME (1).

## Red today

R-conformity-a: `cut · shell/tab-bar` at 320 px, every state.

## Mutation

Revert the repair → falls at 320 px by name.

## Oracle: states that diverge, declared by name

None at 390 px, where the oracle measures; a divergence there is STOP A.

## Commit

`fix(maquette-conformity): the bottom bar's labels read whole at 320 px`
