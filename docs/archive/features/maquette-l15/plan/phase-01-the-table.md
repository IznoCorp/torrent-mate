# Phase 1 — The one navigation table

**Kind** conversion. **Part** 5 (`MODEL.md` § 2).

## The fact that exists four times

`PAGES_OF()` (`legacy.js:7655`, id · label · icon · badge · `offBar` · `fab`), `NAVIGATION`
(`legacy.js:9976`, the drawer's grouping), `PAGES` (`app/page-host.tsx`, id → component) and
`PAGE_PATHS` (`lib/addresses.ts`, id → path). A fact that exists four times is stale in three of
them.

## What lands

`app/navigation.ts` — one exported table, one row per page:

    id · path · Body · root · region · labelKey · icon · group · inBar · actionButton · badge

- **`path`** — `lib/addresses.ts`'s `PAGE_PATHS` becomes a derivation of this table. The address
  model keeps its exemption under invariant 10; it stops keeping a second copy.
- **`Body` / `root` / `region`** — `app/page-host.tsx`'s `PAGES` becomes a derivation too.
- **`labelKey`** — the label is `fr.json`'s, read through `useTranslation()`. **No French in the
  table**: the engine's `l: "Acquisition"` becomes `labelKey: "screens.acquisition.title"` or a new
  `navigation.*` namespace where no key exists. Extracted, never retyped.
- **`icon`** — the path data moves out of the engine's `icons` const into the table. The engine
  keeps `icons` for what it still draws.
- **`group`** — `NAVIGATION`'s three groups, as a value the drawer reads. Group NAMES are copy and
  live in `fr.json`.
- **`badge`** — a FUNCTION the row points at, exported by the feature:
  `features/acquisition/queries.ts` for « to grab + to resolve », `features/arrivals` for the stuck
  count. The frame names the feature once and its counters never.

## What the engine loses

`PAGES_OF` and `NAVIGATION` are deleted. What still needs them reads the seam:

- `render()`'s `found.shellOwned` / `found.fab` / the `404` fallback → `window.__navigation`
- `window.__pages()` → the table's ids
- `renderNav` and `openDrawer` still read it **this phase**; phases 2 and 7 delete them.

`grep -n "PAGES_OF\|NAVIGATION" legacy.js` must list **read sites only** — no declaration of
either — and the « Done when » re-runs it.

## The rule

`harness/navigation.py` gains a hold: **one table, and the four readers agree**. It drives every
page id `window.__pages()` returns, asserts the address the bar reaches matches
`lib/addresses.ts`'s path, that the page host draws it, and that the drawer's entry for it names
the same id. **Its mutation**: remove one row from `app/navigation.ts` and confirm the hold falls
naming the missing page — not « a tab is missing », which a count would also say.

**And a second hold, because a count would pass over an empty read**: the table's row count is held
at a floor. A reader that stopped reading satisfies « every id agrees » perfectly.

## Traps

- **`window.__pages()` is read by `harness/drawer.py`.** A table that answers fewer ids than the
  engine did makes that rule green over a drawer entry that leads nowhere.
- The badge derivation is a hook on the React side and a synchronous accessor on the engine side
  (`lib/queue.ts`'s `queueNow()`). Both must read ONE derivation — §13's rule, and the engine's own
  comment on `PAGES_OF` says so.
