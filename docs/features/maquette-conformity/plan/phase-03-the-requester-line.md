# Phase 3 — The requester line drawn at zero width (a defect, owned by this train)

**Found 2026-09-29** by R-conformity-a's first full pass (254 s, 161 states × 7 widths): `cut · card/requester`, box
**[107, 107]** — zero wide, its text invisible — at EVERY width, 320 to 1280 px, on `acq-card-blocked`,
`acq-card-deferred-ratio`, `acq-card-requester`, `acq-card-follow-error`, `acq-card-no-identity`,
`acq-card-plex-disagrees` and more (the complete list from the second pass's `TM_RESPONSIVE_REPORT`). Owner: this
train, the orchestrator's ruling of 2026-09-29. **Kind: defect** — a behaviour repaired, not a conversion.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n 'card/requester' -g '*.ts' frontend/maquette/design/src` → `ui/card-markup.ts:141`, a
  `cardCaption` span placed beside the single foot in the card's `originRow` when the card has one action and a
  requester (`shared`, `:138`), else inside the body; `grep -n "originRow" frontend/maquette/design/src/features/acquisition/variants.ts`
  → the row's classes (`truncate`, report B.5 R11). The mechanism is READ at the opening in the browser (class
  rule), never guessed: which box squeezes the caption to zero.
- **Points ≈ 8.** The repair (≈ 6 lines, 2); `BUGS.md` line per order 57 — escaped from / why / family repaired by (2);
  the regression hold: R-conformity-a's `card/requester` falls on the tree before the repair (read RED, logged), goes
  green after (1); the family read — every other `cardCaption` in a shared row (1); the RESUME (1); mutation (1).

## Red today

R-conformity-a: `cut · card/requester` at every width on the states above.

## Mutation

Revert the repair → R-conformity-a falls on `acq-card-requester` by name.

## Oracle: states that diverge, declared by name

Every state drawing a card with a requester (built by script) — the requester now visible, accepted by name.

## Commit

`fix(maquette-conformity): the requester line is drawn, not squeezed to nothing`
