# L14 — The surfaces that outgrew their file · DESIGN

**Contract**: `docs/reference/frontend-architecture.md` § 4, `#### L14 — The surfaces that outgrew
their file`. Its « Done when » is the definition of finished and this document does not restate
it — a contract copied into a second file is a contract wrong in one of them. **Brief**:
`docs/features/maquette-l14/BRIEF.md` — what the plan does not say, measured on 2026-09-01.

**Constitution served**: **§15** (the maquette IS the product, and its files are the files the
next version ships — a file nobody can read whole is a file nobody can change safely), **§13**
(B-283: the interface never asserts about data still in flight), **§12** (the phone first — the
skeleton B-283 draws is a phone state, and a tap lost to a re-render, B-247, is a phone defect
before it is anything else), **§16** (the two screens this lot cuts keep their Back exactly as
delivered), **DOIT-10** and **DOIT-11** (every screen keeps its address; nothing here moves one).

**What kind of wave this is.** A **CONVERSION** wave with two behaviour phases inside it, each in
its own commit (D-L14-5, on L12's and L15's precedent). Five phases move code and prove the
rendering did not change — the oracle at zero divergence over its 2 958 measurements, every time.
Two phases change what the interface does — B-283 (a skeleton for what is unknown while a read is
in flight) and the surface half of B-247 (a page's nodes keep identity across a store write) —
and each lands with a rule that DRIVES the behaviour and is seen red under its mutation. **No
phase does both.**

---

## 1. What was measured before this design was written

Run on 2026-09-01 on `386fbf0a1`, this branch's base, against a fresh build of that tree served
on 8899 after the steward released the harness. **Every figure carries the command that produces
it** (§ 0). Re-run them; do not believe them.

| Fact                                                | Command                                                                                                                                                                                                                              | Read                                                                                                                                                                                                               |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| The four files, non-blank                           | `for f in features/acquisition/page.tsx features/media/media-screen.tsx features/library/page.tsx features/arrivals/resolution-screen.tsx; do printf '%-45s %s\n' "$f" "$(grep -cve '^\s*$' frontend/maquette/design/src/$f)"; done` | **756 · 796 · 613 · 430**                                                                                                                                                                                          |
| Files at or over the ceiling                        | `python3 scripts/check-frontend-boundaries.py --arm size \| grep "at or over"`                                                                                                                                                       | **6** (the four, plus the engine's two)                                                                                                                                                                            |
| `Icon` written how many times                       | `grep -rn -E '^(export )?function Icon\b' --include='*.tsx' frontend/maquette/design/src`                                                                                                                                            | **4** — `ui/icon.tsx:13`, `features/releases/releases-screen.tsx:27`, `features/arrivals/resolution-screen.tsx:61`, `features/media/media-screen.tsx:68`                                                           |
| The three local copies against the shared one       | read side by side                                                                                                                                                                                                                    | the three take `{ paths, strokeWidth }`; `ui/icon.tsx` takes the same plus an optional `className` and draws the identical `<svg>` — **no drawing decision differs**, so the swap is a deletion                    |
| Other PascalCase names declared in two files        | `grep -rhoE "^(export )?(async )?function [A-Z][A-Za-z0-9]+" frontend/maquette/design/src --include='*.ts' --include='*.tsx' --exclude-dir=engine \| sed -E 's/^(export )?(async )?function //' \| sort \| uniq -c \| awk '$1>1'`    | **`Icon` ×4, `ActionButton` ×2** — the second is TWO components under one name: the frame's floating action button (`app/action-button.tsx:41`) and the panel's private action row (`ui/panel/index.tsx:89`)       |
| The frame's domain floors                           | `python3 scripts/check-frame-domain.py \| tail -1`                                                                                                                                                                                   | `ui/ 0, lib/ 18, app/ 129`                                                                                                                                                                                         |
| Register                                            | `python3 scripts/check-bug-register.py --next` · `grep -o "\| \*\*Total\*\* \| \*\*[0-9]*\*\*" BUGS.md`                                                                                                                              | next **B-295** · total **174**                                                                                                                                                                                     |
| `app/shell.tsx`                                     | `python3 scripts/check-frontend-boundaries.py --arm size \| grep shell`                                                                                                                                                              | **398** of 400 — not opened by this wave                                                                                                                                                                           |
| Which surfaces keep their nodes across a store bump | the probe in § 4.1, run on this build                                                                                                                                                                                                | **media sheet 61/61, resolution 24/24, incomplete lens 18/18** keep every node; **acquisition « En cours » 5/44, « Suivis » list 12/77, grid 12/24, grouped 12/77; library list 17/53, grid 20/41** replace theirs |
| WHY the acquisition sections replace theirs         | the second probe in § 4.1: the section's `innerHTML` before and after the bump                                                                                                                                                       | **byte-equal** (1 968 characters), the `<section>` node is the SAME, the card inside it is a NEW node                                                                                                              |
| Where the placeholder comes from                    | `sed -n 55,63p frontend/maquette/design/src/features/media/queries.ts`                                                                                                                                                               | `placeholderData: () => reference.sheetFor(title)` — the engine's COMPLETE sheet, so no field is ever missing during priming here                                                                                  |
| The oracle on this build against `main`'s reference | `make maquette-oracle`                                                                                                                                                                                                               | 87 states × 34 regions, 2 958 measurements, **no divergence**                                                                                                                                                      |

**Three of these change what the brief assumed, and § 7.1 makes saying so this wave's duty:**

1. **B-247's surface half has TWO mechanisms, not one, and the acquisition one is React's.**
   The library replaces its rows because `LibraryList` keys the window on the store's `version`
   (`drawKey={version}`), which was written on purpose so a repaint snaps an open swipe shut the
   way the engine's wholesale rewrite did. The acquisition page replaces its cards for a reason
   nobody had measured: **React 19 re-sets `innerHTML` whenever the `dangerouslySetInnerHTML`
   prop is a new object, without comparing the string.** React 18 compared `__html` strings and
   left equal markup alone; 19.2.8's `setProp` assigns `domElement.innerHTML = value.__html`
   whenever the prop's identity moved (`node_modules/react-dom/cjs/react-dom-client.development.js`,
   `case "dangerouslySetInnerHTML"` inside `setProp`, called from the generic prop loop on
   `nextProp !== lastProp`). Every `dangerouslySetInnerHTML={{ __html: … }}` written inline is a
   fresh object per render, so every re-render of a page that subscribes to the store's version
   recreates every engine-drawn child. The media sheet and the resolution screen are JSX and keep
   their nodes; the incomplete lens keeps its nodes only because `LibraryPage` subscribes to
   `state` and a bump moves `version` alone. **Filed as B-295** with the probe that establishes
   it; the repair is § 4.
2. **The brief's rule for B-283 reads « `status === "pending"` », and that is not the reading.**
   With `placeholderData`, TanStack Query reports `status: "success"` and `isPlaceholderData:
true` while the read is in flight; `pending` is the state with NO placeholder at all (an
   address `titleForProviderId` cannot resolve). Both are « in flight » for §13, and the flag is
   `isPending || (isPlaceholderData && isFetching)` — § 5. A rule reading `status` alone is green
   over the primed case, which is the whole case.
3. **`ActionButton` is a name written twice for two different things.** Not the same component
   written out twice — the reading the « twice » arm exists for — but a reader who greps the name
   finds two. The panel's private one is renamed `PanelActionButton` in phase 1, through
   `scripts/rename-identifiers.py`, so the arm can hold PascalCase duplicates at a HARD ZERO with
   no allow-list. An allow-list is where the next `Icon` would hide.

---

## 2. Where each piece lands

Invariant 10 governs every placement: a component that names a medium, a season, a follow or a
decision stays in its feature folder; what names nothing goes to `ui/`. Invariant 7 is the other
edge: no new file under `ui/` imports a feature, and no feature imports another. Every name below
is English and written in full (`docs/reference/code-naming.md`); every header comment is written
so that it reads years from now — **no date, no lot, no phase** (B-287).

| Today                                                                    | Becomes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |     Non-blank (estimate; the phase measures) | Kind                  |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------: | --------------------- |
| `features/arrivals/resolution-screen.tsx` (430)                          | `resolution-screen.tsx` — the screen alone · **`resolution-cards.tsx`** — `ReleaseCard`, `DecisionCard`, `Candidates`                                                                                                                                                                                                                                                                                                                                                                   |                                  ~170 · ~200 | conversion            |
| `features/media/media-screen.tsx` (796)                                  | `media-screen.tsx` — the screen: params, the two reads, the derivations, the bar and the composition · **`sheet-fields.ts`** — the four narrowed types · **`season-list.tsx`** — `SeasonList` · **`media-hero.tsx`** — the hero and the trailer row · **`media-cast.tsx`** — the director/creator row and the cast strip · **`media-library-facts.tsx`** — the « Bibliothèque » facts panel (three branches) · **`media-information.tsx`** — the « Informations » panel and the actions | ~190 · ~30 · ~230 · ~110 · ~70 · ~100 · ~110 | conversion            |
| `features/library/page.tsx` (613)                                        | `page.tsx` — the three lenses' composition · **`library-head.tsx`** — `LibraryHead` · **`library-list.tsx`** — `LibraryList` · **`library-count.tsx`** — `CountLine`, `SortLabel` · **`library-empty.tsx`** — `EmptyLibrary` · **`incomplete-lens.tsx`** — the « Incomplets » body                                                                                                                                                                                                      |         ~110 · ~135 · ~220 · ~70 · ~50 · ~60 | conversion            |
| `features/acquisition/page.tsx` (756)                                    | `page.tsx` — the tab switch · **`acquisition-tabs.tsx`** — `AcquisitionTabs` · **`now-tab.tsx`** — `NowTab` · **`follows-tab.tsx`** — `FollowsTab`'s list · **`follows-filters.tsx`** — its search field, pills and mode switch · **`discover-tab.tsx`** — `DiscoverTab`, containers AND effect together                                                                                                                                                                                |        ~35 · ~50 · ~145 · ~250 · ~110 · ~175 | conversion            |
| `Icon` in three features                                                 | deleted; each file imports `ui/icon`                                                                                                                                                                                                                                                                                                                                                                                                                                                    |                                     −14 each | conversion            |
| `ui/panel/index.tsx`'s `ActionButton`                                    | `PanelActionButton`                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |                                            0 | conversion            |
| the `{ __html }` object, written inline at nine sites                    | **`ui/markup.ts`** — `useMarkup(html)`: one `{ __html }` object per distinct string                                                                                                                                                                                                                                                                                                                                                                                                     |                                          ~30 | **behaviour** (B-247) |
| `LibraryList`'s `drawKey={version}`                                      | the question, the selection mode and the first page's identity — § 4.2                                                                                                                                                                                                                                                                                                                                                                                                                  |                                            0 | **behaviour** (B-247) |
| the unknown parts of the media sheet, printed as answers while in flight | a skeleton line where the answer will go — § 5                                                                                                                                                                                                                                                                                                                                                                                                                                          |                   +40 across the media files | **behaviour** (B-283) |

**What the Découvrir tab keeps, on purpose.** `discover-tab.tsx` carries the containers and the
effect that asks the engine to fill them (`fillSug`, `sugFoot`, `mountDeck`) as ONE unit. The
engine owns those nodes' content and the deck's gesture mutates them in place; the producer and
its callers are **L19's**, and this lot moves the React half exactly as it is.

**What `media-screen.tsx` keeps.** `data-part="hero"` and `data-region="screen-media/body"` are
the two elements `base.css` names for the view transitions (`screen-banner`, `screen-body`) and
`data-key="mediaSheet:<title>"` is the screen's identity for the ladder. They stay on the elements
they are on today; the hero moves as a component but the naming attribute moves WITH the element,
and `view-transition-name` is a name on ONE element — R115's holds read both names and fall if
either lands on two nodes or on none.

---

## 3. The rules this wave lands, and what each does NOT read

Every conversion phase is proved by **the oracle** (D8: geometry and computed style over 87 states
and 34 regions) plus the **size arm**, whose grandfather entry for the file leaves in the same
commit — the arm refuses an entry for a file back under the ceiling, and a file back over it with
no entry, so the count cannot quietly climb again. The oracle's two blind spots (D8: a
pseudo-element or a child node carrying a function) are already held by R26 and R116 for the
surfaces this lot touches, and R115 holds the transition names; each phase runs `--contracts`,
which carries R100, R80 and the cheap guards.

