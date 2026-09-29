# Phase 6 — A card's title is never cut (§ 12, a defect owned by this train)

**Ruled 2026-09-29** (the orchestrator, on the constitution): `product-intent.md` § 12 already decides it — « Rien
d'essentiel n'est tronqué. Un titre coupé … n'est pas un titre : c'est une devinette. Si la place manque, c'est la
mise en page qui change », and the title takes the whole first line. **Kind: defect, § 12** — the visible change
(titles wrap, cards grow) is accepted BY NAME. Report B.5 R2.

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `grep -n "cardTitle\|cardSubtitle" frontend/maquette/design/src/ui/variants/card.ts` → `cardTitle`
  (`whitespace-nowrap overflow-hidden text-ellipsis`, **:37**), `cardSubtitle` (**:41**); R-conformity-a's first
  full pass → `cut · card/title` and `cut · card/subtitle` on the Acquisition cards from 320 px (the complete list
  from the second pass's `TM_RESPONSIVE_REPORT`); `rg -n "pitch" -g '*.ts*' frontend/maquette/design/src/ui` → the
  virtual window's row pitch (`ui/virtual-rows.tsx`, `ui/window-geometry.ts`), which a taller card moves.
- **Points ≈ 12.** The title and subtitle wrap (a class edit, 1); the card's other lines keep their place under the
  title (≈ 6 lines, 2); the virtual list's pitch measured, not assumed, for a wrapped card (≈ 10 lines, 3);
  `BUGS.md` line per order 57 (2); the owed entries removed, R-conformity-a green on them (1); the family,
  ruled into this phase by the orchestrator — `tileTitle` (R8) and `castCaption` (R9) wrap too (≈ 4 lines, 1);
  mutation (1); the RESUME (1). Above 15 at the opening: cut into 7a (the card) and 7b (tile, cast), told.
- **Readers.** `virtual.py`, `scroll_keeps_place.py`, `cards.py`, `one_card_per_medium.py` — the pitch and the
  card's geometry; re-read at the opening.

## Red today

R-conformity-a: `cut · card/title`, `cut · card/subtitle` (owed to this phase until it lands).

## Mutation

Restore `whitespace-nowrap` on `cardTitle` → R-conformity-a falls by name.

## Oracle: states that diverge, declared by name

Every state drawing a media card whose title wraps at 390 px (built by script) — accepted by name.

## Commit

`fix(maquette-conformity): a card's title takes its whole line and wraps — never a riddle`
