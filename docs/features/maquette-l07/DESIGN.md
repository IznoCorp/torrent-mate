# L07 — Tailwind and CVA, surface by surface

**Lot** `L07` of `docs/reference/frontend-architecture.md` § 4, Phase 2. **Depends on** L02, L04,
L06 — all `LANDED`. **Branch** `feat/maquette-l07`. **Version** 0.98.35.

D2 in force: styling goes through Tailwind utilities, and the design vocabulary is expressed as
typed component variants (`class-variance-authority`) rather than hand-written class names. Each
surface converts on its own, with the oracle green at every step.

---

## § 1 — What this lot is, measured on the day it opened

Every figure below carries the command that produces it. A number nobody can re-measure is a
number nobody can contest.

|                                         |                                                          | how                                                             |
| --------------------------------------- | -------------------------------------------------------- | --------------------------------------------------------------- |
| BLOCK 1 — the prototype harness         | **228 lines**                                            | `awk 'NR<=228' frontend/maquette/design/refonte.html \| wc -l`  |
| BLOCK 2 — the application's stylesheet  | **4 136 lines**                                          | `awk 'NR>=229' frontend/maquette/design/refonte.html \| wc -l`  |
| Rules in BLOCK 2                        | **530**                                                  | count of lines ending in `{` from line 229                      |
| Declarations in BLOCK 2                 | **2 328**                                                | count of indented `property:` lines from line 229               |
| Distinct classes declared in BLOCK 2    | **293**                                                  | `.name` selectors, comments stripped                            |
| `@keyframes`                            | **5** — `pulse`, `spin`, `heroin`, `sh`, `splashremplit` | `grep -n '@keyframes' refonte.html`                             |
| `:has()` uses                           | **4**                                                    | selectors Tailwind cannot express; they stay in the base layer  |
| `className` sites in the component tree | **437** over 18 `.tsx` files                             | `grep -rhoE 'className=' design/src --include='*.tsx' \| wc -l` |
| `class="…"` in the shell document       | **49**                                                   | `grep -ohE 'class="[^"]*"' design/index.html \| wc -l`          |
| `class="…"` in the dying engine         | **131**                                                  | same, over `design/src/engine/legacy.js`                        |

**The rule suite and the two references, on the day this opened.** 55 rules, 1 227 holds,
`taken_at_commit` `a4418e6a`; the oracle measures 83 states × 33 regions against a reference
recorded at the same commit, verified an ancestor of `HEAD`. Both are healthy — this wave starts
from a tree whose post-merge steps were actually done.
<sub>`python3 -c "import json;d=json.load(open('frontend/maquette/hold-counts-baseline.json'));print(d['totals'],d['taken_at_commit'])"`</sub>

### The oracle measures 19 computed properties, and two of them decide how this lot converts

`regions.json` → `probe.computedStyleSubset` lists `position`, `font-size`, `font-weight`,
`line-height`, `padding`, `margin`, `border`, `border-radius`, `gap`, `opacity`, `visibility`,
`color`, `background-color`, **`box-shadow`**, **`animation`**, `display`, `flex-direction`,
`align-items`, `justify-content`.

`box-shadow` being measured is not a detail — see D-L07-4. `transition-duration` is **not**
measured, which is why D-L07-3's guard is a rule over class names rather than a hope that the
oracle catches a wrong duration.

---

## § 2 — Decisions

The four marked **(operator, 2026-08-24)** were arbitrated before a line was written, per §15 of
the constitution. The rest are proposed by the wave and are the operator's to overturn.

### D-L07-1 — BLOCK 1 is cut before it is deleted (operator, 2026-08-24)

**The lot says BLOCK 1 is deleted rather than converted. It is not deletable as it stands.**
Measured: six of its regions are the application's, not the prototype's —

| region                | lines  | why it is the app's                                                                                  |
| --------------------- | ------ | ---------------------------------------------------------------------------------------------------- |
| `@font-face` Geist    | 10–19  | the typeface the whole interface is set in                                                           |
| `login:socle`         | 22–47  | `box-sizing`, `html`/`body`, and **`overscroll-behavior-y: none`** — a compositor-facing declaration |
| `a` / `button` resets | 50–58  | the file's own comment says Tailwind's preflight covers these in the app                             |
| `:focus-visible`      | 59–62  | L03                                                                                                  |
| `.visually-hidden`    | 71–81  | L03                                                                                                  |
| `.skip-link`          | 88–103 | L03                                                                                                  |

What genuinely dies with BLOCK 1: `.stage` and `.device` (the phone frame), the `.hbtn` harness
buttons, the `html.measuring` hides, the declared harness deviations (`.device .bottombar` and
the two desktop `@media` re-assertions).

**And the boundary is wrong in the other direction too — two regions of BLOCK 2 are harness**, and
each says so in its own comment:

| region                                                               | lines     | rules |
| -------------------------------------------------------------------- | --------- | ----- |
| the state panel (`.hpanel`, `.states`) — « HARNESS, never exported » | 3824–3882 | 8     |
| the design-notes overlay (`.note`, `.notes`)                         | 4009–4035 | 4     |

They are deleted with BLOCK 1, not converted.
<sub>`grep -nE 'HARNESS\|Design notes overlay' frontend/maquette/design/refonte.html` reads 3824 and 4009 and nothing else past line 229.</sub>

**The cut happens in phase 1, before a single surface converts** — the same order the lot already
imposes for the compositor-facing declarations, and for the same reason: a region that moves in
the same commit as a conversion cannot be attributed when something falls.

### D-L07-2 — The palette is renamed to Tailwind's namespace, in its own phase (operator, 2026-08-24)

L06 named space, type, radius and easing with the namespaces Tailwind v4 reads, so those four
families lift into `@theme` unchanged — **verified by compiling Tailwind 4.3.2 against L06's own
token names**: `.p-4 { padding: var(--spacing-4) }`, `.text-6 { font-size: var(--text-6) }`,
`.rounded-3 { border-radius: var(--radius-3) }`, `.ease-standard { … var(--ease-standard) }`.

The palette does not: `--background` is in no Tailwind namespace, so `bg-background` does not
exist. Two mechanisms reach the same end, and **both were verified to work with the runtime theme
switch** — Tailwind emits its tokens inside `@layer theme`, and the prototype's unlayered
`:root[data-theme="light"]` block wins in the cascade:

- `@theme inline { --color-card: var(--card) }` — no rename, but two names for one colour live in
  the tree for good.
- renaming `--card` → `--color-card` — one canonical name, no alias block.

**The rename is the decision, and it lands as its own phase before any surface converts.** A token
rename changes no computed style, so the oracle closes that phase at zero divergence: if anything
moves, it is the rename and nothing else. Folding it into each surface's conversion was refused —
an oracle failure would then be unattributable between the rename and the conversion, which is
what "surface by surface" exists to prevent.

**30 colour tokens move. The 8 `--mq-shadow-*` do not** — see D-L07-4.
<sub>38 tokens declared between the `login:palette` markers; 462 `var()` call sites on them in `refonte.html`.</sub>

### D-L07-3 — Motion durations become bare milliseconds, held by a guard that reads class names (operator, 2026-08-24)

**`--duration-*` is not a Tailwind namespace, and the name is already taken.** Verified by
compilation: `duration-2` emits `transition-duration: 2ms` — Tailwind reads the bare number as
milliseconds. So the one family of L06's scale that does not lift is also the only one that
produces a **wrong value instead of a build error**. Redefining the utility does not recover the
name either: with `@utility duration-* { transition-duration: --value(--duration-*) }` in the
sheet, `duration-2` still compiles to `2ms` — the core utility wins.

The four touch-response steps become `duration-150`, `duration-200`, `duration-300`,
`duration-450` at their 22 call sites, all of which are `transition:` shorthands. **The three
loop periods are not affected and stay declared**: their 4 call sites are `animation:` shorthands,
which become `--animate-*` theme entries carrying the whole shorthand.
<sub>`grep -nE '^\s*[a-z-]+\s*:[^;]*var\(--duration-' refonte.html`</sub>

**What this costs, and it is why the guard is not optional.** `check-css-tokens.py --arm scale`
reads CSS _declarations_; a value living in a class name is invisible to it, and `duration-137`
compiles without complaint. A new arm reads the class names of the maquette's source and refuses
any `duration-<n>` outside the four steps. Mutation-tested: introduce a fifth value, watch the arm
fall and name it, restore.

### D-L07-4 — Shadows keep their tokens and never go through `shadow-*`

Tailwind rewrites every shadow into a five-part composite so ring and inset utilities can compose
with it:

```
.shadow-card { --tw-shadow: 0 10px 30px var(--tw-shadow-color, …);
               box-shadow: var(--tw-inset-shadow), var(--tw-inset-ring-shadow),
                           var(--tw-ring-offset-shadow), var(--tw-ring-shadow), var(--tw-shadow) }
```

Visually identical, and a **different computed `box-shadow` string** — which is one of the 19
properties the oracle measures. Converting the 8 shadows to `shadow-*` would therefore produce a
divergence on every shadowed region, none of them a visual change, and a wave whose whole proof is
"nothing moved" would open with dozens of divergences that mean nothing. The arbitrary-property
form `[box-shadow:var(--mq-shadow-card)]` compiles to `box-shadow: var(--mq-shadow-card)` — the
computed value is identical. Verified by compilation, all three forms.

### D-L07-5 — The engine's CSS becomes a bounded residue that dies with L13 (operator, 2026-08-24)