| Rule                                               | Phase       | Holds                                                                                                                                                                                                                                                                                                                                                                                             | What it does NOT read — said first                                                                                                                                                                                                                       |
| -------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/check-component-once.py` (new — its own guard: `check-frontend-boundaries.py` is at 952 of its 1 000-line ceiling; the plan's phase 1 records the deviation) | 1           | a PascalCase top-level function declared in more than one file under `design/src` (the engine and the mocks excluded) — hard zero, no allow-list, the corpus size printed with a floor                                                                                                                                                                                                            | camelCase helpers (`announce` ×4, `isOpen` ×2, `useStaging` ×2 are private helpers or two subjects — a hook written twice is the report's to name, not this guard's); a component copied under a DIFFERENT name                                            |
| `--arm size` (existing)                            | 2, 3, 5, 6  | the four entries leave `GRANDFATHERED` one by one; « Done when » reads through it                                                                                                                                                                                                                                                                                                                 | nothing new — it is the arm the lot was written against                                                                                                                                                                                                  |
| **R119 — `harness/priming.py`** (new)              | 4           | with a PARTIAL placeholder and 2 000 ms of latency: while in flight the screen draws what the tap knew (title, year, kind) and a `[data-skeleton]` where each unknown part will go, and NO `[data-part="no-info"]`; after `quiet()` the skeletons are gone and the no-info for the missing trailer is drawn; the control: the same walk with the FULL placeholder draws no skeleton at any moment | the rendering of the skeleton (oracle — but no named state shows it at rest, so the drawing is held by its variant and by this rule's presence count only); the seasons' own placeholder (there is none: seasons in flight are read through `isPending`) |
| **R100 (f)** — `harness/persistence.py` (extended) | 7           | on `acq-now-loaded`, `acq-follows-list`, `acq-follows-grid`, `lib-list`, `lib-grid`, `mediasheet-series`, `arr-resolution`: every captured node — cards, tiles, rows, buttons, key-value rows — `isSameNode` after `window.__store.touch()`, with a floor on the number captured per state                                                                                                        | the engine-FILLED containers of Découvrir (`#sugitems`, `.deckbody` — B-247's other half, L19's); a write that legitimately redraws (entering selection mode, a sort, a delete); the boot hint's own `pointerdown` (L15 closed that path)                |
| the oracle                                         | every phase | zero divergence                                                                                                                                                                                                                                                                                                                                                                                   | anything a rule above names                                                                                                                                                                                                                              |

