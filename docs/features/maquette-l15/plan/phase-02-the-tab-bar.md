# Phase 2 — The tab bar

**Kind** conversion. **Part** 6. **Closes** B-231's cause.

## What is wrong today

`renderNav()` writes `nav.innerHTML` and `render()` calls it **unconditionally** at
`legacy.js:7868`. Every page switch and every store bump replaces the chrome's buttons with new
nodes — so a persistent chrome, the first property of `MODEL.md` § 3, is false, and focus cannot
survive a redraw (P28).

## What lands

`app/tab-bar.tsx` renders `<nav id="nav">` itself — the element, not its children — at the same id,
the same classes and the same `data-part`, as `ui/sheet.tsx` renders `#sheet`. It reads
`app/navigation.ts` (`inBar`), the store (`state.page` → `aria-current`) and each row's `badge()`.

`index.html`'s empty `<nav id="nav">` is removed **in this same commit** (D-L15-2).

`publishBarHeight()` moves out of `app/shell.tsx`'s boot and into a layout effect on this
component: the boot call queries `.bottombar` before React has drawn it, and a query that answers
nothing attaches no `ResizeObserver`. **R84's one publisher is unchanged** — `app/bar-height.ts`
stays it; only the moment it is called moves.

## What the engine loses

`renderNav`, its call in `render()`, and the `nav` capture at module evaluation.

## The rules

- **P1 — one document.** A new hold walks every named state and asserts
  `performance.getEntriesByType("navigation").length` stays 1. Cheap; contracts tier.
- **P2 — a persistent chrome.** A hold captures the tab bar's button nodes, switches page, bumps
  the store, and asserts `isSameNode` on each. **Its mutation**: give a button a `key` derived from
  `state.page` and confirm the hold falls naming node identity.
- **P28 — focus survives a redraw.** Same hold, asserting `document.activeElement` after a focus on
  a tab and a page switch.

## Traps

- `app/bar-height.ts` measures `.bottombar` by CLASS. The class stays; the rule that reads it is
  R84 and it must still pass.
- The bar is `md:hidden`. The oracle measures at 390 px, so the hidden state is measured by
  nothing — the a11y tier and R84 are what read it, and the class is preserved verbatim.
