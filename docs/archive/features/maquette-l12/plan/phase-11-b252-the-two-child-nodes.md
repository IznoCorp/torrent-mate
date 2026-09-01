# Phase 11 — B-252's two child nodes

**Kind: RULE ONLY.** No source change. It closes **B-252**, placed on L12 by the steward on
2026-08-30.

## Why these two need rules at all

**D8's descendants clause.** A region resolves to the nodes its selector names, and the nineteen
properties are read on **those** nodes — never on a child. So a defect on a child node is invisible
to the oracle **by contract, correctly**. The remedy is not to widen the oracle: *a child node that
carries a function is covered by a named rule*, exactly as a pseudo-element is.

**Both were found by eye in #528's adversarial review and replayed by the steward with the oracle
green over both** — 167 divergences before, 167 after, all on `shell/sheet-content`, in both cases.
That is the measurement that makes this phase necessary rather than tidy.

## The two rules

1. The dialog's paragraph carries its **`color`** — read under **both themes**. (Its defect:
   `dialogParagraph` stripped of its colour.)
2. The danger action's **contrast** under `data-theme="light"`. (Its defect: `selectionAction`
   carrying `bg-transparent` in its base — white on white under the light theme, contrast **1.00**.)

**Both are read on the CHILD node**, which is the entire point. A rule that resolves the region's
root and reads there reproduces the oracle's blindness and would be green over both defects — the
B-085 question asked in advance.

## Mutation

The steward's own replay commands are the mutations, and they are already known to leave the oracle
green:

```
sed -i '' 's/ text-muted-foreground"/"/' frontend/maquette/design/src/ui/variants/frame.ts
```

The paragraph rule must fall on it. The equivalent edit re-introducing `bg-transparent` on the
danger action must fell the contrast rule under the light theme **and not under the dark one**.
Restore both.

## Done when

Both rules exist and bit; B-252 closes in `BUGS.md`; the oracle is unchanged — **and that is the
expected result, not a disappointment**: it is what D8's clause predicts.
