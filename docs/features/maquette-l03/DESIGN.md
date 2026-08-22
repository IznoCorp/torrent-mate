# L03 — Accessibility

**Codename** `maquette-l03` · **Commit type** `feat` · **Bump** 0.98.17 → 0.98.18
**Lot** `docs/reference/frontend-architecture.md` § Phase 1 — L03 (BINDING) · *depends on L01*
**Date** 2026-08-22

> The lot's own **Done when**, quoted from the architecture file so nothing here softens it:
> « Every screen has its landmark; every interactive element has an accessible name; a layer
> traps and restores focus; the whole application is reachable by keyboard; an automated audit
> runs in the gate; and the oracle is green — the non-visual part of this lot must move
> nothing. »

---

## 1. What is measured today

Every figure below was taken on `main` at `f5568068`, with the command that produced it. They are
the lot's starting line, and the burn-down is measured against them and no other number.

| Measurement | Value | Method |
| --- | --- | --- |
| `<main>` | **0** | `grep -rEo '<main([ >/]\|$)' design/src design/index.html design/refonte.html` |
| `tabindex` | **0** | `grep -rn 'tabIndex\|tabindex' design/src design/index.html` |
| `<dialog>` | **0** | same form |
| Keyboard handling (`keydown`, `Escape`, `onKeyDown`) | **0**, in React *and* in the 34 650-line engine | `grep -rn 'keydown\|onKeyDown\|Escape' design/src` |
| `role=` | **13** lines | `grep -rEc 'role=' design/src design/index.html design/refonte.html` |
| `<nav>` | **2** (`index.html`, `legacy.js`) | as above |
| `aria-*` | **63** — 31 `aria-label`, 13 `aria-hidden`, 11 `aria-pressed`, 6 `aria-checked`, 2 `aria-selected` | `grep -rno 'aria-[a-z]*' … \| sort \| uniq -c` |
| Headings | **1 `<h1>`** for **26 `<h2>`** and 1 `<h3>` | as above |
| `<button>` | **115** static, **3** with no static accessible name | script in § 9 |
| Focus ring | **already global** — `:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px }`, `refonte.html:59` | `grep -n 'focus-visible' design/refonte.html` |

**The 3-button figure is not the number, and the design says so on purpose.** The engine builds
buttons from helper functions and template strings; a static scan cannot see them. The real count
is what `axe-core` reports over the 83 rendered states, and P0 exists to record it before anything
is touched.

### Two findings that shape the lot

**`data-open` is already the universal layer signal.** `setOpen(element, on)`
(`legacy.js:9501`) toggles the `open` class *and* the `data-open` attribute, and it is called for
`#drawer`, `#screen`, `#dlg` and `#scrim`. On the React side `sheet.tsx` and the five screen
components emit `data-open` themselves. A focus manager therefore has nothing to invent and
nothing for the engine to call: **it observes an attribute that already exists**, it anchors on
`data-*` as D4 requires, and it survives the engine's death (L13).

**Interactive targets are already focusable.** The engine's click delegation opens only to
`event.target.closest("button, a[data-navgo]")` (`legacy.js:11694`) — a comment in the file
records that restricting it « only at buttons left the drawer inert », which is why it is the way
it is. So clickable things are native buttons and anchors. The keyboard hole is in the **layers**
and in the **shortcuts**, not in the targets.

---

## 2. Four decisions, arbitrated by the operator on 2026-08-22

Each was presented with its alternatives and its cost. They are settled; a later lot that wants
to revisit one re-argues it, it does not assume it.

### D-L03-1 — The mechanism outlives the engine; only the attributes go into it

The drawer, the dialogs, the toast and the tab bar are drawn by `legacy.js`, the engine D5 says
dies at L13 rather than surface by surface. The lot cannot promise « a layer traps and restores
focus » without touching them.