**Every rule lands with its mutation, seen red and restored, at the moment it is written.** The
`check-component-once.py` and the size arm are GUARDS — `scripts/mutate.sh` cannot judge a guard (B-273) — so
they are mutated by hand and read by exit code; R119 and R100 (f) are rules, mutated through
`mutate.sh` against a committed tree.

---

## 4. B-247's surface half — two mechanisms, one property

### 4.1 The measurement

The probe: on each named state, wait for `window.__mocks.quiet()`, capture every node matching
`#view [data-part="card"], #view [data-part="tile"], #view button, #view [data-part="pill"],
[data-part="screen"][data-open] button, [data-part="screen"][data-open] [data-part="episode/row"],
[data-part="screen"][data-open] [data-part="card"], [data-part="screen"][data-open] [data-part="key-value"]`,
call `window.__store.touch()`, wait 250 ms, and count `isSameNode` by position. The second probe
reads the first `<section data-part="section">`'s `innerHTML` before and after and compares the
two strings. Both become R100 (f) in phase 7; the figures are § 1's row.

### 4.2 The repair

**The acquisition page (B-295).** One `ui/` helper, `useMarkup(html)`, returns the SAME `{ __html }`
object for as long as the string is unchanged — the comparison React 18 made and React 19 does
not. Every `dangerouslySetInnerHTML` site this lot touches goes through it: the « En cours »
sections, the « Suivis » list, groups and grid, the empty notes, the skeleton sections, and the
library's incomplete lens. The helper names no domain (invariant 10 — `ui/ 0` stays 0) and is
the only place the trick is written, so the day React changes again there is one line to change.

