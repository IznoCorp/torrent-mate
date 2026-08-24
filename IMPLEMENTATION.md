# Current feature: shell-mobile — the v1 redesign

## THE MISSION CHANGED. Read this before anything else.

**This is no longer a mobile restyling of the shipped app.** It is a REDESIGN — a finished v1,
a version in its own right. The prototype is not a reference the current app is brought towards
piece by piece; it is the product, and the app will be rebuilt onto it.

That reverses the order of work:

1. **Finish the prototype first — every page.** Especially the ones that exist IN PRODUCTION and
   are not yet drawn here. A surface that production has and the prototype does not is a hole in
   the v1, not a later phase. The inventory is below and it is exhaustive. ⚠ **« Every page » is
   the SCOPE, never the running order** — that is `docs/reference/frontend-architecture.md`'s
   thirteen lots, and where they stand is § « Where the frontend work stands » just below.
2. **Then the operator judges.** The prototype is bound to the backend only once the operator
   considers the design AND the front-end architecture solid enough. That judgement is theirs, it
   is not a checklist, and no amount of green rules substitutes for it.
3. **Then, and only then, it becomes the new version.** Binding it to the backend is a separate
   mission with its own plan.

Until step 2 is passed, **nothing here derives app code**. The phase table that used to sit in
this file described the opposite order — deriving the app surface by surface — and it is gone.

**Branches:** one per wave (`feat/maquette-sp4b`, `feat/maquette-sp4c`, …) — each wave
squash-merges onto `main` after green CI and a clean final adversarial review (standing
operator instruction). What waits until the end is not `main` but the **binding**:
production keeps running the shipped SPA untouched, the merged waves change only the
prototype track (`frontend/maquette/`, its CI gates and docs), and nothing derives app
code until the operator's judgement (step 2 above). Non-negotiable.

**Spec:** `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md`
**The prototype:** `frontend/maquette/design/refonte.html` — §15 of `docs/reference/product-intent.md`. It is the VISUAL reference and carries the stylesheet; since SP4-fin wave 1 it carries no program — the engine is
`frontend/maquette/design/src/engine/legacy.js`, and every migrated surface starts in its own component.
**Bug register:** `BUGS.md` at the repo root — every reported defect, one closed at a time.

---

## Where the frontend work stands — and what comes next

**The target and the ORDER live in `docs/reference/frontend-architecture.md` (BINDING). This
section is the only place that says where the work STANDS.** Duplicating state is what produced a
stale table read as current for three days.

|                            |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Last landed**            | **L06 — The scale**, PR **#490**, merged 2026-08-24, version 0.98.32, squash `a4418e6a`. The scale: 32 tokens in one `:root` block, four families at zero (276 spacing, 150 type, 106 radius, 24 motion folds), the three fields at 16 px (D-L06-6 wide), the 42 contrast findings paid and `color-contrast` in the enforced hard-zero floor (D-L06-5), `--tm-bottom-bar-h` published by the shell (D-L06-4), the ratchet dismantled. Two rules joined the suite (R83 type_scale 9 holds, R84 runtime_tokens 8 holds → 55 rules, 1 227 holds); 47 oracle divergence signatures accepted, each with its fold named. Both references re-recorded from `main`'s tip at `a4418e6a` and verified ancestors of `HEAD` |
| **In flight**              | **L07 — Tailwind and CVA, surface by surface**, PR **#494**, branch `feat/maquette-l07`, version 0.98.37. Sixteen phases: four build the ground, eleven convert one surface each in the order L09 reuses, one deletes the scaffolding. **Phases 1–5 landed** — the base layer left BLOCK 1 (six of its regions were the application's, including the typeface and three of L03's), the 18 compositor-facing declarations gained a guard that reads the components as well as the stylesheets, and `DESIGN_SOURCES` reached the component tree. Tailwind v4 then arrived confined — preflight deliberately NOT imported, the scale lifted into `@theme static`, the scan held from both ends by a new guard. **Two measured traps, and neither would have been caught by anything that existed**: naming `@source` directories confines NOTHING (Tailwind scans the project root automatically and `@source` only adds to it — the same mechanism that leaked 936 bytes into production), and a plain `@theme` is tree-shaken, so the scale vanished from the served document and 2 236 of 2 739 measurements collapsed — while the run BEFORE it was green **because the leak was still dragging the tokens in**. Then the palette: 30 colours renamed to `--color-*` and moved into `@theme static`, the 8 shadows deliberately left outside the `--shadow-*` namespace so no utility can ever be made of them, the light theme given its own marker because `@theme` is unconditional and a theme is a condition — and both themes MEASURED, since the oracle reads only the dark one. **The rename tool could not do the rename**: asked to move `--card` it touched zero files and said so as « 0 file(s) touched », because a word boundary cannot precede `--`. It has a custom-property mode now, anchored on the FORM rather than the word, with five tests. Oracle at 0 divergence over 2 739 measurements at the close of each phase; one named hold-count movement (R74 split, 9 → 10, because widening the read exposed that its pattern could not tell the router's history instance from the platform's) |
| **Next**                   | **L07 — Tailwind and CVA, surface by surface** (depends on L02, L04, L06 — all `LANDED`): no wave opens without its design and its plan. The lots run strictly in sequence |
| **Before it**              | L03 — PR **#475**, version 0.98.18 · L02 — PR **#470**, version 0.98.13 · L01 — PR **#467**, version 0.98.10. All three archived under `docs/archive/features/`; L04 and L05 are archived beside them (L04 by #482, L05 by this pull request)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **What decides the order** | `docs/reference/frontend-architecture.md`, never this table. This table says only where the work STANDS                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |

**What L04 is, in one line**: the maquette's 26 files stop being grouped by KIND and get grouped
by SUBJECT, the two import cycles are broken, the hub `data.ts` stops existing, and seven guards
refuse the next drift. **Nothing observable changes** — the oracle is the proof, green at every
step.

Four decisions were arbitrated by the operator on 2026-08-22 and are recorded in its DESIGN § 2:
the module ceiling covers **the maquette only** (production is not touched — it is archived at
switchover); **no unit-test runner** lands here, and the debt is recorded against **L09**, which
brings the mock layer non-vacuous tests must rest on; `components/panel.tsx` splits **in three**,
its two domain blocks registering themselves; and `data.ts` is **cut for good** rather than
renamed. Two further decisions were taken in the design with their precedent: `i18n/` does not
move (two tools read its literal path), and the three files that die at L13 share the existing
`engine/` bucket, `legacy.js` itself staying put because its path is the most-cited in the
repository.

**What L04 is NOT**: bundle splitting (that is L12 — it changes loading behaviour), the harness's
53 flat `.py` files (recorded and deliberately unscheduled), and B-036 / B-040, which belong to
their own waves.

**Next action**: L07 is open. Its design is `docs/features/maquette-l07/DESIGN.md`, its plan
`docs/features/maquette-l07/plan/INDEX.md`, and the wave is on `feat/maquette-l07`. Phase 1 is the
work in hand.

**Phases of L07** — the plan is `docs/features/maquette-l07/plan/INDEX.md`, which owns the
reasoning and the 20 ACCEPTANCE criteria. This table owns only the status.

| #   | Phase                                                | File                                        | Status |
| --- | ---------------------------------------------------- | ------------------------------------------- | ------ |
| 1   | The base layer, and what the compositor reads        | `plan/phase-01-the-base-layer.md`           | [x]    |
| 2   | Tailwind arrives, confined                           | `plan/phase-02-tailwind-confined.md`        | [x]    |
| 3   | The palette takes Tailwind's name                    | `plan/phase-03-the-palette-rename.md`       | [x]    |
| 4   | Motion, and the guard that reads class names         | `plan/phase-04-motion.md`                   | [x]    |
| 5   | The shell                                            | `plan/phase-05-the-shell.md`                | [x]    |
| 6   | The shared primitives, and the first typed variants  | `plan/phase-06-the-primitives.md`           | [ ]    |
| 7   | Arrivées, and its resolution screen                  | `plan/phase-07-arrivals.md`                 | [ ]    |
| 8   | Médiathèque — the card                               | `plan/phase-08-the-card.md`                 | [ ]    |
| 9   | Médiathèque — tiles, selection, filters              | `plan/phase-09-library.md`                  | [ ]    |
| 10  | Acquisition — the deck and the follows               | `plan/phase-10-acquisition.md`              | [ ]    |
| 11  | Acquisition — the add screen, releases, quality      | `plan/phase-11-add-and-releases.md`         | [ ]    |
| 12  | Média — the sheet, the matrix, the popover           | `plan/phase-12-the-media-sheet.md`          | [ ]    |
| 13  | Système, and Maintenance                             | `plan/phase-13-system-and-maintenance.md`   | [ ]    |
| 14  | Configuration — the panel and its eight field kinds  | `plan/phase-14-settings.md`                 | [ ]    |
| 15  | Compte, and the install proposal                     | `plan/phase-15-account-and-install.md`      | [ ]    |
| 16  | BLOCK 1 dies, `refonte.html` dies, §15 is amended    | `plan/phase-16-the-scaffolding-dies.md`     | [ ]    |

**What L07 is, in one line**: the 4 136-line hand-written stylesheet becomes Tailwind utilities
behind typed CVA variants, one surface at a time with the oracle green at every step; the
scaffolding that was never meant to ship is deleted rather than carried forward; and what the
dying engine still needs becomes a residue with a name, a count and a date of death.

