# Phase 7 — The drawer

**Kind** conversion. **Parts** 6 and 7.

## What lands

`ui/drawer.tsx` (the primitive: the `<aside id="drawer">`, its transition, its `data-open`) and
`app/drawer.tsx` (the content: the brand, `app/navigation.ts`'s three groups with their badges,
the appearance control, and the served identity from `lib/served-identity.ts`).

It **registers with the ladder** through `app/layer-registry.ts` — a name, an `isOpen`, a
`close(pop)` — and the engine's `onEngineBack` walks the registration instead of testing
`#drawer.classList.contains("open")`. **The handler does not move**: L13 takes it.

`app/drawer-gesture.ts` (E-002) stays a frame gesture and moves with the drawer: it attaches to the
same `#drawer` and keeps calling `window.__closeLayers`.

`index.html`'s empty `<aside id="drawer">` is removed in this commit.

## What the engine loses

`openDrawer`, `closeDrawer`, `servedIdentityBlock`, and the `data-drawer` / `data-navgo` verbs'
markup half. The verbs themselves are `app/`'s (Part 12 says so by name) and become the component's
own handlers.

## The rules

- **R65 must still bite, unchanged.** `harness/drawer.py` holds three defects at once — an entry
  that leads nowhere, an entry naming an id no page carries, and the current entry painted in
  invisible ink. It is re-run and its mutations re-exercised: this is the phase most likely to
  break it, and a rule that used to bite and now passes vacuously is the failure this repository
  counts.
- A new hold: the drawer is **registered**, and Back closes it through the registration. Its
  mutation: unregister it and confirm the hold falls naming the missing rung — not « Back did
  nothing », which a dead handler would also say.

## Traps

- The contrast hold measures colours as PAINTED, through a canvas. A Tailwind utility resolving to
  the same `oklch()` is what keeps it green; a hand-written hex would too, and would be wrong.
- `app/focus.ts` watches `data-open` on the drawer and needs nothing from the engine — but it reads
  the attribute, so the component must emit `data-open` and not only a class.