**The library list.** `drawKey` stops naming the store's `version` and names what actually makes
a row's markup differ: the MODE (`libMode` — a tile is not a card), the SELECTION MODE (`selMode`
— `libRowHTML` and `tileHTML` read it to draw a checkbox in place of the poster's link), and the
identity of the listing's first page. That last one is what a real change to the rows produces
and nothing else does: TanStack Query's structural sharing keeps a page object's identity while
its content is equal, so a refetch that changes nothing keeps the nodes, a delete
(`__deleteLibraryItems` rewrites the pages) changes it, and a new question (search, category,
sort, scenario) is a new query with a new first page. A page loading BELOW keeps the first page's
identity, so paging no longer rebuilds the window — which the windowed rows were written to
avoid and were losing on every landing, since `render()` bumps the store on every cache landing
through `app/engine-redraw.ts`. A toggled checkbox is already written onto the node in place by
the delegation (`legacy.js:10073`), so a kept node reads right.

**The consequence, named so it is a decision and not an omission (D-L14-3).** A swipe left open
on a follow or a library row now SURVIVES an unrelated store write instead of snapping shut. The
engine's own `openCard` keeps pointing at a live node — which is the case `ui/virtual-rows.tsx`
already argued for within a scroll, and the case B-247 names for a tap. No rule held the snap;
the operator may overrule it at the review, and the change is one line (`drawKey`) either way.