**Four decisions were arbitrated by the operator on 2026-08-24** and are recorded in its DESIGN
§ 2: BLOCK 1 is **cut before it is deleted** (six of its regions are the application's, including
the typeface and three of L03's); the palette is **renamed** to Tailwind's `--color-*` namespace
**in its own phase**, before any surface converts, rather than aliased through `@theme inline`;
the four motion durations become **bare milliseconds** with a new guard reading class names; and
the CSS the dying engine still consumes becomes a **bounded residue** that dies with L13.

**One measured trap the wave opened on, and it produces no signal from any existing instrument**:
`--duration-*` is not a Tailwind namespace, and `duration-2` is already a Tailwind utility meaning
**2 ms**. So the one family of L06's scale that does not lift is the only one that compiles to a
WRONG VALUE instead of an error — and `transition-duration` is not among the oracle's 19 measured
properties, so nothing that exists today would have caught it. Verified by compiling Tailwind
4.3.2; redefining the utility does not recover the name either.


**Phases of L06** — the plan is `docs/archive/features/maquette-l06/plan/INDEX.md`, which owns the
reasoning and the 24 ACCEPTANCE criteria. This table owns only the status.

| #   | Phase                             | File                                           | Status |
| --- | --------------------------------- | ---------------------------------------------- | ------ |
| 1   | The scale, and the ratchet        | `plan/phase-01-the-scale-and-the-ratchet.md`   | [x]    |
| 2   | Space folds                       | `plan/phase-02-space-folds.md`                 | [x]    |
| 3   | Type folds                        | `plan/phase-03-type-folds.md`                  | [x]    |
| 4   | Radius, motion, the runtime token | `plan/phase-04-radius-motion-runtime-token.md` | [x]    |
| 5   | The palette pays its debt         | `plan/phase-05-the-palette-pays-its-debt.md`   | [x]    |
| 6   | The ratchet dies                  | `plan/phase-06-the-ratchet-dies.md`            | [x]    |

### Review cycles — PR #484

### Cycle 1

Four reviewers (code, tests, comments, silent failures), 2026-08-23. Retained: 2 major
(`knownMedium` leans on the fuzzy `sheetFor`; the B-046 hold tolerates a fixed scratch port),
6 medium, a batch of minors → `plan/phase-09-pr-fixes-cycle-1.md`. Ignored with reason: the
pre-existing bug numbers in old comments, the README's `/profile` row, the French `recordPath`
message, `switchover.py`'s pipe (rejected twice). Open for the operator: a second Back after a
cold screen reaches the exit guard — the documented design, questioned.

### Cycle 2

Two reviewers (code+silent failures, tests+comments) over phase 9's diff, 2026-08-23. Cycle-1
findings verified closed. Retained: 3 major — the reopen fires on a Back onto a buried sheet entry
(a wrong interface, introduced by 9.4); R69's seam wraps `pushState` only (two boot catches held
by nothing); the reader takes an inline return type's `{` as the body and counts a call as a read
— plus 2 medium and minors → `plan/phase-10-pr-fixes-cycle-2.md`. Ignored with reason: library
titles reaching the synthesised fallback from an address (the in-app door's own behaviour, D-8.3),
`armedExit` on the reopen branch (pre-existing shape), four TypeScript shapes refused as « cannot
read » (deliberate).

### Cycle 3

Two reviewers over phases 10–11, REAL taps at 390×844, 2026-08-24. Cycle-2 findings verified
closed; § 16's forbidden path (Back climbing to the parent over a real stack) hunted and not
found. Retained: 1 critical (the 404's « Aller à Acquisition » blind-steps onto the guard — one
Back then quits the PWA), 1 major (drawer/account-menu page switches leave the abandoned page
sandwiched — rule 2 fails exactly on the finger-reachable walks), 1 major-premise (« the tab bar
sits above the layers » is false; two branches lean on the sentence), comment rot from the fourth
boot seam, and reader/hold minors → `plan/phase-12-pr-fixes-cycle-3.md`.

### Cycle 4

One reviewer over phase 12 + the R82 split, real taps, 2026-08-24. The split verified hold-
conserving (96 checks, multiset-compared); the continuation's lifecycle attacked and not
broken; the 12.3 premise re-verified true. Retained: 1 critical — `homeFloorExists` written
once at boot, stale after the 404's escape lays the floor (12 Backs to leave; re-opens 12.2
via the drawer) — and two overstating sentences → `plan/phase-13-pr-fixes-cycle-4.md`.

### Cycle 5 — the ceiling, and one bounded excursion past it