**55 of the 293 declared classes are consumed only by `legacy.js`** — dialogs, skeletons, deck
tiles — and the login gate and the splash sit beside them. D5 assigns `/login`, the splash, the
document-level delegation and the boot handshake to **L13**, so converting them here would be
L13's work pulled forward, and would make L07 a wave that changes mechanism as well as styling.

That CSS moves to a declared residual sheet, whose contract is written at its top: it names L13 as
its death, and **a rule refuses it growing**. The lot's "no hand-written component stylesheet
remains" reads as _for every surface this lot converts_, with the residue named, counted and dated
rather than left unremarked.

**This is also what keeps the sign-in gate working.** `serve.py` composes `/login` by extracting
six marker regions of raw CSS (`scale`, `font`, `palette`, `socle`, `style`, `splashstyle`) as
text. Tailwind's utilities live in a built stylesheet, so text extraction would return a page with
no styling at all. With login and splash in the residue, their markers survive untouched.

### D-L07-6 — CSS lands in the three layers D3 names, and `refonte.html` dies with the wave

| layer           | file                           | content                                                                                                                            |
| --------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| Tokens          | `design/src/styles/theme.css`  | `@import "tailwindcss"`, the `@theme` block, the `@source` confinement                                                             |
| Base            | `design/src/styles/base.css`   | reset, safe areas, the compositor-facing declarations, the L03 regions, `@font-face`, the 5 `@keyframes`, the 4 `:has()` selectors |
| Residue         | `design/src/styles/legacy.css` | D-L07-5's bounded sheet, carrying the `login:*` markers                                                                            |
| Everything else | the component                  | utilities behind typed CVA variants                                                                                                |

`refonte.html` ends the wave carrying nothing but a `<title>`, so it is deleted and `index.html`
keeps the title. That makes §15 of the constitution point at a file that no longer exists, which
is exactly the amendment the lot's **Done when** requires: the visual reference becomes the tokens
plus the component catalogue.

**Fourteen files name that path** and move in the same step: seven under `harness/` (including
`common.py`, which holds `DESIGN_SOURCES`), five under `scripts/`, plus `serve.py` and
`vite.config.mjs`. `oracle.py` and `fidelity.py` are not among them — they reach the sources
through `common.py`, which is why that file moves first.
<sub>`grep -rln 'refonte\.html' --include='*.py' --include='*.mjs' --include='*.sh' --include='*.js' frontend scripts | grep -v node_modules | wc -l`</sub>

`DESIGN_SOURCES` is the one that matters beyond a path edit: it is a three-file
tuple that does not include the component tree, so every source-level hold reading
`design_source()` goes blind the moment styling moves into components. **It gains the component
tree and the three stylesheets in phase 1**, before anything moves — otherwise six rules stay
green over evidence that has simply moved to another file, which is a trap this repository has
already paid for.

### D-L07-7 — The surface order, fixed here and reused by L09

The lot requires this order be written down. It is two tiers: shared foundations first, because a
page cannot convert before the primitives it composes; then the pages, in the order the operator
meets them.

**Tier A — foundations (no page converts here).** base layer and compositor rule · palette rename
· Tailwind wiring and scan confinement · the shell (top bar, bottom bar, scrollport, drawer,
scrim, FAB, toast) · the shared primitives (`ui/`: the one action-button system, form controls,
chips, empty and surface states, skeletons, dialog, sheet, panel).

**Tier B — the pages, and L09 walks this same list.**

1. Arrivées (live strip, pilot bar, the nine steps) · its resolution screen
2. Médiathèque (card, grid tiles, grid selection, filter zone, view tabs)
3. Acquisition (Découvrir deck, suggestion card, follows) · the add screen · releases and quality screens
4. Média — the sheet, the season matrix, the air-date popover
5. Système (key/value rows)
6. Maintenance
7. Configuration (settings panel, the eight field kinds)
8. Compte
9. The PWA install proposal

**Not in either tier, by D-L07-5**: the sign-in gate, the splash, and the markup the engine still
draws. **Not in either tier, by D-L07-1**: the design-notes overlay, which is deleted.

### D-L07-8 — The scan is confined, and the confinement is held from both ends

The production app already carries `@source not "../../maquette"` in
`frontend/src/styles/globals.css` — the fix for the 936 bytes that leaked once. The maquette's own
entry declares the mirror: it scans `design/src`, `design/index.html` and nothing above it. **A
rule holds both directions**, because a confinement written in one file and read by nobody is the
shape of every guard this repository has found green over its own subject. The proof the lot asks
for is a built production bundle whose CSS contains no class the maquette alone declares.

### D-L07-9 — Every class is classified three ways before it is touched

A surface's classes do not all have the same fate, and reading them as one is how a conversion
takes a load-bearing rule with it. Each conversion phase sorts its own scope first:

| kind               | what it is                                                                                                         | what happens to it                                                                                                                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **drawn**          | a component renders the element and owns its look                                                                  | converts to utilities behind a typed variant                                                                                                                                                              |
| **engine-drawn**   | `legacy.js` writes the markup                                                                                      | moves to the residue (D-L07-5), untouched                                                                                                                                                                 |
| **engine-toggled** | a component renders the node, the engine adds or removes the class on it (`classList.add`, a `class="… ${state}"`) | the look moves into the component as a `data-*` variant, **and the engine's write moves in the same step** — a `data-*` contract has three ends (D4) and they travel together or the interface half-works |

The third kind is the one with no natural warning: the conversion compiles, the component renders,
and the state simply stops painting because the engine is still writing a class nothing declares
any more.

### D-L07-10 — The scope of each phase is frozen in a manifest, not judged per phase

`plan/surface-manifest.json` partitions BLOCK 2's **530 rules into 38 surfaces**, each assigned to
a phase, and `plan/build-surface-manifest.py` **asserts the partition is total** — a rule owned by
no phase would otherwise reach phase 16 unconverted with nothing having said so.

Class names are the key. Line numbers are recorded for provenance and go stale as soon as the
first phase deletes a rule; a plan that scoped by line number would be wrong by phase 5.
<sub>`python3 docs/features/maquette-l07/plan/build-surface-manifest.py` → `38 surfaces, 530 rules, partition total`</sub>


---

## § 3 — What the oracle will say, and how it is answered

**The floor is zero divergence for most of this wave, and that is a stronger claim than L06's.**
L06 changed values on purpose and accepted 47 divergence signatures. This lot changes _mechanism_
and promises the rendering does not move — so a divergence is a defect until proved otherwise, not
a fold to be reviewed.

Three places where a divergence is expected and must be reviewed rather than accepted on sight:

1. **Shorthand expansion.** `padding: 8px 12px` written as `px-6 py-4` produces the same computed
   `padding`. A conversion that drops a side does not. The oracle sees this; it is the main thing
   it is for here.
2. **Tailwind's preflight**, if the `a`/`button` resets are dropped in its favour (D-L07-1 keeps
   them explicit precisely so this does not arise).
3. **`box-shadow` and `animation`**, addressed by D-L07-4 and by keeping the `@keyframes` in the
   base layer.

The oracle runs at the close of **every phase**, not only at the end. That is what "surface by
surface" means, and a divergence accepted without review names the same debt L06 has just paid.

---

## § 4 — Phases (the plan owns the detail)

The plan is `plan/INDEX.md`, which owns the reasoning and the ACCEPTANCE criteria. This section
owns only the shape.

| #    | Phase                                               | What it settles                                                                                                                                                                                      |
| ---- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | The base layer, and what the compositor reads       | The three stylesheets exist; the 17 compositor-facing declarations and the six app regions of BLOCK 1 are in the base layer; a rule refuses their removal; `DESIGN_SOURCES` gains the component tree |
| 2    | Tailwind arrives, confined                          | The build gains Tailwind v4; `@theme` lifts L06's four families; the scan is confined from both ends and a rule holds it. No surface converts                                                        |
| 3    | The palette takes Tailwind's name                   | D-L07-2's rename, alone, oracle at zero                                                                                                                                                              |
| 4    | Motion, and the guard that reads class names        | D-L07-3's four steps and the new arm                                                                                                                                                                 |
| 5    | The shell                                           | Tier A's frame                                                                                                                                                                                       |
| 6    | The shared primitives, and the first typed variants | `ui/` as CVA components — the API the rest of the wave composes                                                                                                                                      |
| 7–15 | Tier B, one surface per phase                       | D-L07-7's order                                                                                                                                                                                      |
| 16   | BLOCK 1 dies, and so does `refonte.html`            | The residue is bounded and its rule bites; §15 is amended                                                                                                                                            |

---

## § 5 — Out of scope, named

- **B-055** (the accessibility floor measures only the dark theme, 154 findings asleep in light),
  **B-056** (`splashremplit`), **B-057** (`audit2.py` measures four contexts of five), **B-058**
  (the commit-msg matcher fires on prose quoting it). Open, and not this lot's to close. B-056 sits
  inside the splash CSS, which D-L07-5 keeps as residue — so this lot does not touch it, and must
  not copy the name forward either.
- **The backend.** Nothing is wired. The interface is not frozen.
- **L09's work.** This lot proves the rendering did not change; L09 changes where the data comes
  from. Together a conversion defect and a wiring defect are indistinguishable, and the
  architecture file refuses the merge of the two explicitly.
- **`/control` and `/pipeline`**, which are surfaces still to be drawn and follow the drawing
  method, not this one.
- **The 53 flat `.py` files of the harness**, recorded and deliberately unscheduled.