**What is NOT repaired here.** The engine still bumps the store on every cache landing and every
action, and every page that subscribes to `version` still re-renders on each — this lot makes a
re-render keep its nodes; it does not make the engine bump less. Découvrir's containers are filled
by the engine and are L19's. `features/maintenance/page.tsx`, where B-247 was found, is not one of
the four and is not opened; R100 (f) reads the four surfaces and says so.

---

## 5. B-283 — a skeleton for what is unknown, and only that

**The decision it applies** (operator, 2026-08-31, « A généralisée + amorçage »): the screen opens
with what the tap already knows, in real content, and draws a skeleton for the parts still in
flight — never an answer. The maquette's placeholder is the engine's complete sheet, so at rest
and during priming here nothing is missing and **no pixel moves**; the real backend's projection
carries `{t, f}`, and that is the case the rule drives.

**The flag.** `inFlight = sheet.isPending || (sheet.isPlaceholderData && sheet.isFetching)` for the
sheet; `seasons.isPending` for the seasons read, which has no placeholder. An errored read is not
in flight: §13 refuses an assertion about data that has not ARRIVED, and a read that failed has
answered — the screen prints what it can, as today.

**Field by field, never block by block.** A part whose value the placeholder carries is drawn; a
part whose value is absent AND `inFlight` draws a skeleton line where the answer will go; a part
absent once landed draws the assertion it draws today (« aucun synopsis », « pas de
bande-annonce », « inconnu »). The parts: the metadata line and the genres in the hero, the
rating, the trailer row, the synopsis, the director/creator row, the cast strip, the seasons and
aired counts, the completeness pip, and the provider identifiers. The BLOCKS stay — the body keeps
its eight children at every instant, which is what R115's priming hold counts.

**The drawing.** One typed variant, `skeletonLine` in `ui/variants/surfaces.ts`, wearing the
residue's `sk` shimmer exactly as `Skeletons` does (`ui/state-surfaces.tsx`) — `.sk` carries the
shimmer under its reduced-motion guard and dies with the residue at L13, at which point the
shimmer moves to the variant as every residue rule does — plus a height on the type scale and a
width variant (`full`, `wide`, `half`, `short`). It emits `data-skeleton=""`, the attribute the
harness already counts. A `<p>` that today prints « aucun synopsis » keeps its element and its
class; its CONTENT becomes lines. No new named state is added: `engine/states.js` is one of the
two files this lot may only subtract from, and R119 drives the state itself.