**Decided:** the focus **mechanism** is written shell-side in TypeScript, observes layer state
through `data-open`, and survives L13. Only the **attributes** (`role`, `aria-*`, `tabindex`) are
placed in the engine's markup, where they have to be. Little throwaway work; the interface is
accessible end to end today.

**Rejected:** React-only (the layers that trap focus are precisely the ones left out — the lot's
Done when would not hold). Whole engine including the deck, the selection bar and the generated
cards (a substantial body of markup rewritten as components in later lots, so paid twice).

### D-L03-2 — `axe-core`, its own tier, and CI on every PR

**Decided:** `axe-core` injected by Playwright over the 83 named states. A new tier
`frontend/maquette/harness/run.sh --a11y`, included in the full suite **and** added to the CI job
`harness-contracts` — which already runs `npm ci --prefix frontend/maquette/design` and installs
Chromium, so the wiring costs one step. Floor: **zero violations**, in the hard form — no
threshold, no tolerated list.

**Why an external instrument rather than a house rule.** A rule proves only the list of criteria
someone wrote into it. That is the exact failure this repository has already paid for twice —
`check-no-french.py` reported « no violation » because its word list had holes, and the answer was
to turn the question around. `axe-core` finds what we did not think of. It is the same reasoning
that made L01 an oracle rather than an opinion.

**Rejected:** full suite only (a regression could live across several PRs). A house rule (cheaper,
and blind by construction).

### D-L03-3 — The oracle floor is zero divergence; movement is neutralised, not accepted

`role`, `aria-*` and `tabindex` are invisible to the oracle — they change neither a rectangle nor
a computed style (D6). **Element substitutions and enlarged touch targets are not.**

**Decided:** every tag substitution is neutralised in CSS so the rendering does not move by a
pixel, and the lot's promise stays checkable in one command: *the non-visual part moves nothing*.
Touch targets that are too small are **recorded as debt and handed to L06**, not fixed here.

**Rejected:** reviewing and `--accept`ing divergences one by one (honest about touch targets, but
the « nothing moved » promise disappears and the review costs). Re-recording the reference (the
most complete, and it destroys the comparison point every following lot depends on).

**The rule that makes it tenable — substitute, never wrap.** `<div id="port">` becomes
`<main id="port">`: `display:block` on both sides, the oracle sees nothing. Wrapping `#view` in a
new `<main>` would add a box, hence a layout risk. Any substitution that is not neutral is
neutralised in the stylesheet, and **the oracle arbitrates, not the author**.

### D-L03-4 — Colour contrast is measured, recorded, and excluded from the floor

`axe-core`'s `color-contrast` rule targets the palette, which is L06's subject (the scale and the
visual language), not L03's.

**Decided:** the rule runs, its result is **recorded** — how many, where — and filed as an input
to L06's dossier. It does **not** fail L03's gate.

**Rejected:** including it (L03 would then decide the visual language before L06 arbitrates it,
and the oracle would move everywhere). Disabling it (« not measured » reads as « no problem »,
which is what this repository refuses).

---

## 3. Architecture — five units

Each unit is stated as *what it does · how it is used · what it depends on*, so it can be
understood and proved on its own.

### U1 — Landmarks and document structure

*What it does.* Gives every screen a landmark and a document outline an assistive technology can
navigate: `<main>`, `role`/`aria-label` on the regions that already exist, one `<h1>` per screen
with `<h2>` under it, a skip link, `aria-current` on the active tab, and a document title that
follows the route.

*How it is used.* By substitution on existing elements (D-L03-3). No new box.

*Depends on.* Nothing. It is the first structural unit because names and focus order both read the
tree it fixes.

### U2 — Accessible names

*What it does.* Every interactive element carries a name an assistive technology can announce.

