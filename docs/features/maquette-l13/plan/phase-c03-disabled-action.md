# Phase c·3 — A disabled action looks disabled

**Opening measure (2026-09-15, on `6839dd913`):**

- **Commands.** `grep -n panelAction design/src/ui/variants/controls.ts` → the `actionButton` cva
  (`kind: { panelAction: "sact border", … }`, three `tone` compounds at `kind: "panelAction"`);
  `design/src/ui/panel/index.tsx:85` applies `disabled={action.desactive || undefined}`. No tsc
  probe: no type changes. `grep -ln panelAction harness/*.py` → 0 files: no rule reads this variant
  today. `grep -n B-339 BUGS.md` → `open`, 1×.
- **Points ≈ 4.** 1 in-scope site (`controls.ts`'s `actionButton` base, the `disabled:` half) ≈ 1;
  one wholly new rule (no existing reader), its two probes (enabled vs. disabled, both themes and
  `prefers-reduced-motion`) and its mutation ≈ 3.
- **Found (2026-09-15).** `controls.ts:28`, the `actionButton` cva's OWN base string (applied to
  every `kind`, `panelAction` included), already reads `"… disabled:opacity-50"` — a disabled action
  ALREADY draws at 50% opacity, which is a property the two drawings already differ on. The phase's
  "Red today… the two drawings are identical" is true only if the new rule reads a property `opacity`
  does not touch (background, border or text colour, none of which have a `disabled:` half yet); a
  rule reading raw `opacity` would pass against the tree as it stands, before any move. The phase's
  own DESIGN choice — which property carries the "spent" reading — is unmade by this measure and is
  not for this commit to pick.
- **Landed (2026-09-15, ruling 118).** The opacity half was L20's (`60c6d9b1d`); R197, 5 holds, lands
  as the guard, s1–s3 green from the start; the spent act loses its « + »; B-339 `to confirm`.

A BEHAVIOUR change: the panel action variant that a·8 converted from `.sact` gains its `disabled:`
half, so a spent action is not drawn like an available one (DESIGN § 10, B-339).

## The proof FIRST

B-339's entry names the defect but not a rule, so the rule is written from the defect. Its label is
bound to the next free number.

- **What it drives.** Open the add screen, add a result, and open that result's panel. Its primary
  action is passed `desactive: done`.
- **What it reads**:
  1. the button is `disabled` and a tap does nothing, which is already true and stays held;
  2. its computed drawing DIFFERS from the same variant enabled, read on the properties the
     `disabled:` half declares, as two probes compared in the document the way R80 compared them;
  3. under `prefers-reduced-motion: reduce` and under both themes, reading 2 still differs.
- **Red today.** The variant has no `disabled:` half, so the two drawings are identical.
- **Mutation.** With the commit made first, `scripts/mutate.sh` removes the `disabled:` half.
  Reading 2 falls, naming the property that no longer differs.
- **Hold counts.** `python3 scripts/harness-hold-counts.py --compare`, with `failed` read FIRST and
  the new holds named.
- **The oracle may diverge ONLY on states that draw a disabled panel action**, each accepted with
  « B-339 » (D8). The phase lists them.

## The move

- **The action variant gains its disabled half.** The variant in `ui/variants/` (`ui/panel/index.tsx`
  applies it) gains a `disabled:` half that uses the palette's existing tokens, and no new colour
  literal.
- **What it covers.** It is the floor every not-available action inherits, including DOIT-4's queued
  state. So the half is written on the variant, never on one caller.
- **Invariant 10.** The variant knows « disabled », never « added ».

## Gate

Per INDEX « Gates ». In addition, B-339 closes with the rule's red reading and its mutation.

## Commit

`fix(maquette-l13): a spent panel action is drawn as disabled`