**How R119 thins the placeholder** — and three things about this paragraph and § 3's row for R119
changed while the rule was built, each because a reading proved the drawing wrong. **The plan's
phase 4 records those deviations**, as phase 1 records the guard's; a design is what was decided,
so it is not edited to agree with what the code became.

**How R119 thins the placeholder.** `window.__referentiel` is a plain object and `sheetFor` a
property on it; the rule wraps it before opening the sheet so it answers `{ t, k, y }` alone for
the title under test, sets `window.__mocks.setDefaultLatency(2000)` after `window.__reset()` (which
zeroes it), navigates to the sheet's address, and reads at ~300 ms and again after `quiet()`. The
title is Broadchurch's — the one sheet with no trailer, which `screen_addresses.py` already uses —
so the landed reading has exactly one no-info part to find. **The control**: the same walk with
the wrapper removed draws no skeleton at any moment, which is what says the thinning is what the
rule measures and not a slow build.

---

## 6. One kind of change per commit — how this wave obeys § 0

Conversion phases (1, 2, 3, 5, 6) land at zero oracle divergence and move no behaviour. Behaviour
phases (4, 7) name what they change in their own commit and land with the rule that drives it.
Where a behaviour phase touches a file a conversion phase cut, it does so AFTER the cut — which is
why B-283 follows the media decomposition and B-247 follows the acquisition and library ones.

---

## 7. What every rule in this wave must survive — B-085's questions, asked first

Before each rule is believed: **what does it not read, and what would it still read if the
behaviour were gone?**

- A rule that reads the FULL placeholder for B-283 is green over the defect it is written for
  (the brief, § 5). R119 thins the placeholder and CONTROLS that the thinning happened.