*How it is used.* In components the labels go through `useTranslation()` and land in
`design/src/i18n/fr.json` — **extracted, never retyped**: a retyped string renders correctly while
the reference is broken. In the engine they are French literals like every other string in that
file, and the guard permits it by a named exemption rather than by omission: `check_strings`
globs only `.ts`/`.tsx` under the shell, and `check_unread_javascript` names `legacy.js` as one of
the two allowed JavaScript files — « an implicit exclusion is what this file exists to distrust ».
That debt dies with the engine.

*Depends on.* U1 for the regions that name themselves through their landmark.

### U3 — The focus manager

*What it does.* The only genuinely new piece. A TypeScript module in the shell that observes
`data-open` on the layer roots and, for each opening: remembers the trigger, places initial focus
inside the layer, traps it there (`inert` on the background — React 19 supports the attribute),
and **returns focus to the trigger on close**.

*How it is used.* It is installed once at boot. It knows nothing about the engine; it reads an
attribute. That is what makes it survive L13.

*Depends on.* `data-open`, which already exists on both sides. Nothing else.

### U4 — Keyboard paths

*What it does.* `Escape` closes the top layer by calling `window.__closeLayers` — **the verb
already exists**, and the lot does not write a second one. The tab bar is navigable. Anything that
is not already a native control answers `Enter` and `Space`.

*Depends on.* U3 (the layer stack the Escape path unwinds).

### U5 — Live regions and states

*What it does.* The toast becomes an announced region (`role="status"`), loading surfaces carry
`aria-busy`, errors are announced. Today a screen reader says nothing about what is happening.

*Depends on.* U1 for where the regions sit.

---

## 4. The gate

| | |
| --- | --- |
| **Instrument** | `axe-core`, a devDependency of `design/package.json`, injected by Playwright |
| **Surface** | the 83 named states of `design/src/states.js` |
| **Tier** | `frontend/maquette/harness/run.sh --a11y` — a fourth tier beside `--contracts`, `--oracle` and the full suite; **included in the full suite** and **added to the CI job `harness-contracts`** |
| **Floor** | **zero violations**, hard: no threshold, no tolerated list |
| **Excluded from the floor** | `color-contrast` — run, recorded, filed to L06 (D-L03-4) |
| **Not in** | `--contracts`. That tier is « the rules that fall when a NAME moves ». An accessibility audit is not one of them, and mixing the two would blur what each tier answers |

---

## 5. What proves the wave

Four proofs. None is optional, and each is a command with an expected output — the ACCEPTANCE
format the repository requires.

1. **The oracle is at zero divergence.** `make maquette-oracle` (`oracle.py --check`), 83 states
   × 33 regions. This is the whole content of « the non-visual part must move nothing ».
2. **The harness hold counts are unchanged.** `frontend/maquette/harness/run.sh`, full suite,
   compared against `hold-counts-baseline.json`. L02's lesson: **only the hold-count comparison
   saw the logout contract fall** — a green suite is not the same statement.
3. **`axe-core` reports zero on the 83 states**, `color-contrast` excepted and separately
   recorded.
4. **The new rule is mutation-tested.** Break a focus trap on purpose, confirm the rule falls
   *and names the right defect*, restore. A rule that has never been seen red proves only that it
   agrees with the code.

**Order of operations, and it is a lesson already paid:** commit the work, run the gates, commit,
*then* mutate and restore. Mutating before the commit is how a mutation gets shipped.

**After the squash merge, re-record the oracle reference** (`make maquette-oracle`, then
`python3 frontend/maquette/oracle.py --record`, commit). The squash replaces the commit the
reference names, and the pointer goes dangling on a fresh clone.

---

## 6. Explicitly out of scope

Named here so that « not done » is a decision on the record rather than an oversight.

