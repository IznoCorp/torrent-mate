# Phase 3 — The hamburger invisible on iPhone, light and dark (the operator's defect)

**Reported 2026-09-29** (rulings file § « TWO DEFECTS », defect A): on an iPhone the hamburger does not show, in
light nor in dark. **Kind: defect.** The WebKit pass of phase 2 is its oracle and must read it RED first; the
mechanism is READ in WebKit, never guessed.

**Opening measure:**

- **Commands.** Phase 2's WebKit red on `shell/menu` (light and dark), its box, its computed `display` /
  `visibility` / `color` / the icon's `stroke` and `fill`, `elementFromPoint` at its centre — logged in the RESUME
  before a line of the product moves; `rg -n 'shell/menu' -g '*.tsx' frontend/maquette/design/src/app` → where it is
  drawn.
- **Points ≈ 8.** The repair (≈ 6 lines, 2); `BUGS.md` per order 57 — escaped from « aucune porte ne lit le moteur de
  l'iPhone », family « le moteur de l'appareil ≠ celui du harnais », repaired by the WebKit pass (2); the family read —
  every frame control under WebKit (1); the red before, green after (1); mutation (1); the RESUME (1).

## Red today

Phase 2's visibility hold on `shell/menu`, WebKit, light and dark.

## Mutation

Revert the repair → the WebKit visibility hold falls by name.

## Oracle: states that diverge, declared by name

None expected in Chromium at 390 px (the oracle's engine); a divergence there is STOP A.

## Commit

`fix(maquette-conformity): the hamburger is seen on an iPhone, in both themes`