- A rule that captures nodes and re-selects them by selector reads a replacement as the original
  (R100's own header). R100 (f) holds handles on the page and asks `isSameNode`, as (b)–(d) do.
- A rule that reads the acquisition page ONCE reads the tab that happens to be open. R100 (f)
  drives the three tabs by name and prints its count per state, with a floor.
- A guard that counts duplicates from a regex is only as good as the regex: `check-component-once.py` prints
  how many declarations it read, holds a floor, and its mutation is a second `Icon` written back.
- A size gate is arithmetic and cannot lie about a count — but it can be satisfied by moving lines
  into a file that is then never imported. `check-markup-contracts.py`'s arm 5 refuses an exported
  variant nobody names, and `tsc -b` refuses an unused import; a component nobody renders is
  refused by the oracle's divergence when its markup leaves the screen. All three run at every
  phase.
- « Nothing moved » over a conversion says nothing about a behaviour (§ 6's newest trap): phases
  4 and 7 are held by their rules, and the oracle's green there is the least of what they owe.

---

## 8. Decisions taken in this design

| #            | Decision                                                                                                                                                                                                         | Because                                                                                                                                                       |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D-L14-1**  | `Icon` lives in `ui/icon.tsx` and NOWHERE else; the three private copies are deleted, not merged — the shared one already takes what they take                                                                   | the signatures agree and the `<svg>` is identical; « one exception in sight » (the contract) is what the file in `ui/` already is                             |
| **D-L14-2**  | The « written twice » guard holds **PascalCase** declarations at a hard zero, and `ui/panel/index.tsx`'s private `ActionButton` is renamed `PanelActionButton` so no allow-list is needed                        | an allow-list is a baseline, and a baseline is where the next copy hides; the rename is one private identifier, through the rename tool, proved by the oracle |
| **D-L14-3**  | A page's nodes keep identity across a store write, and the consequence — an open swipe survives an unrelated write — is accepted and named for the operator's review                                             | B-247's own text; `ui/virtual-rows.tsx` already treats a row replaced mid-gesture as the defect; no rule held the snap                                        |
| **D-L14-4**  | The `{ __html }` identity is stabilised in ONE `ui/` helper (`useMarkup`), never at the sites                                                                                                                    | the trick is React-version-specific; one file changes when React does; `ui/ 0` domain words stays 0                                                           |
| **D-L14-5**  | Conversion and behaviour split per phase and per commit, not per wave                                                                                                                                            | § 0's rule, on L12's and L15's precedent                                                                                                                      |
| **D-L14-6**  | The library's `drawKey` names the mode, the selection mode and the first page's identity — never the store's `version`                                                                                           | those three are what makes a row's MARKUP differ; `version` moves on every cache landing and every action, and moved the window on each                       |
| **D-L14-7**  | B-283 draws a skeleton per FIELD, inside the element that will carry the answer, and keeps every block                                                                                                           | the body's child count is what R115's priming hold reads; a block that appears late would be the two-owner shape L12 paid for                                 |
| **D-L14-8**  | No new named state for the priming; R119 drives it through the mock layer and a thinned reference                                                                                                                | `engine/states.js` is only subtracted from (the brief); the mock layer's knobs are the driving surface built for this                                         |
| **D-L14-9**  | `discover-tab.tsx` moves the containers and the effect as one unit and changes nothing in them                                                                                                                   | the producer and its engine-side callers are L19's; the effect and the containers are one arrangement (« React manages zero children there »)                 |
| **D-L14-10** | The instruments' debts named in the plan's § 5 (B-269, B-272, B-273, B-276, B-277, B-278, B-287, B-291) are NOT taken: no phase here opens `served_copy.py`, `mutate.sh`, `harness-hold-counts.py` or `exits.py` | the rule is « the next wave that touches the tool takes its debt »; this wave touches `persistence.py` and `check-frontend-boundaries.py`, which carry none   |

---

## 9. The register, written DURING the wave

`BUGS.md`, next number **B-295** (`python3 scripts/check-bug-register.py --next` — a number taken
on another branch is invisible here). Entries land as they are found. Known at the design:

- **B-295** — React 19 re-sets `innerHTML` on the prop object's identity, so every re-render of a
  page subscribed to the store's version recreates its engine-drawn children; nine sites, none
  memoised. Filed at the design with the probe; **`fixed #NNN`** by phase 7.
- **B-283** — `fixed #NNN` by phase 4, with R119 and its mutation.
- **B-247** — its surface half recorded in the body as done by phase 7 with R100 (f); the row
  stays `open` until L19 closes the producer half, and says so.

The fifth post-merge step — recounting « guards green over what they do not read » — is this
wave's too, and **zero is a real answer written down**.

## 10. The gates

**Per phase**: the oracle at zero divergence, `run.sh --contracts` (the contracts tier and the
repository's cheap guards — the script prints both counts), and every rule of the phase
mutation-tested, seen red, restored.

**Before merging**: the **full** suite (`run.sh`, not `--contracts`), the `--a11y` tier,
`scripts/harness-hold-counts.py --compare` with every movement written down — reading `failed` in
the totals before trusting a record (B-291) — and `make check` at zero failures **and zero
errors**.

**The harness is one per machine.** The steward released it on 2026-09-01 and runs no instrument
while this wave is open; every run is announced by message all the same, and a rule that falls
while another listener is on 8899 is re-run alone before it is read as anything.

## 11. What this wave does not do

- Move a pixel. Every conversion is at zero divergence or the divergence is a defect.
- Move a producer or its engine-side gesture callers (L19), the ladder's handler (L13), or a line
  INTO `app/shell.tsx` (398 of 400) or the engine's two.
- Touch `docs/production/`, or re-create `docs/archive/`.
- Adopt a library: nothing here needs one, and D9's question was asked (a memoised prop and a
  key are not a problem a library solves).
- Backend work (D7): B-283's repair is in the screen; the projection is untouched.
- Relitigate D1–D11, invariants 1–15, or the operator's answers of 2026-08-30.
- Stop between phases (the plan's INDEX carries the constraint and its self-check).