| Left out | Where it goes, and why |
| --- | --- |
| **Touch-target size** (WCAG 2.5.8) | Measured and recorded; corrected in **L06**. Enlarging a target moves pixels the scale has not arbitrated yet |
| **Colour contrast** | Measured, filed to **L06**, outside the floor (D-L03-4) |
| **B-036** — `system-panne` and `acq-follows-groupe` are still French state ids, and no arm of `check-no-french.py` reads the state table | It belongs to a wave, and this is not the one: mixing it with accessibility blurs both. Flagged, not taken |
| Converting engine-drawn surfaces to components | L13 and the surface lots. L03 places attributes in the engine, it does not migrate it |

---

## 7. Risks

| Risk | What it would look like | Response |
| --- | --- | --- |
| A tag substitution is not layout-neutral | The oracle reports divergences on regions the lot never meant to move | The oracle is the arbiter: neutralise in CSS until it is green, or drop that substitution. **Never** `--accept` |
| `axe-core` finds a large first violation count | P0 records a number the wave then has to burn down inside its own scope | P0 exists precisely to surface that number **before** any change. If it is large enough to change the lot's shape, that is an arbitration to bring to the operator, not a target to quietly trim |
| Engine-side aria labels add French to a file under a guard | `check-no-french.py` fails | **Verified on `main` before the spec was written, not assumed.** `check_strings` builds its scope from `.ts`/`.tsx` under the shell, so `legacy.js` string literals are read by no arm, and `check_unread_javascript` names the file as exempt with its reason. Separately, `check_french_debt` bounds the 25 declared debt **words** (names, not strings) to that same file. The production-app ratchet (`french-exemption-baseline.json`) reads `frontend/src` and is not concerned |
| `inert` on the background breaks the harness's own driving | Rules that click through a layer stop working | The harness bar (`.hbtn`) sits outside the layer roots; hold counts in proof 2 catch any rule that falls |

---

## 8. Phases

**P0 comes first because the instrument comes before the change.** That is L01's lesson applied to
its own successor: measured before, a burn-down is a fact; measured after, it is an opinion.

| # | Phase | What it delivers |
| --- | --- | --- |
| **P0** | The instrument, and the debt recorded | `axe-core` wired, the `--a11y` tier, CI step, and the **violation count on `main` before anything is touched**, per state and per rule |
| **P1** | Landmarks and structure (U1) | `<main>`, region roles and labels, one `<h1>` per screen, skip link, `aria-current`, document title per route — all by substitution, oracle green |
| **P2** | Accessible names (U2) | Every control named; component labels extracted into `fr.json` through `useTranslation()`, engine labels as French literals under the named exemption |
| **P3** | Focus manager and keyboard paths (U3, U4) | The `data-open` observer: trigger memory, initial focus, trap via `inert`, restore on close. `Escape` through the existing `window.__closeLayers`; tab bar navigable |
| **P4** | Live regions and states (U5) | `role="status"` on the toast, `aria-busy` on loading surfaces, announced errors |
| **P5** | The floor bites | Hard zero enforced, mutation test, documentation, oracle green, hold counts unchanged |

---

## 9. Methods, so every figure in § 1 is re-derivable

```bash
cd frontend/maquette/design
# tags
for t in main nav header footer section aside ol li h1 h2 h3 dialog; do
  printf '%s: ' "$t"
  grep -rEo "<${t}([ >/]|$)" src index.html refonte.html 2>/dev/null | wc -l
done
# aria surface
grep -rno 'aria-[a-z]*' src index.html refonte.html | awk -F: '{print $NF}' | sort | uniq -c | sort -rn
# keyboard handling
grep -rn 'keydown\|onKeyDown\|Escape' src index.html | wc -l
```

Buttons without a static accessible name — the script that produced « 115 / 3 » — walks each
`<button …>` in `index.html`, `src/engine/legacy.js` and every `*.tsx`, and counts the ones with
neither `aria-label`/`aria-labelledby` on the open tag nor text content in the body once tags,
entities and JSX expressions are stripped. **It undercounts by construction**, which is § 1's
point: `axe-core` on the rendered states is the measurement, and this one is only the floor below
which the truth cannot be.
