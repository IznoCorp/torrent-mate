# Phase 15 — The install proposal, and the appearance

**Kind** conversion. **Part** 9.

## The install proposal

`app/install.ts` — two platforms, two paths, and neither is optional. Android and desktop fire
`beforeinstallprompt`, which must have its default prevented or the browser posts its own proposal;
it is replayed on a gesture, once. iOS Safari fires nothing, so the banner IS the guide.

**Who is asked, and when**, moves verbatim: never over the gate, never when standalone, not twice a
session. `alreadyInstalled()` — `display-mode: standalone` — becomes **the one place that knows
whether browser chrome exists around the application** (Part 9 names it as such, and P27 is L11's
to measure).

`#installbar` becomes `app/install-bar.tsx` rendered into phase 4's bottom slot: it is one of the
three things Part 6 says the slot holds.

## The appearance

`app/appearance.ts` — the three values, the `localStorage` key, the live `matchMedia` listener that
acts only while « system » is chosen, and the `data-theme` attribute. **The inline script in
`index.html` stays**: it must run before any module does, and the document's comment says why.

**One defect is fixed by the move and it is not a behaviour change**: the inline script reads
`"systeme"` / `"clair"` while the engine writes `"system"` / `"light"`. The two have disagreed
since the English rename, so a saved « light » choice does not survive a reload without a flash.
The values are made one, in the engine's spelling, which is the one every other reader uses.

## The rules

- R51 and R52 hold the install halves; they are re-run.
- A hold on the appearance round trip: choose « light », reload, assert `data-theme="light"` is set
  **before the first paint** — read from a `document.documentElement` snapshot taken in an init
  script, not after load. **Mutation**: put the two spellings back and confirm the hold falls
  naming the value that did not survive.

## The oracle reads this one

`shell/install-bar` is a region; the appearance changes every colour the subset measures. The
oracle runs under the default theme, so a light-theme divergence is invisible to it — the rule
above is what reads it.