One reviewer over the phase-13 delta, real taps, 2026-08-24. Cycle 4's defect verified fixed
(tab AND drawer walks flat, the drawer's replace-in-place gone); every wrong-raise and
wrong-lower attack rejected but ONE: the lowering line fired on a FORWARD too (the handler holds
the direction and did not read it there) — depth 4 → 12 off a 404 arrival, eleven Backs to
leave. The fix is the reviewer's own one condition (`direction === "BACK"`), landed with four
R82 holds and mutation-tested (`812543fa`), then re-verified by the orchestrator. **This is one
fix past MAX_CYCLES = 5**, taken rather than merging over a known critical or stalling the wave:
bounded to a single condition, specified by the reviewer, verified on the reviewer's own walk.
The excess is recorded here for the operator rather than smoothed over.

**Phases of L05** — the plan is `docs/archive/features/maquette-l05/plan/INDEX.md`, which owns the
reasoning and the 21 ACCEPTANCE criteria. This table owns only the status.

| #   | Phase                                                            | File                                             | Status |
| --- | ---------------------------------------------------------------- | ------------------------------------------------ | ------ |
| 1   | The harness's ground                                             | `plan/phase-01-the-harness-ground.md`            | [x]    |
| 2   | The pages take their paths                                       | `plan/phase-02-pages-take-paths.md`              | [x]    |
| 3   | The screens are renamed                                          | `plan/phase-03-the-screen-renames.md`            | [x]    |
| 4   | The sign-in screen gets its address                              | `plan/phase-04-login.md`                         | [x]    |
| 5   | The panel tier                                                   | `plan/phase-05-the-panel-tier.md`                | [x]    |
| 6   | The offline guard, and one subtraction                           | `plan/phase-06-the-guard-and-the-subtraction.md` | [x]    |
| 7   | The records, and the gate                                        | `plan/phase-07-the-records.md`                   | [x]    |
| 8   | PR fixes, review cycle 1 — the four blocking defects             | `plan/phase-08-pr-fixes-cycle-1.md`              | [x]    |
| 9   | PR #484 fixes, review cycle 1 — what four reviewers found        | `plan/phase-09-pr-fixes-cycle-1.md`              | [x]    |
| 10  | PR #484 fixes, review cycle 2 — what phase 9 opened              | `plan/phase-10-pr-fixes-cycle-2.md`              | [x]    |
| 11  | The navigation path — § 16 rules 1–3, D1b (operator, 2026-08-24) | `plan/phase-11-navigation-path.md`               | [x]    |
| 12  | PR #484 fixes, review cycle 3 — the layer walks                  | `plan/phase-12-pr-fixes-cycle-3.md`              | [x]    |
| 13  | PR #484 fixes, review cycle 4 — the stale floor flag             | `plan/phase-13-pr-fixes-cycle-4.md`              | [x]    |

**What L05 is, in one line**: the eight pages leave `?page=` for a real path, the address model
leaves the engine for `lib/addresses.ts` — the first subtraction of D5 — and the harness host
moves to one that answers a real path, which is what lets a rule drive by URL instead of through
a seam that dies with the engine.

**What L05 left open, and it is on `main`**: four blocking defects, found by an adversarial review
that did not write the code and reproduced by the wave itself before it stopped. A deep address to
a media sheet lands the 404 page underneath it (`state.page = 404`, so Back reads « Adresse
introuvable ») — a regression against the tree before it, on the wave's own headline feature, and
R75 stays green because the screen covers the frame. A 404's address recomposes to `/`, which R69's
fourth hold cannot see because it only measures the cold load. `?panel=follows` without its colon
is accepted as a genre and an unknown subject fabricates a media labelled « à jour », reachable
from a URL. And the fallback port moved onto `switchover.py`'s, whose bind error is swallowed, so
R73 would report a broken sign-in where there is a port collision. Two further findings sit beside
them: the navigation-failure flag those guards are meant to raise is read by no rule, here or
before, and the ninth boundary arm stays green if `addresses.ts` is deleted.

**What L03 is, in one line**: landmarks, accessible names, focus management on every layer, the
keyboard paths — and `axe-core` in the gate at a hard zero. Four decisions were arbitrated by the
operator on 2026-08-22 and are recorded in its DESIGN § 2: the focus MECHANISM is written
shell-side and survives L13 while only attributes go into the dying engine; the audit is
`axe-core` on its own `--a11y` tier, in CI on every PR; the oracle floor is **zero divergence**,
tag substitutions neutralised in CSS rather than accepted; and colour contrast is measured,
recorded and handed to L06 rather than enforced here. Touch-target size and B-036 are named as
out of scope in § 6.

**Phases of L03** — the plan is `docs/archive/features/maquette-l03/plan/INDEX.md`, which owns the
reasoning and the 18 ACCEPTANCE criteria. This table owns only the status.

| #   | Phase                                 | File                                       | Status |
| --- | ------------------------------------- | ------------------------------------------ | ------ |
| 1   | The instrument, and the debt recorded | `plan/phase-01-instrument-and-debt.md`     | [x]    |
| 2   | Landmarks and structure               | `plan/phase-02-landmarks-and-structure.md` | [x]    |
| 3   | Accessible names                      | `plan/phase-03-accessible-names.md`        | [x]    |
| 4   | Focus manager and keyboard paths      | `plan/phase-04-focus-and-keyboard.md`      | [x]    |
| 5   | Live regions and states               | `plan/phase-05-live-regions.md`            | [x]    |
| 6   | The floor bites                       | `plan/phase-06-the-floor-bites.md`         | [x]    |

### L03 is complete on its branch — 744 accessibility violations to 0, and nothing moved

`axe-core` over the 83 named states: **744 violations over 7 rules → 0**. The oracle: **0
divergence over 2 739 measurements**, at the close of every phase. The floor is a hard zero, in
`run.sh --a11y` (a fourth tier), in the full suite and in CI on every maquette pull request.

|                          |                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The instrument           | `frontend/maquette/a11y.py` — axe-core over the 83 states, three modes, importing `oracle.py`'s plumbing rather than copying it                                                                                                                                                                                                                                                                                                                            |
| What an audit cannot see | **R81** (`harness/focus.py`, **20 holds**) — the recorded figure, from `hold-counts-baseline.json` → `rules["focus.py"].count`, which is a runtime count by `common.Journal`. The wave's prose said 15 and the source has 10 `check()` call sites, five of them inside a loop over the layers: neither is the answer, and only the recording is: focus in and back out, `Escape`, the skip link landing FOCUS, `aria-busy`, every error surface announcing |
| The starting line        | `a11y-debt.json`, which `--record` now refuses to overwrite: it is a starting line, not a snapshot                                                                                                                                                                                                                                                                                                                                                         |
| Handed to L06            | `a11y-contrast.json` — 42 contrast findings on 10 elements, 27 of them one badge. Touch-target size was expected to be a debt and is **not**: `target-size` is applicable and reports 0                                                                                                                                                                                                                                                                    |

**Four findings, and three of them are about instruments rather than about markup.**

1. **The audit's first version was a vacuous gate.** Scoped to `.device` — the phone frame, the
   product, an entirely reasonable choice — five page-level axe rules go `inapplicable` without a
   word. It reported « 0 violation » for `landmark-one-main` on a tree with zero `<main>`.
2. **The hold-count baseline's commit pointer was dangling**, and `--compare` read that field only
   to print it. It refuses now — more strictly than `oracle.py --check`, which only warns.
3. **A hold-count recording needs a tree AT REST**, and « the served copy is frozen at the start »
   is true and insufficient: `entry.py` and `startup.py` compare against the design host, and
   `serve.py` re-reads `index.html` on every request. Editing during a recording made them measure
   a new document against an old build. **This is the trap the next wave will meet unchanged.**
4. **The CI step guarding the maquette fixture was red on `main`** — one drifted value — and
   `--record` refuses a baseline taken on a red suite, so proof n° 2 was unobtainable until it was
   repaired.

**And the rule found three defects in the focus manager on its first run**, one of which is worth
carrying: `focus()` on an element inside an `inert` subtree does nothing, silently — so restoring
focus before clearing the mark left the caret on `<body>` at every close. The manager reproduced
the exact defect it exists to prevent.

**One arbitration is the operator's and is reversible**: `maximum-scale=1, user-scalable=no` is
gone from the viewport meta. It was 83 of the 744 (WCAG 1.4.4, zoom forbidden), and iOS Safari has
ignored `user-scalable=no` since version 10 — but it undoes a deliberate PWA choice.

**Phase 1 found three things nobody was looking for.** The hold-count baseline
pointed at `c7714c38`, a commit the L02 squash replaced — not an ancestor of `HEAD`, absent from
a fresh clone — and `--compare` read that field only to print it, where `oracle.py --check` at
least warns. It refuses now. The maquette's follow fixture had drifted from `acquire.db`, so the
CI step guarding it was red on `main` and no baseline could be recorded at all. And the first
version of the new audit was a VACUOUS GATE: scoped to `.device` it made five page-level axe
rules `inapplicable` and reported « 0 violation » for `landmark-one-main` on a prototype with
zero `<main>` elements.

**The debt, measured before the wave touched it**: 744 violations over 7 rules across the 83
states — 533 `region`, 83 `meta-viewport`, 49 `landmark-one-main`, 49 `page-has-heading-one`,
24 `aria-allowed-attr`, 4 `scrollable-region-focusable`, 2 `button-name` — plus 42
colour-contrast findings held for L06. The instrument reproduces: two recordings of one tree are
byte-identical.

**What L02 settled, measured on `main` after the merge**: **0 selection calls anchored on a CSS
class**, out of 699 in `harness/*.py` — 473 on `data-*`, 188 on an id, 33 on a bare tag, 5 on a
role. The floor is held by ARM 2 of `scripts/check-markup-contracts.py`, which **extends** that
guard rather than sitting beside it, and its floor is a hard zero.
<sub>method: extract the string argument of every `querySelector|querySelectorAll|locator|matches` call in `harness/*.py` and classify it</sub>

> ⚠ **Two figures for one burn-down, and neither is re-measurable now.** The wave's own rows said
> « baseline 834 → 0 » and « baseline burn-down 342 → 0 » of the same thing. The end state is
> measured above and is not in doubt; the starting figure is, and guessing which is right would
> put a third number into circulation. Whoever knows should say so in
> `docs/archive/features/maquette-l02/plan/INDEX.md`; until then neither is cited.

### What the next session needs to know before touching anything

1. **The oracle exists, and it runs on THIS machine.** `make maquette-oracle`, or
   `frontend/maquette/harness/run.sh --oracle`. A measurement is bound to the machine that took
   it — on a Linux runner the same unmodified tree reads 1477 where this one records 1474.1 — so
   the reference carries its platform and `--check` REFUSES to compare across a mismatch. It is
   never run on `--contracts`, which is the per-pull-request tier.
2. **After a squash merge, RE-RECORD the reference.** The reference names the commit it measured;
   squashing replaces that commit, so the pointer goes dangling on a fresh clone. `--check` now
   says so on its own — « NOT an ancestor of HEAD » — but the fix is a command, not a warning to
   live with.
3. **The oracle reference was dangling, and it is mended** — PR **#473**, `baseCommit` now
   `8adc5643`, an ancestor of `HEAD`. Nothing is blocked. What is worth keeping is the shape of
   the incident and one thing it proved for free:

   - It was point 2 of this very list, met anyway by the wave that had just written it. The step
     has therefore moved into the plan's § 5 method, where a wave reads it, with the two commands
     it actually takes.
   - **The re-record changed ONE line of 35 651** — `baseCommit` — and left every measurement
     byte-identical. So the reference was stale only in its pointer, and, unplanned, **the oracle
     is deterministic**: two recordings of the same tree on the same machine produce the same
     file. L01 proved the instrument BITES; nothing had proved it REPRODUCES, and an oracle that
     did not would have cried at every wave.

   ⚠ **And the paragraph this replaces said « DANGLING RIGHT NOW » four days after it stopped
   being true.** An urgent state written into a handover list is a statement nobody retires when
   it resolves — the mirror of the lesson above, and the same file. Anything here phrased as
   _right now_ is a claim to re-check before citing.

4. **B-036 is open and belongs to a wave, not to a tidy-up**: `system-panne` and
   `acq-follows-groupe` are still French state ids, and **no arm of `check-no-french.py` reads
   the state table**. Fixing the two names without adding the arm repeats the reason they
   survived.
5. **The L06 spec is parked, not lost** — `docs/superpowers/roadmap/maquette-l06/specs/`. Its
   header names the three points on which the architecture file supersedes it, including a scale
   granularity the operator arbitrated on figures presented before #466 existed. **Re-arbitrate;
   do not silently pick one.**

**What it delivers.** `frontend/maquette/oracle.py`, three modes (`--record`, `--check`,
`--accept`) plus `--contracts` and `--coverage`, measuring **83 named states × 33 regions =
2 739 measurements in ~24 s** against a committed reference of 36 237 lines. L01 delivered it at
82 states; L02 added one, and this paragraph kept L01's figures — re-measure before citing.
<sub>`python3 -c "import json;c=json.load(open('frontend/maquette/oracle-reference.json'))['counts'];print(c)"` · `wc -l frontend/maquette/oracle-reference.json`</sub> Wired as a THIRD
tier: `frontend/maquette/harness/run.sh --oracle` and `make maquette-oracle`, deliberately not in
`make check`.

**What it proves, and it is the architecture file's own « Done when »**: a deliberate ONE-PIXEL
padding change fails it with 10 divergences, every one on `shell/sheet-content`, each `+2px` of
height, across the ten `settings-*` states that open the panel.

**Six findings, each measured rather than argued** — the full record is in the wave's DESIGN and
its plan INDEX:

1. The recovered 17-property subset was **blind to an overlay opening**. `#scrim` between
   `lib-list` and `drawer-navigation`: 17/17 properties identical AND an identical rectangle.
   Amended to 19 with `opacity` and `visibility`; flagged for the operator's arbitration.
2. **Neutralising once at open neutralised nothing.** `.note` is re-emitted by the page
   components, so it was back in 56 of the 82 states; the boot toast is timer-driven and was
   visible in 34. The first reference measured the prototype's scaffolding.
3. The plan's **order was wrong**, and a measurement said so: `drawer-navigation` read five times
   gave five values. Determinism moved ahead of the reference.
4. `make lint` read `frontend/maquette/harness/` but **not `frontend/maquette/`**, so
   `fidelity.py` and `serve.py` had never been linted.
5. An ACCEPTANCE criterion was **vacuous before it could pass** — `check-markup-contracts.py`
   does not read `data-region` at all.
6. The frozen clock **changes nothing this oracle can see**, measured at 03:00 against 23:30.
   Recorded as measured rather than dressed up as a demonstration. B-036 was opened along the
   way: two state ids are still French.

**What it does NOT do.** It changes no rendering — that is what makes its own reference
trustworthy — and it does not re-anchor the 280 class-anchored rule selections, which is L02.

**Why this lot came before the visual language.** SP5b — the scale — is lot **L06**, and it
`depends on L01`. Phase 0 says « Nothing else may start »: every lot after it changes mechanism
while promising the rendering is unchanged, and until L01 that promise could not be proved at all
— `fidelity.py` had no target left and `parity-probe.py` went with the translation layer in #465.
**It can be proved now**, which is what unblocks L02 and everything after it.

---

## Current state

**SP4 is complete.** Seventeen waves have landed, each squash-merged onto `main` after green CI
and a clean final adversarial review; none of them derives app code.

The catch-all is empty. `design/refonte.html` — 39 561 lines when SP4 opened, an entire
application inside one injected fragment — is **4 217 lines: a title and a stylesheet**. It
holds no script, no element, no inline handler. What it carries is BLOCK 1 and BLOCK 2, and
that is deliberate: the CSS contract is SP5's subject, and the spec fixes it there.

| Where it lives now            | What it is                                                                                                                                                                                                                                                                                                                                      |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `design/src/engine/legacy.js` | the engine, moved byte for byte, still JavaScript on purpose                                                                                                                                                                                                                                                                                    |
| `design/index.html`           | the application shell's markup, in the document Vite owns                                                                                                                                                                                                                                                                                       |
| `design/src/states.js`        | the scenario table — a 709-line file whose fixture BODY is 656 lines (the array's interior, lines 48-703; its delimiters `const STATES = [` and `];` sit on 47 and 704). It registers **82** states, of which 74 are written out and 8 generated by a `...[…].map()` — a count by regex reads 74 and is wrong. The harness's, not the product's |
| `design/src/seams.ts`         | the three names the engine imports instead of reading off `window`                                                                                                                                                                                                                                                                              |
| `design/src/**`               | every page and every screen, as components                                                                                                                                                                                                                                                                                                      |

Every step of it was proven the same way: a state-by-state comparison of the WHOLE phone frame,
recorded before and replayed after — **0 divergence on 82 states**, _or, where the markup changed
on purpose, the rename map applied to the RECORDING and exact equality required_, which says
« every difference is a rename and nothing else ». That second half is not decoration: it is what
the claim actually covered at two of the three waves, and dropping it overstates the proof.
At each of the three SP4-fin waves, with the rule suite green at unchanged hold counts.

> **⚠ THIS PROOF IS NOT REPLAYABLE TODAY, and the formula is cited three times in this file**
> (`grep -c '0 divergence' IMPLEMENTATION.md` → 3, lines 56, 94, 106). The
> instrument, `frontend/maquette/fidelity.py`, IS committed (added in `21c54a98`, PR #447) and
> says so in its own first paragraph: « it stops being runnable the moment the legacy renderer it
> compares against is deleted. That order is the point: prove first, delete after. » Those
> renderers are gone — no `*Legacy` name is reachable from `window.__referentiel` — and the
> `--record` path needs a recording taken while the legacy still owned the page. **No recording
> is committed**, and the ones left in `/tmp` are void: 38 of the 82 state ids no longer exist
> after the English rename (#455/#456). The 82 states themselves are current — `states.js`
> registers exactly 82. Cite the figure as a proof that WAS taken, never as one that can be
> re-taken on demand.

**One item of the spec's SP4-end list was argued rather than done**, and it is open to
contest: `__go` did not move shell-side. It holds `pilotage`, a latch the engine reassigns, and
an imported binding cannot be assigned — moving it would have meant exporting a setter for a
private flag. The 656-line TABLE moved (in a 709-line file); the driving stayed. The residual behaviour debts (the
deep-entry path, the 240 ms delay on `data-next`) are named in the SP4-fin plan and belong
to their own work: none of these waves changed behaviour, by construction.

| Wave                                                  | Branch                      | PR   | What it settled                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------------------------------------------- | --------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **SP1 — dossier servi**                               | `refactor/maquette-sp1`     | #429 | The prototype became a served folder — `design/refonte.html`, images extracted as real files, `/assets/` session-gated and immutably cached (R70) — plus the operator's post-merge corrections: no inline action on a result card, and a screen layer that stacks (R71).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **SP2 — coquille Vite**                               | `refactor/maquette-sp2`     | #430 | `design/` became a Vite project as well, and R72 proved the built output renders identically to the source — mutation-verified three ways.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **Bascule — the host serves the build**               | `refactor/maquette-bascule` | #431 | `serve.py` serves `dist/index.html`, rebuilds under a lock when any input is newer, and on failure shows the build's own last words instead of a generic error (R73).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **SP3 — the router, by strangler**                    | `feat/maquette-sp3`         | #432 | React 19 + TanStack Router as the outer shell and the SINGLE writer of URL and history; the legacy engine speaks `window.__pont` (R74), and `design/` gained its own strict typecheck gate.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **SP4a — the machinery**                              | `feat/maquette-sp4a`        | #437 | `magasin` (TanStack Store) became the owner of the engine's state, the host learned to answer ANY address (SPA fallback), and `/profil/$titre` + `/ajout` landed as the first real routes (R75, R76).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **SP4b — the fiche and the panel**                    | `feat/maquette-sp4b`        | #441 | `<PanelContent>`/`<Sheet>` became the single React panel and `openSheet()` retired to a tripwire; `/fiche/$titre` landed as a real route, and scroll is now kept per HISTORY ENTRY rather than per address.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **SP4c — resolution and releases**                    | `feat/maquette-sp4c`        | #442 | `/resolution/$dossier` and `/releases/$titre` landed as real routes, `Pont.reculer(n)` killed M11's double Back, and R57's probe moved off the legacy `#screen` onto the screen's own identity.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **clean-code / i18n**                                 | `refactor/clean-code-i18n`  | #446 | No French in the code and no interface text in it either: `react-i18next` in the shell, every UI string in `fr.json`, English names across `design/src`, the harness and the two servers — and `scripts/check-no-french.py`, four arms, in `make check` and in CI, which is the half that outlives the wave.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **SP4d wave 1 — the shell owns a PAGE**               | `feat/maquette-sp4d1`       | #447 | Système, Maintenance and Configuration became final components inside the legacy `#view` through a page host (R77); R67 stopped judging a list it had not found, R60 gained a positive control, and the nine delegation attributes gained tap-driven holds. The wave's own adversarial review found a shipped defect no rule covered: the legacy removed a node React owned, tearing the root down.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **SP4d wave 2 — Arrivées**                            | `feat/maquette-sp4d2`       | #448 | The pipeline's health page became a final component, with the first migrated control that WRITES (the pilot's bar, whose three states include DOIT-4's queue). A defect of class came out of it: a harness driver mutating the engine's `state` alias in place leaves a migrated page stale, and R77 gained the source-level hold that catches it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **SP4d wave 3 — the Médiathèque, and E-001**          | `feat/maquette-sp4d3`       | #449 | The largest data surface, its infinite scroll and its search field became a component; the page host stopped supplying a root, because a page emitting four of them cannot live in one. E-001 shipped maquette-first with its own rule (R78), and a rule found 87 library sheets with no genre and no cast (B-030).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **SP4d wave 4 — Acquisition, and the last two pages** | `feat/maquette-sp4d4`       | #450 | The last page wave: `viewAcquisition` — three tabs, a deck and a second infinite scroll — plus `viewProfil` and `viewIntrouvable`. `PAGES_OF()` carries no `render` at all, which is SP4-fin's entry condition. The review found four real defects, the first of which left the page inert: every action mutates the world IN PLACE and signals with `toucher()`, and the component subscribed only to the state.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **SP4-fin wave 1 — the engine leaves the fragment**   | `refactor/maquette-sp4fin1` | #451 | The 35 052-line inline script became `design/src/engine/legacy.js`; the fragment fell from 39 561 to 4 507 lines and holds nothing executable. 0 divergence on 82 states. The engine republishes its 254 top-level names — 230 by value, 24 by getter, the split measured — because the harness drives it by bare name. Four rules had gone green over a file emptied of their subject; `common.py` now owns `DESIGN_SOURCES`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **SP4-fin wave 2 — the markup leaves the fragment**   | `refactor/maquette-sp4fin2` | #452 | The 287 lines of application shell move to `index.html` — not into React, because the engine captures its containers at module evaluation, before React has rendered anything. **The fragment is now a title and a stylesheet.** The login gate, built from both files now, is byte-identical. Two more readers had to follow the markup; R72 needed no renegotiation, measured.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **SP4-fin wave 3 — the bridge dies**                  | `refactor/maquette-sp4fin3` | #453 | The 656-line scenario fixture leaves the product for `src/states.js`; the state ALIAS dies (99 reads go to the store, and a whole defect class goes with it); 61 seam call sites become imports through live `export let` bindings, so a typo fails the build. R74 renegotiated — what it called a bridge is now a driving surface for measurement; R72 needed nothing, measured.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **English names — no French left in the code**        | `refactor/english-names`    | #455 | The operator named two examples (`data-suivante`, `trierLib`) and both were real: 141 of the engine's 446 declared names were French, and nineteen `data-*` contracts. Everything moved, including the seams three frozen-with-reason entries had been protecting (`pont`/`ecrans`/`panneau` → `bridge`/`screens`/`panel`) and the `data-key` values on both sides. `scripts/code-vocabulary.txt` turns the detector's question around — « is this word one we use? » has no holes by construction. The guarantor pass before merge found five things the green gate could not see: a vocabulary SEEDED from the code had licensed the 25 French words it existed to catch (declared debt now, bounded to the dying engine by `check_french_debt`); `data-*` names had a rule and no arm; `frontend/scripts/` was outside every scope; the production app still carried a `controle/` directory and 19 French names; and the renaming tool was silently rewriting interface copy through four forms it did not know — it reads its protected spans from TypeScript's own parser now. |
| **Values, routes and parameters**                     | `fix/design-restart`        | #456 | The operator lifts the freeze that had been protecting a French address: a route and a parameter are NAMES, not data. The state vocabulary goes English from the backend to the stylesheet (nothing was persisted, so no migration), and the routes follow in the prototype AND in production — the three French addresses answering as redirects, because a rename that 404s the very address it renames is breakage in disguise. The renaming tool paid three defects of one kind — a UTF-16 offset, `regions()` which is a JavaScript scanner, and a values mode so wide it rewrote 429 lines of prose before being rebuilt on the right criterion: the whole string, never the word. The design host now restarts when its code changes, the asymmetry that had locked the operator out.                                                                                                                                                                                                                                                                                         |

The full record of each wave, in the words written when it landed, is in
`docs/superpowers/shell-mobile-wave-log.md`; the per-wave plans are in `docs/superpowers/plans/`.

### The latest wave, in full

**SP4-fin wave 3 — the bridge dies, and the fixture leaves the product**: Branch `refactor/maquette-sp4fin3`, version 0.97.24. Four things the spec named for SP4-end,
each proven at **0 divergence on 82 states** (with the rename-map disjunction, and the
replayability caveat, both recorded above).

### The scenario table was never the engine's

`STATES` — **656 lines of FIXTURE** — was carried by the product so that something outside it
could measure the product. It is `src/states.js` now, importing by name the eighteen engine
names its entries call, which the engine EXPORTS explicitly rather than being reached through a
global.

**What did not move is the driving, and that is an arbitrage rather than an oversight.** `__go`
closes the harness panel, unmasks three overlays, resets the world unless asked not to, and
holds `pilotage` — a latch the engine REASSIGNS. An imported binding cannot be assigned, so
moving `__go` out would have meant exporting a setter for a private flag: one indirection
traded for a worse one. The engine keeps the mechanics and looks the state up in the table this
module REGISTERS with it — in that direction, so the engine never depends on the module that
measures it. An empty table is a legitimate state (a document with no driver cannot be driven)
and `__go` says so by name.

### The state alias is gone, and with it a whole class

`let state` was re-pointed at the store's object on every notification: a CACHED COPY, correct
only for as long as the subscriber refreshing it kept up. All 99 reads go through
`currentState()`, which reads the store. The seed became `INITIAL_STATE`, used once at boot; the
subscriber — whose entire body was the refresh — is deleted; `window.state` became a live read.

What that removes is a class, not an instance: a rule could drive a page by mutating the cached
object, and R77 had to hold that none did. With no cached object there is nothing to mutate.

### The seam is an import, and what that buys is narrower than it sounds

61 call sites — `panneau` 40, `ecrans` 14, `pont` 7 — stop going through `window` and import
from `src/seams.ts`. The exports are `let`, deliberately: the implementations need the store,
which the shell creates in its BODY, after its imports, and the engine is one of them. An ES
export is a LIVE BINDING, so the shell fills them at boot and the engine reads them at call
time, which is the only time it calls.

**Stated plainly, because it is easy to oversell**: the engine is JavaScript `tsc` does not
check, so this is not type safety at the call sites. What it is — a declared dependency, and a
name the BUNDLER resolves. Exercised: renaming one import to `pnot` fails the build.

**And the globals do not disappear**, for a measured reason rather than a tidy one: this harness
drives through them — `__screens` nine times, `__panel` eight, `__bridge` twice (the three were
still named `__ecrans`/`__panneau`/`__pont` here long after #455 renamed them). They are the
same objects the shell fills the imports with, so the two ways cannot disagree.

### R74 renegotiated, R72 not — and both by measurement

R74's subject changed meaning: what it called « the bridge » was three globals bridging a
classic script to a module world, and that world is gone. It now describes a DRIVING SURFACE for
measurement. Recorded in `regions.json`. R72 needed nothing at all, measured rather than assumed:
the fragment is still injected verbatim, exactly once.

### Two errors of mine, and one of them killed the page

The blanket rewrite of `state.` landed in PROSE in four comments. Found with a scanner that
tracks comment / string / template-interpolation context properly — which also showed that the
six occurrences it flagged « in strings » were `${…}` interpolations, i.e. code.

Worse: the edit to the publication block **never ran**. Its command was issued in a shell whose
`cd` had failed, and I read the un-edited line in a later grep without registering it. The result
was `state: { get: () => state }` with the binding removed — so the name resolved to
`window.state`, i.e. to that getter, and the page died at load with « Maximum call stack size
exceeded ». **A failed command is not a no-op; it is an edit that did not happen, and the next
read must be treated as evidence rather than scenery.** The reason is written at the exact line.

---

## Where to start

**`BUGS.md` at the repo root is the bug register.** Every defect the operator reports is written
there when it is reported, one is closed at a time, and a fix closes only with a mutation-tested
rule that covers the path the operator actually walks. Read it before starting anything. Closed
entries keep their full history in `BUGS-CLOSED.md`, indexed from `BUGS.md`.

Read, in this order:

1. `frontend/maquette/README.md` — the prototype's contract, its named states, the rule set,
   and the traps already paid for. It is short and it saves days.
2. `docs/superpowers/specs/2026-08-10-refonte-mobile-quatre-pages-design.md` — §7 carries the
   method. Its §8 phases describe deriving the app surface by surface, which is the order the
   mission reversed: read them as history, not as instructions.
3. `BUGS.md` — what is reported and not yet confirmed.

**Serve the prototype locally.** There are TWO hosts and the harness measures only one of
them — running the wrong one is a green run over nothing.

|                  | Port     | What                                                                                                                                                | Started by                 |
| ---------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| **Harness host** | **8899** | `harness/server.py --serve`, rooted in `/private/tmp/tm-refonte`, serving a COPY of the build at `/` and folding every router-owned address onto it | `run.sh`, or by hand       |
| **Design host**  | **8712** | `serve.py`, scrypt password-protected (`tm-design.iznogoudatall.xyz`)                                                                               | PM2 (`torrentmate-design`) |

`harness/common.py` pins the first one: `PROTOTYPE = "http://127.0.0.1:8899/"`.
Never 8710/8711/8712/8899 for a server of your own — `harness/server.py`'s `RESERVED_PORTS`
names all four, and the reverse proxy routes the first three to production, staging and the
design host.

**`python3 serve.py 8899` is wrong**, and it is the recipe this file used to carry: `serve.py`
is the DESIGN host, it answers **401** without a session, and the harness would then measure the
sign-in screen — every rule green, nothing measured.

**A plain `python3 -m http.server` is wrong too, and that one is newer.** It was right while a
page lived in the query: the document had one address, `/wrapped.html`, and a static server
serves a file at its own path. Since L05 a page sits on a real path, and a plain server answers
404 to every one of them — which the router renders as its not-found page, so the whole suite
would measure that instead of whatever was under test. `harness/server.py --serve` folds any
address with no file behind it onto the document, and keeps a 404 for the resources that really
are files (`/vite/…`, `/assets/…`, `/sw.js`, `/manifest.webmanifest`). What has not changed is
where it is ROOTED: on the copy of the BUILD, never on `design/`, which would serve unbuilt
TypeScript and measure nothing real.

```bash
# 1. Rebuild, and refresh the copy the harness reads — BEFORE EVERY RUN.
cd frontend/maquette/design
npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets

# 2. The harness host — check before starting, it is usually already running.
lsof -nP -iTCP:8899 -sTCP:LISTEN || (python3 frontend/maquette/harness/server.py --serve 8899 /tmp/tm-refonte &)
```

Two traps, each paid for twice. A STALE COPY of the rule scripts can end up in
`/tmp/tm-refonte`, and running those measures the previous version — there is none there today
(`ls /tmp/tm-refonte` → `assets`, `server.log`, `vite/`, `wrapped.html`), so this is a warning
about what to check, not a description of what is there. And a `wrapped.html` that was not
re-copied measures the previous build.

The prototype needs a wrapper supplying a viewport meta; the harness scripts build one. Without
it Chrome falls back to the legacy 980px layout viewport and every measurement is wrong.

**Run the harness.** The project's own `python3` (3.12.4, Playwright 1.62.0) carries Playwright;
the hardcoded 3.11.9 path this file used to require is no longer needed (PM2 keeps it for
`serve.py`).

```bash
cd frontend/maquette/harness
for s in *.py; do
  [ "$s" = common.py ] && continue   # the shared plumbing, not a rule
  python3 "$s" > /dev/null || echo "FAILED: $s"
done
```

Every script fails through its exit code, not through its output. A script that only prints
cannot fail, and a script that cannot fail is a report nobody is obliged to read.

**Two traps, each already paid for twice.** A stale copy of the scripts lives in
`/tmp/tm-refonte`; running from there measures the previous version. And `/tmp/tm-refonte/
wrapped.html` — the harness's copy of the BUILD, the same document the host serves — must be
rebuilt and re-copied before every run, or the same thing happens one level down:

```bash
cd frontend/maquette/design
npm run build
cp dist/index.html /tmp/tm-refonte/wrapped.html
rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
ln -sfn "$(git rev-parse --show-toplevel)/frontend/maquette/design/assets" /tmp/tm-refonte/assets
```

`pwa.py` measures the LIVE host `tm-design.iznogoudatall.xyz`, not the local server. After
editing `serve.py`: `pm2 restart torrentmate-design`.

---

## THE OBJECTIVE — what the maquette is, in one paragraph

**The maquette is the next version of the frontend, and it will REPLACE the current one.** On
switchover day `frontend/src` is ARCHIVED and `frontend/maquette/` takes its place. Nothing is
transposed, translated or merged surface by surface — which is why every page and every
MECHANISM the shipped app has must eventually exist here: afterwards there is nothing left to
take from it. The backend is adapted to what this interface needs, and that work comes after the
interface is frozen.

### What is done, and what remains — measured 2026-08-20

Read this table instead of counting surfaces. **The pages are the part that is finished**; what
remains is most of what makes an application.

|                      | Production                                           | Maquette                                                                                                                                                            |
| -------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API modules          | **11** (`frontend/src/api/*.ts`)                     | **0**                                                                                                                                                               |
| Network calls        | **65** `apiFetch` · 36 `useQuery` · 21 `useMutation` | **1** — and it is a LOGOUT (`legacy.js:11243`, `/logout` on the design host). **Zero data** reaches the maquette from a backend                                     |
| WebSocket            | **24** files                                         | **0**                                                                                                                                                               |
| Service worker / PWA | yes                                                  | no                                                                                                                                                                  |
| Pages drawn          | 9                                                    | 9 + 5 screens — **not the same nine**: `/control` and `/pipeline` have no maquette page (owed, see REMAINS), and `host` + `arrivals` have no production counterpart |

Commands — and the maquette's needs `--include='*.js'` too, because its single call lives in
the legacy engine, a `.js` file the other two globs walk straight past (an adversarial review
ran the command as first written and got 0):

```bash
grep -rhoE '\b(fetch|apiFetch|useQuery|useMutation)\(' \
  --include='*.ts' --include='*.tsx' --include='*.js' frontend/src | sort | uniq -c
grep -rlE 'WebSocket' --include='*.ts' --include='*.tsx' --include='*.js' frontend/src | wc -l
# then the same two over frontend/maquette/design/src
```

**DONE** — 8 pages and 5 screens as final components; TanStack routing with the URL carrying the
state; 82 named states driving 50 rule scripts over 80 recorded rules; the engine moved out of
the fragment (which is now a title and a stylesheet); English names throughout with the shell's
copy in i18n resources; colour and elevation tokenised — **186 of 188** `color:` declarations (`(?<![-\w])color\s*:`; a `\bcolor` regex reads 203/206 because `-` is a non-word character and `background-color` matches it), and the 55 raw values left in BLOCK 2 are all token DECLARATIONS, which is where they belong.

**REMAINS** — the four subjects, and this list is NOT an order.

> ⚠ **The order is `docs/reference/frontend-architecture.md`'s thirteen lots, and nothing else.**
> This list used to open « in the order the work actually has to happen », and that sentence
> survived #466 by four days while naming an order that file had replaced. Read as an order it
> sends the next session to draw `/control` or to open the visual language — and the visual
> language is lot **L06**, which `depends on L01` under a Phase 0 that says « Nothing else may
> start ». **Which lot comes next is § « Where the frontend work stands », at the top of this
> file.**

1. **The two pages the mission re-opened** — `/control` (8 panels) and `/pipeline` (10 panels).
2. **The visual language (SP5b)** — type, radius and spacing have no scale at all: 21 distinct
   font sizes for 150 declarations, 16 radii, 64 padding values for 112 declarations, and three
   spellings of one pill (`99px` ×25, `9999px` ×11, `50%` ×1).
3. **The size of the gap the SWITCHOVER closes — not work the maquette does now.** The table
   above measures it: 11 API modules against 0, 65 network calls against one logout. But
   **while the maquette is a maquette it is NOT connected to the backend** (operator,
   2026-08-20), and that is deliberate, not a lag: fixtures are what make 82 named states
   drivable and 50 rules deterministic. A prototype wired to live data measures the data, not
   the design. The wiring belongs to the switchover, with the backend adapted to what the
   frozen interface needs. What the table is FOR is honesty about the distance: no document
   stated it before 2026-08-20 — they counted surfaces, and surfaces were never the hard part.
4. **The legacy engine** — 34 626 lines still driving, `__go` shell-side, the 240 ms delay on
   `data-next`, and `/login` + the splash still engine-driven markup rather than components.
   **79 % of those lines are FIXTURES** — `SHEETS_RAW` alone is 20 538 — so the engine's own code
   is about 6 949 lines, and most of the rest stops existing when real data arrives. That is why
   items 3 and 4 are interleaved surface by surface rather than run one after the other.
   <sub>method: bracket-match every `const X = [` / `const X = {` in `legacy.js` and sum the spans over 100 lines</sub>
5. **BLOCK 1 must stop shipping at switchover.** `refonte.html` is split into BLOCK 1 (the
   prototype harness — phone frame, demo bars, design notes) and BLOCK 2 (the application). The
   maquette's own build carries BOTH today, which is right for a prototype and wrong for the
   app. `harness/export.py` used to guard that boundary from the extraction's side and went with
   it; nothing guards it now.

**Items 2 to 5 above are planned in `docs/reference/frontend-architecture.md`** — the settled
architecture decisions and the ordered lots that reach them, each with its dependencies and its
definition of done. (Item 5 is held by its lot L07: BLOCK 1 is deleted rather than converted, and
its disappearance is part of that lot's proof.) That file says what must become true and in what
order; **this section stays the only place that says where the work stands.** Item 1 is
deliberately outside it: those two pages are surfaces to be drawn, and the existing method
covers them.

### THE MISSION — dictated by the operator, 2026-08-19

**The maquette is a NEW VERSION of the app, and EVERY screen is to be redrawn. All of them.**
It is not a reskin of the shipped surfaces and it is not bounded by what production has today.
Its purpose is a new, COHERENT user experience, and the first objective is to **freeze that
interface**.

- **No surface is out of scope.** A production screen with no page here is a page still to be
  drawn, never an arbitration to leave it out.
- **What the maquette already holds is VALIDATED** by the operator. Do not relitigate it.
- **What remains is not only pages**: the UX, the interaction language and the prototype's
  ARCHITECTURE all have to be finished and consolidated before the interface is frozen.
- **The backend follows the interface.** The engine will be adapted to what the new interface
  needs, and that work comes AFTER the freeze. A backend limitation is therefore never a reason
  to draw less — record it, and draw what the experience requires.

**This supersedes the `Gone | Contrôle` ruling below.** Read the section that follows as the UX
argument for WHERE those panels belong — that argument stands — and never as a licence to leave
`/control` or `/pipeline` undrawn. The operator overturned that exemption on 2026-08-19.

---

## What the v1 still owes, page by page

Read from the shipped router (`frontend/src/router.tsx`) and the shipped nav model
(`frontend/src/components/layout/nav.ts`) against the prototype's named states.

Two of production's routes are already redirects and owe nothing: `/scraping` → `/media`,
`/registry` → `/systeme`. A third, `/maintenance`, is **also** a redirect — `MaintenanceRunRedirect`
sends it to `/systeme?tab=journal`, or to `/pipeline?run=…` when it carries a run. The page it
names has not existed for some time; its panels live on `/systeme`.

### The v1's structure, and it is settled

The prototype's four tabs and production's four do not agree: production's bar is
`Acquisition · Médias · Pipeline · Contrôle`, the prototype's is
`Acquisition · Médiathèque · Arrivées · Système`. The disagreement was arbitrated by the
operator rather than split down the middle, and the arbitration replaced the question:

> **The cut is by the NATURE OF THE TROUBLE.** A medium in trouble is Arrivées. A machine in
> trouble is Système. A setting is Configuration. A command run against the library is
> Maintenance.

That axis is the reason the panels can be placed at all. Production's `/controle` has no axis —
it stacks blocked media (`ToHandleList`) on top of disk and provider health (`CompactHealth`)
with nothing saying why they share a page. **So `Contrôle` does not survive AS IT IS**: its
eight panels each have a home under the rule — `ToHandleList`, `ScrapeActivityPanel`,
`LastRunDigest`, `StalledPanel`, `AcquisitionSummaryCard`, `SchedulersPanel`, `CompactHealth`,
`PipelineControls`, read from `frontend/src/pages/Dashboard.tsx`.

> ⚠ **Amended 2026-08-19.** This paragraph used to conclude « none of those homes is a new
> page », and that was read as « `/control` and `/pipeline` are deliberately page-less ». The
> operator has overturned that: every screen is redrawn, these two included. What survives here
> is the PLACEMENT argument — a medium in trouble is Arrivées, a machine in trouble is Système —
> not an exemption from being drawn.

|         |                                                                                         |
| ------- | --------------------------------------------------------------------------------------- |
| Bar     | `Acquisition · Médiathèque · Arrivées · Système` — unchanged                            |
| Off-bar | `Maintenance` · `Configuration`, reached from Système and from the drawer               |
| Redrawn | `Contrôle` — its panels are placed by the rule above, and the page is OWED (2026-08-19) |

Where every shipped panel lands. The first block places itself; the second was arbitrated;
the third is derived from the rule rather than asked again.

| Shipped panel                                         | Home            | Why                                                                                                                                                                               |
| ----------------------------------------------------- | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ToHandleList` — blocked staged media                 | **Arrivées**    | a medium in trouble                                                                                                                                                               |
| `ScrapeActivityPanel`                                 | **Arrivées**    | a medium being identified                                                                                                                                                         |
| `RecentResolutions`                                   | **Arrivées**    | a medium just unblocked                                                                                                                                                           |
| `FlowBoard` — the eight stages                        | **Arrivées**    | the pipeline's health is where its media are                                                                                                                                      |
| `CompactHealth` — disks, index, Redis, providers      | **Système**     | a machine in trouble                                                                                                                                                              |
| `ActionCatalog`, index repairs, `DestructiveLogPanel` | **Maintenance** | commands run against the library                                                                                                                                                  |
| `PipelineControls` + `PipelineActionBanner`           | **Arrivées**    | DOIT-3 — act where one observes. The blocked stage and the button to relaunch it are one glance                                                                                   |
| `RunHistoryTable` · `RunDetail` · `RunLogFeed`        | **Système**     | « succès d'exécution » and « logs ». Arrivées keeps the PRESENT — what is stuck, what arrived in 24 h — and never becomes an archive                                              |
| `AcquisitionSummaryCard`                              | **Acquisition** | the tab already shows it in full; it does not owe a second, shorter copy                                                                                                          |
| `SchedulersPanel`                                     | **Système**     | did it fire, did it succeed. Its HOUR is a setting and lives in Configuration — the schedule and its health are two objects that share a name                                     |
| `LastRunDigest` — « X détectés, Y récupérés »         | **Arrivées**    | a count of media, not of executions. The run's _history_ is Système's; the last run's _result_ is the story of what arrived                                                       |
| `StalledPanel` — per-step reasons                     | **split**       | a torrent deferred for ratio is a medium (Arrivées); a step that raised is code (Système). The operator's rule is explicit: no blocked medium in Système, but its code errors yes |

### The surfaces drawn so far — and the two the operator has since re-opened

**Every row below is drawn and VALIDATED.** What this table is NOT is a statement that the
surface inventory is closed: since 2026-08-19 the mission is that every screen is redrawn, so
`/control` and `/pipeline` — production tabs with no page here — are **owed**, and this table
does not yet list them.

| Surface                                                                       | State                                                                                                                            | Rule                       |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `/login`, `/acquisition`, `/media`, `/config`, `/media/:provider/:providerId` | drawn before this                                                                                                                | R49–R63                    |
| **Arrivées**                                                                  | **drawn** — the pilot's bar, the nine steps of the last real run, its digest, and « arrivé dans les 24 h »                       | R66, `harness/arrivals.py` |
| **Système**                                                                   | **drawn** — the deferral is lifted. PM2 services, schedulers, the pipeline's executions, disks, index, dependencies, code errors | R67, `harness/machine.py`  |
| **Maintenance**                                                               | **drawn** — six rubrics over the engine's 26 real `library-*` commands, plus the destructive journal                             | R67                        |
| **Configuration**                                                             | **extended** — a seventh rubric, « Les passages programmés », over the six real cron schedules                                   | R60 extended               |
| `*` (NotFound)                                                                | **drawn** — and it closed a crash: an unknown id used to stop the whole frame on a TypeError                                     | R68, `harness/address.py`  |
| multi-user account                                                            | **drawn** — the one real account, its session read from `web.json5`, and the place of the others marked EMPTY                    | R68                        |

Every figure on these surfaces is read from the live system — `pipeline_run`, `pm2 jlist`, `df`,
`library.db`, the maintenance registry, `web.json5`, `ecosystem.config.js`. Four of the rules go
back to those sources AT RUN TIME rather than comparing against a number written beside them: R66
against `pipeline_run` by run_uid, R67 against `pm2 jlist` and the maintenance registry in both
directions, R68 against `web.json5`.

---

## The third axis: what the prototype owes as an APPLICATION

The operator's judgement is on the design **and** the front-end architecture. The design is
measured by 50 rule scripts (`ls frontend/maquette/harness/*.py` → 52, minus `common.py`, which
is shared plumbing). `regions.json`'s `$adversarialReview` records **80** numbered rules — but
**16 of them are named in no harness script at all** (R18, R19, R21, R24, R25, R32-R40, R49,
R58), so at most 64 are executable. « 80 rules » is an inventory, never a coverage figure;
the architecture was measured by nothing.

**EVERY FIGURE BELOW CARRIES ITS DATE AND ITS COMMAND, and that is the point of the column.**
The version of this table dated 2026-08-16 was taken before the single file was split, and by
2026-08-19 not one of its eight rows was still true — yet it was captioned « Today » and was
read as current for three days. Worse, two of its numbers (« 83 » and « 265 ») could not be
reproduced by any command anyone could name. Re-measure before citing; if a row's command no
longer produces its number, the row is stale, not the code.

All commands run from `frontend/maquette/design/src`, over `*.js`, `*.ts` and `*.tsx`.

| Measure                              | 2026-08-19                   | Command                                                                                                                                                                                      | 2026-08-16                             |
| ------------------------------------ | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| lines of code                        | **42 176**                   | `find . -name '*.js' -o -name '*.ts' -o -name '*.tsx' \| xargs wc -l`                                                                                                                        | 41 400                                 |
| hardcoded data sets                  | **54** array literals        | `grep -rEho '^\s*(const\|let\|var)\s+\w+\s*(:[^=]*)?=\s*\[' --include='*.js' --include='*.ts' --include='*.tsx' . \| wc -l`                                                                  | « 83 », by no known command            |
| network calls                        | **1**                        | `grep -rEo '\b(fetch\|XMLHttpRequest\|axios)\s*\(' … \| wc -l`                                                                                                                               | 1                                      |
| direct `state.` accesses             | **142**                      | `grep -ro '\bstate\.' … \| wc -l`                                                                                                                                                            | « 265 », by no known command           |
| `currentState()` calls               | **99**                       | `grep -ro 'currentState()' … \| wc -l`                                                                                                                                                       | not measured (the alias still existed) |
| `render()`                           | 1 defined, **67** bare calls | `grep -rEo '(^\|[^.\w])render\(\)' … \| wc -l`                                                                                                                                               | 1 defined, 47 calls                    |
| named `window.__` seams              | **26** distinct              | `grep -rEoh 'window\.__[A-Za-z0-9_]+' … \| sort -u \| wc -l` — the `-h` is load-bearing: without it `grep -r` prefixes each match with its file name and `sort -u` counts 56 file/name PAIRS | 11                                     |
| `history.pushState` / `replaceState` | **1 / 0**                    | `grep -rEo 'history\.(pushState\|replaceState)' …`                                                                                                                                           | 5 / 3                                  |
| reads of browser `location`          | **6**                        | `grep -rEon '(window\.)?location\.[a-zA-Z]+' …`, minus TanStack's own `history.location` / `location.state`                                                                                  | 3                                      |

Two of those moves are explained rather than mysterious: `pushState` fell to 1 because SP3 made
the router the single writer of history, and `state.` fell from 265 to 142 because SP4-fin wave 3
killed the alias — the reads did not disappear, 99 of them became `currentState()`.

None of these numbers is a defect **of the prototype**: a single dependency-free file is
exactly what made it verifiable. They are the **seams** the binding will have to open.

### The three questions, and what they are worth now

**1. Where does a piece of data come in?** 54 array literals by the command in the table above (2026-08-19), against « 83 » claimed on 2026-08-16 by no command anyone can name — the figure depends entirely on what the regex counts, so cite the command with it or do not cite it. What matters is not the count: the number rose across the drawing waves and the
situation improved, which is only apparently contradictory: every new constant is read from a
living source named in its comment — `pipeline_run`, `pm2 jlist`, `df`, `library.db`, the
maintenance registry, `web.json5`, `ecosystem.config.js` — and **four rules go back to those
sources at run time** instead of comparing against a number written beside them. R66 checks the
run by its `run_uid`, R67 counts processes against `pm2 jlist` and commands against the engine's
registry in both directions, R68 reads `web.json5`, R63 reads `acquire.db`.

That is the answer to the question, and it is executable: **a constant whose value is verified
against its source is a named seam; a constant nothing verifies is a coupling.** R63 demonstrated
it on its own by failing when the scheduler ran — a rule that fails with TIME does not signal a
defect, it points at a seam. The triage remains to be done: how many of those constants are
verified against their source, and how many are a coupling.

**It fell again the same day**, a few hours later: the 15:20 run pushed Silo from 9 to 11. Twice
in one session, without a single line of the prototype being touched. That is no longer an
illustration of the question, it is its answer: **those constants cannot be maintained by hand,
and the binding has no choice but to wire them.**

**2. Who owns the state?** Nobody — **142** direct `state.` accesses plus **99**
`currentState()` calls (2026-08-19), against 265 measured on 2026-08-16. **Read that fall as a
RENAME, not as progress**: SP4-fin wave 3 killed the `state` alias, so the reads moved to
`currentState()` rather than going away. Nothing moved on the ownership front and that is
deliberate: splitting the state requires splitting the file, and a single file is exactly what
made the rule suite writable. **This is the question that remains whole**, and the only one of
the three that cannot be settled without first deciding how the prototype gets split.

One thing was still learned crossing it: `state.pipe` **leaked** from one named state to the
next, so the same id did not render the same thing depending on the path taken to reach it. R10
found it. That is the exact cost of ownerless state, and the counter-measure fits in one
sentence: **every named state names ALL of its dials**, as it already named its page and its
phase.

**3. Where does a route live?** It used to live in `state.page`, and the URL did not carry it.
**That is settled.** The measurement that said so was final: `history.pushState` four times,
`location` read **zero** times — the interface told the browser where it was and never asked it.
That was not a debt to hand over, it was a **non-conformity with DOIT-10**, and it showed: a
reload fell back onto the opening page, and no screen could be sent to anyone.

The state travels in the QUERY, not in the path, and that is a decision: this document opens
from a static server, from the prototype host, and from `file://`, and path-based routing
requires a server that rewrites every unknown path to the document — two of those three cannot.
The binding will map `?page=lib` onto production's `/media`; what is judged now is that the URL
and the interface never contradict each other. R69, `harness/url_state.py`.

---

**Next action:** two things are owed and they are of different kinds:

1. **The surfaces the mission re-opened** — `/control` and `/pipeline` have no page here, and
   since 2026-08-19 that is a gap, not an arbitration. Drawing them is maquette-first work:
   drawn, named states, a rule that bites, a mutation that proves it.
2. **The visual language, the application and the legacy engine** — including the three
   questions of this section. **Their scope is written**: `docs/reference/frontend-architecture.md`
   carries the settled decisions and the ordered lots, each with its dependencies and its
   definition of done. Take the first lot that is not `LANDED` and whose dependencies are.
   One consequence was already recorded in the SP4-fin plan and still holds: `refonte.html` is
   on its way out — BLOCK 2 becomes a stylesheet of the maquette's own Vite project, and BLOCK 1
   goes with the harness.

> This paragraph read « frame the remaining work with the operator … SP5 has no written scope:
> it is to be agreed before any code » until that scope was agreed and written. Left as it was,
> it sent a session that had just been told where to start back to asking where to start.

Every surface listed in the inventory above IS drawn and validated — `harness/arrivals.py` (R66)
executes green against `library.db` for the most recent one — so nothing there is to be redone.

**This line used to say « draw the missing surfaces — Arrivées first », and that was wrong from
the day it was written.** It and the inventory that contradicts it landed in the SAME commit
(`c49e7ada`): inside that one commit Arrivées was already marked **drawn** while this paragraph
asked for it to be drawn. The contradiction was original, not drift — so « the lower line is
older » is not an argument, and `git blame` refutes it. Whoever reads a conflict here again:
the inventory is the one carrying material proof (a page component, a rule, an executed run).

Note that question 3 was not only architecture: **DOIT-10 requires every detail to have its
URL**, and the prototype's routes used to live in `state.page` alone. That non-conformity is
closed — the URL carries the state in its query, held by R69; what the binding still owes is the
mapping onto production's paths.

---

## What the prototype already settles

These were argued, measured and recorded. Re-opening one costs a day; the reasons are in
`frontend/maquette/regions.json` → `$adversarialReview` (**80** R-entries as of 2026-08-19, « 65 » before) and, nested inside it, `$methodLessons` (**43**, « 37 » before).

- **The prototype is the reference.** A divergence between the app and it is a defect in the app,
  unless the prototype was amended first with the reason written down.
- **The CSS is the maquette's own — RETIRED 2026-08-20.** This entry used to read « CSS is
  extracted, never retyped », then « SP5's target, not today's state ». Both are void: the
  extraction, the `.tm` scoping, the 461-entry allowlist and the rendering-parity probe existed
  so the SHIPPED app could be migrated towards the maquette surface by surface, and the maquette
  REPLACES the app. BLOCK 2 of `refonte.html` IS the application's stylesheet; nothing lifts it
  or copies it. `scripts/check-css-tokens.py` holds what still matters — every `var()` in
  BLOCK 2 resolves inside BLOCK 2.
- **Every gesture answers a pointer** — and a finger is read from the stream the compositor does
  not cancel. A gesture living inside the scrollport reads touch events; one that can claim its
  axis in `touch-action` keeps the pointer path.
- **Episode presence is read, never inferred.** A `number <= owned count` threshold assumes the
  hole is at the end of a season; it is false for 35 series in this library.
- **A trailer always opens YouTube**, never in-app playback, wherever one arrives from.
- **One back control**, in the flow, on every screen that has one.
- **One card, one behaviour.** The poster opens the media sheet, the card body opens the bottom
  panel, a gallery tile answers a long press. The panel carries EVERY action for that medium;
  an inline button is a shortcut, never the only way in. The panel is derived from what is true
  about the medium, so the one reached from a gallery equals the one reached from a card.
- **One builder per shape, not per screen** — and none of them takes markup. `cardHTML` for every
  list, `tileHTML` for every gallery, `panneauHTML` for every bottom panel, a separate builder
  for a release candidate (not a medium: no sheet, no panel). Each takes a descriptor of FACTS;
  a view wanting something outside it adds the fact rather than passing markup.
- **One season rendering**, within a sheet and across sheets.
- **Identify is not follow.** Resolving a stuck folder associates a medium so the pipeline
  finishes; it never creates a follow.

## Method lessons that cost the most

- **A screenshot fingerprint is not an oracle.** Two captures of the same unmodified file diverge
  on 8 to 15 of the states. Use bounding rects plus a computed-style subset.
- **A synthetic event is not a finger.** It is never cancelled, so it cannot tell whether a
  gesture survives the compositor. Two gestures were lost that way and no script noticed.
- **A rule that never bit proves nothing.** Every rule added is mutation-tested: break the
  behaviour on purpose, confirm the rule falls and names the right defect, restore.
- **A derivation must not read back its own output.** The list poster was sized against the
  median card and now sets it, so the computation returns its own answer.
- **A rule can assert the DEFECT.** R53 did, twice, in both directions: it first certified a
  startup screen that flashed for one frame, then demanded a floor that made the bar play twice.
  Writing down the behaviour that exists is not the same as writing down the one that is wanted.
- **« It cannot affect production » is a measurement, not an argument.** The prototype was proved
  harmless by building the bundle on both sides and comparing — and the first comparison said no:
  Tailwind v4 scans from the project root, took six words out of `refonte.html` for utilities, and
  shipped 936 bytes of them to production. The design host's icons, sitting in `frontend/public/`,
  shipped another 56 kB the same way.

---

## Carried, not hidden

1. **Plex deletion.** `api/plex.py` only refreshes. Which route removes an entry on this server is
   a verification step of the binding mission, not a claim of this one.
2. **A real deletion cannot be validated before production.** Staging writes to the real disks and
   the real databases, and fabricating a medium for the proof is forbidden. Protocol: dry-run only
   on staging; the first real deletion happens after the production merge, on a medium the
   operator names, after a genuine `sqlite3 .backup` — a file copy of a WAL database is not a
   backup.
3. **The multi-user account system** is a later mission. The user menu draws its place — profile
   and preferences, disabled, saying why — so the shape is settled before the feature lands.
4. **`?tab=maintenant`.** The label became « En cours »; whether the URL param migrates with a
   legacy redirect or stays is decided when the prototype is bound to the backend. The deep link
   must keep working either way, and the prototype has to DRAW what a legacy link lands on.
5. ~~**The list poster cannot be enlarged by its own derivation.**~~ **Closed**, and the question
   was replaced rather than answered: the poster is no longer a fraction of anything, it reaches
   the card's edges. 84px wide, with the card's height as its floor, so a card at that floor
   gives an exact 2:3 and its artwork is untouched. What remains named in R47 is the limit —
   full height and the 2:3 ratio cannot both hold on a taller card, so cropping is bounded.
6. ~~**The design host and the app share their icons.**~~ **Closed.** The design host carries a
   yellow-ringed set of its own, generated from staging's shape by
   `frontend/scripts/make-design-icons.py`.
7. **The arbitration SCREEN itself is drawn but not built.** `ds/DecisionRow` and the vocabulary
   are derived; the screen's own shape — one folder at a time, the three ways out side by side,
   the progression replacing the desktop deck's keyboard shortcuts — belongs to the Arrivées
   screen the prototype already draws — what is missing is the app, and the app comes after the
   operator's judgement.
8. **The synopsis is not in the read-model.** The library's rows carry it in the prototype, read
   from the `<plot>` of each medium's own NFO — real data, but `library.db` has neither a column
   of `media_item` nor a key of `item_attribute` for it. The app cannot render this surface until
   the read-model grows the field, and the scan that fills it. Nine of 349 titles have no plot at
   all, and those must show nothing rather than a filler.
9. ~~**Editing a setting is drawn only as far as the panel.**~~ **Closed.** Five fields, one
   refusal and one state that crosses them, each derived from the setting's VALUE rather than
   from a list of keys. R60 extended, `harness/settings.py` — 42 checks, eight named states, one
   per field.
10. **Five tokens the app will owe.** The design-system lint found nine hardcoded colours in the
    prototype — a real C19 violation, and one of them (`var(--warning, #d97706)`) was the B-014
    shape again: a fallback onto a token that IS defined, which is a landmine that has not gone
    off. They are tokens now: `--mq-shadow-toast`, `--mq-shadow-pop`, `--mq-shadow-card`,
    `--mq-shadow-badge`, `--mq-scrim-soft`, `--mq-tile-overlay`. Their VALUES live in the
    prototype's own palette. ⚠ **Amended 2026-08-20 (SP5a):** that palette sat in BLOCK 1 and
    was therefore NOT exported, so the generated stylesheet named these tokens and defined
    none of them — thirty-five used, one declared, across 458 `var()` calls. The palette has
    moved into BLOCK 2, where the application's rules can see it, and
    `scripts/check-css-tokens.py` refuses the next `var()` with no declaration. The sentence that stood here — « when the app adopts
    that stylesheet, `tokens/maquette.css` must gain the five it does not yet carry » — is
    obsolete: nothing is owed to `tokens/maquette.css`, and the count was five only because it
    looked at one token family. Measured, because « it
    custom properties in the shipped CSS, and leaving them out keeps `frontend/dist`
    byte-identical.

11. **Answering a decision was a no-op on the acquisition side.** Found while drawing the screen:
    « Résoudre → » on « À traiter » opened the screen, took the choice, and left the item exactly
    where it was, because the answer only ever looked in the Arrivées list. Fixed in the prototype.
    The app's equivalent — whether resolving from one queue clears it from the other — is a
    verification step of the binding mission, on the real API, not a claim of this one.
