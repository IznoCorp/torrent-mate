# L04 — Boundaries and the tree

**Codename** `maquette-l04` · **Commit type** `refactor` · **Bump** 0.98.20 → 0.98.21
**Lot** `docs/reference/frontend-architecture.md` § Phase 1 — L04 (BINDING) · _depends on L01_ · **runs alone**
**Date** 2026-08-22

> The lot's own **Done when**, quoted from the architecture file so nothing here softens it:
>
> « seven guards, each failing on a deliberate violation and wired into the gate: **1.** no import
> cycle (the two above are gone); **2.** a fan-in ceiling — a module outside `ui/` and `lib/`
> imported by more than a set number of features is refused; **3.** layering — `ui/` and `lib/`
> never import `features/` or `routes/`; two features never import each other; **4.** size — the
> module ceiling (invariant 6), covering the frontend; **5.** the typing ratchet — no `any`, no
> `ts-ignore`, from today's zero; **6.** no duplicate import from one module; **7.** one address,
> one file. Plus: the tree matches the target, `data.ts` no longer exists, and grandfathered files
> are listed with their converting lot. »

**Serves** `product-intent.md` §15 (the maquette is the product, and « ce qui reste n'est pas que
des pages : l'UX, le langage d'interaction et **l'architecture** de la maquette doivent être
terminés et consolidés avant le gel ») and its 2026-08-20 clause « aucune vague ne s'ouvre sans
son design et son plan ». No user-visible surface changes, by construction — which is what §15's
own method demands of a move.

---

## 1. What is measured today

Every figure was taken on `main` at `875a9b98`, with the command that produced it. They are the
lot's starting line.

| Measurement                                              | Value                                                         | Method                                                                                                                   |
| -------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Files under `design/src`, engine excluded                | **26** (25 modules + `i18n/fr.json`)                          | `find frontend/maquette/design/src -type f -not -path '*/engine/*' \| wc -l`                                             |
| **Import cycles**                                        | **2 back-edges**, **3 simple cycles**                         | resolve every relative `from "…"` under `design/src` into a graph, then walk it                                          |
| **Hub module**                                           | `data.ts`, **17 importers** of 25 modules                     | fan-in over the same graph                                                                                               |
| Its symptom                                              | **6** files import `data` twice                               | same graph, per-file duplicate targets                                                                                   |
| `Reference`, the hub's largest type                      | **340 lines**, **108 members**                                | bracket-match `export type Reference = {` and count top-level keys                                                       |
| … of which read by exactly one prospective feature       | **73**                                                        | regex each member name over every module, group modules by prospective feature                                           |
| … read by 2 to 6 features                                | **28**                                                        | same                                                                                                                     |
| … read by no component at all (engine-only) | **10** | same, comments stripped — three of them (`actionResolve`, `actionLeave`, `secHTML`) are NAMED only inside comments, and a first reader counted that as a read |
| … shared _with the panel_ — dissolved by decision D3     | **15 of the 28**                                              | same                                                                                                                     |
| **Files ≥ 400 non-blank lines** (engine excluded)        | **8**                                                         | `grep -cve '^\s*$'` per `.ts`/`.tsx`/`.js`                                                                               |
| **Files ≥ 250** (engine excluded)                        | **12**                                                        | same                                                                                                                     |
| **`any` / `as any` / `@ts-ignore` / `@ts-expect-error`** | **0**                                                         | `grep -rnE ':\s*any\b\|as any\|@ts-ignore\|@ts-expect-error' --include='*.ts' --include='*.tsx' src` minus `src/engine/` |
| **`lazy()` / dynamic `import()`**                        | **0**                                                         | `grep -rnE 'lazy\(\|import\(' src` minus `src/engine/`                                                                   |
| **Route declarations**                                   | **6**, all inside `shell.tsx` (682 lines)                     | `grep -n 'createRoute\|path:' src/shell.tsx`                                                                             |
| **The oracle at the starting line**                      | **2 739 measurements, 0 divergence**, reference at `737ce5e9` | `make maquette-oracle`                                                                                                   |

### The two cycles, stated exactly

The architecture file names two. The graph reports **three simple cycles over two back-edges**,
and the difference matters when the fix is verified:

```
components/panel.tsx  →  data.ts  →  components/panel.tsx
components/panel.tsx  →  settings-labels.ts  →  data.ts  →  components/panel.tsx
screens/add.tsx       →  shell.tsx  →  screens/add.tsx
```

The first two are ONE defect: the back-edge is `data.ts → components/panel.tsx` (a type-only
import of `PanelDescriptor`), reached by two paths. Removing that single edge removes both
cycles. The third back-edge is `shell.tsx → screens/add.tsx`, and `add.tsx`'s import of `go` is
its other half.

### Two findings that shape the lot

**The panel is why the `Reference` type looks unsplittable.** 15 of the 28 shared members are
shared _with `components/panel.tsx`_ — `seasonsOf`, `ownedFor`, `sheetFor`, `EP_LABEL`, `POSTERS`,
`TODAY` (the seasons grid) and `settingId`, `fileName` (the field editor). Those eight are not
genuinely cross-cutting: they are one file holding two domains. Decision D3 dissolves them, which
is why D3 lands **before** the `Reference` split in the step order and not after.

**What remains shared is not domain at all.** After D3, the shared set is dominated by drawing
plumbing the engine publishes — `escapeHtml`, `svgIcon`, `icons`, `emptyInner`, `surfErrInner`,
`skelCardsInner`, `factRowsHTML`, `cardHTML`, `tileHTML`, `secInner`, `render`, `toast`,
`initials`, `baseTitle`, `posterBox`, `paintSelBar`. These render nothing themselves (they return
strings) and know no domain, so `lib/` is their home by the lot's own placement rule — and the
fan-in guard exempts `lib/` by its own wording. No exemption has to be invented for them.

---

## 2. Decisions

D-L04-1 to D-L04-4 were presented to the operator with their alternatives and their cost, and
arbitrated on 2026-08-22. D-L04-5 and D-L04-6 are taken here, with their reasons, because they
have a settled precedent in this repository rather than a real alternative.

### D-L04-1 — The module ceiling covers the maquette, and only the maquette

Invariant 6 is « hard ceiling 400 non-blank lines, soft warning at 250 », and the Done-when says
« covering the frontend ». Measured: the maquette has **8** files ≥ 400 and 4 more ≥ 250;
production `frontend/src` has **42** ≥ 400 and **73** ≥ 250, one of them a 7 398-line _generated_
file (`api/schema.d.ts`).

**Decided:** the guard reads `frontend/maquette/design/src` and nothing else. **Production is not
touched** — the operator's words: _« ton mandat ne touche pas à la production, l'oracle s'occupe
de la maquette pas de la production »_.

**Why it is not a softening.** Production is ARCHIVED at switchover (§15). A 42-entry
grandfather list there would have no « converting lot » to name for any entry, because production
is never converted — it is deleted. That is machinery guarding an object about to stop existing,
which is the failure § 2 of the architecture file exists to prevent. It is also the exact shape of
the French rule's existing production carve-out.

**Rejected:** the whole frontend with a 50-entry list (above). A maquette ceiling plus a pinned
production COUNT that may not rise (one more baseline file to maintain, for an app whose growth
stops at switchover anyway).

### D-L04-2 — No unit-test runner in this wave; the debt is L09's

The maquette has no test runner at all: `package.json` carries `dev`, `build`, `preview`,
`typecheck`. Measured: **11** of the 31 non-component functions are pure and testable without a
browser; the meatiest is `epState` (**8 branches**, deciding how an episode reads), touched today
by **3 assertions in one browser rule**.

**Decided:** nothing is installed. The debt is recorded in the architecture file against **L09**.

**Why L09 and not « later ».** The clean mock layer does not exist yet — **L08 builds it, seeded
from the fixtures it replaces**. Unit tests written before it would invent their own fakes by
hand, and a test whose fake is hand-made proves the fake. This repository has paid for that twice,
most expensively when a test mocking `Popen` stayed green over a continuation that crashed in
production and left the medium stuck in staging. Written after L08, the same tests rest on a layer
that is itself proved.

**Rejected:** landing the runner empty (small, and it puts a fifth instrument in the gate during a
wave whose promise is that nothing observable changes). Landing the runner and writing the tests
(mixes three kinds of change, which § 0 forbids in bold).

**What is kept from the option not taken:** the target tree already reserves
`features/<domain>/*.test.ts`. That slot stays declared, so L09 adds a runner, not a convention.

### D-L04-3 — The panel splits in three, and the domain blocks register themselves

`components/panel.tsx` is **628 lines** holding, in one file: five generic blocks (rich text,
chip, poster, actions, facts), a **seasons grid** reading `seasonsOf` / `ownedFor` / `sheetFor` /
`EP_LABEL`, and a **settings field editor** importing `Setting` and `settingLabel`. Five surfaces
open panels through it.

**Decided:** three pieces. `ui/panel/` keeps the descriptor, the generic blocks and the renderer
and imports no feature. The seasons block moves to `features/acquisition/`, the field block to
`features/settings/`, and each **registers its block kind** with the renderer at boot.

**Why, beyond the layering rule.** It is what makes D-L04-4 affordable: eight of the twenty-eight
shared `Reference` members are shared only because this one file holds two domains. Splitting the
panel does not add to the lot's cost — it removes from it.

**What must be proved, because an indirection can fail silently:** every declared kind is
registered before the first panel opens. `refuseBlock` keeps its existing job — an unknown kind
throws where the producer wrote it, never draws nothing — and a rule holds the registration, so a
feature that forgets to register fails loudly rather than rendering an empty panel.

**Rejected:** keeping a closed switch inside `ui/` (the letter of the layering rule holds — no
import — while its intent does not, and the next domain block lands there too). Making the panel a
feature with a named exception to « two features never import each other » (an exception on day
one is how a guard starts having a list).

### D-L04-4 — `data.ts` is cut for good, not moved

**Decided:** the 73 single-owner members go to their feature; the 10 members no component reads are
**deleted from the type**; the drawing plumbing goes to `lib/`; the handful genuinely shared
between two domains after D-L04-3 is arbitrated one by one and recorded in the plan. `data.ts`
stops existing.

**The correction that made this affordable, and it is recorded because it was stated wrongly
first.** « Cutting costs 17 files, moving costs 1 » is false: in both cases the 17 importers
change their import line. The real difference is what survives — a dissolved hub, or a renamed
one. The architecture file's corollary is explicit: « `data.ts` is not slimmed, it stops
existing ».

**How the global stays typed without a hub.** `window.__referentiel` is one runtime object, so
its type is declared once — as the **intersection of the feature slices**, in an ambient
declaration under `app/`, importing each slice with `import type` only. A feature then reads its
own slice through its own accessor and imports nothing: the ambient type needs no import at the
reading site. `app/` may import features (layering forbids it of `ui/` and `lib/`), and a
type-only edge creates no runtime dependency.

**Rejected:** one typed door in `lib/`, exempt from the fan-in ceiling by the guard's own wording
(smallest diff — and it silences, by exemption, the guard written to stop exactly this). Splitting
the thirty small domain types while keeping the 108-member block whole (the border between « a
domain type » and « a member of the block » then has to be drawn and defended).

### D-L04-5 — `i18n/` does not move (taken here)

**Decided:** `src/i18n/` keeps its path.

**Why.** It is a resource bundle, not a module, and **two independent tools read its literal
path**: `serve.py:106` (`DESIGN_ROOT / "src" / "i18n" / "fr.json"`, which the login gate and the
served pages read their words from) and `scripts/check-no-french.py`, whose string arm exempts any
file with `i18n` among its path parts (`"i18n" not in p.parts`, four call sites). The target tree
does not name `i18n/`, so nothing requires it to move, and moving it would put a three-ended
contract in a wave that has no reason to touch it.

### D-L04-6 — The three dying files share one bucket, and `legacy.js` does not move (taken here)

`engine/legacy.js` (34 650 lines), `states.js` (711) and `seams.ts` (77) all stop existing at
**L13**. None of them is in the target tree, and leaving them loose at `src/` root would force the
tree guard to carry per-file exceptions on its first day.

**Decided:** `states.js` and `seams.ts` move **into the existing `engine/` directory**, beside
`legacy.js`, which does **not** move. `engine/` is documented as the legacy bucket, grandfathered
whole, with L13 named as its converting lot.

**Why `legacy.js` stays put.** Its path is the most-cited in the repository — `common.py`'s
`DESIGN_SOURCES`, `resync.py`, `refresh-maquette-fixture.py`, `check-css-tokens.py`,
`nofrench_lexicon.py`'s `DEBT_FILE`, `page_host.py` and several dated documents. The architecture
file has already ruled on this exact trade for the harness's 52 flat files: « Moving them means
changing as many paths cited across documents and briefs — a real cost for a gain in comfort. […]
it waits for a stronger reason than tidiness. » Two files move; the cited one does not.

**What this costs, named so it is not discovered mid-wave:** `legacy.js`'s single import line
(`from "../seams.js"` → `"./seams.js"`), `states.js`'s single import line, and
`check-no-french.py`'s French-debt allow-list entry for `states.js`. Three ends, one commit.

**The naming tension, recorded rather than paid for:** the scenario table is deliberately NOT the
engine's — SP4-fin wave 3 took it out of the engine on purpose — and it now sits in a directory
called `engine/`. Renaming the directory to `legacy/` would re-open every pointer `legacy.js`'s
staying put was meant to protect. The bucket's meaning is written down instead.

---

## 3. The target tree, file by file

The rule that decides where a file goes, quoted from the architecture file:

> **A file lives with what makes it change.**
> One surface makes it change → `features/<that surface>/`. Two surfaces make it change for their
> own reasons → either it knows no domain and belongs in `ui/` or `lib/`, or **it is two files**.
> It knows no domain → `ui/` if it renders, `lib/` if it does not.
>
> **Never create a folder for a KIND of file.** No root `hooks/`, no `types/`, no `utils/`.

| Target                  | Holds                                                                                                              | From                                                                                              |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `app/`                  | boot, providers, the router tree, the ambient reference type, the page host, the focus manager, the store, the 404 | `shell.tsx` (what remains of it), `store.ts`, `focus.ts`, `pages/host.tsx`, `pages/not-found.tsx` |
| `routes/`               | one file per address — six today                                                                                   | the six `createRoute` blocks now inside `shell.tsx`                                               |
| `features/acquisition/` | the Acquisition page, the add screen, the seasons panel block                                                      | `pages/acquisition.tsx`, `screens/add.tsx`, the seasons half of `panel.tsx`                       |
| `features/library/`     | the Médiathèque, the media sheet                                                                                   | `pages/library.tsx`, `screens/media.tsx`                                                          |
| `features/arrivals/`    | Arrivées, the arbitration screen, the release-choice screen                                                        | `pages/arrivals.tsx`, `screens/resolution.tsx`, `screens/releases.tsx`                            |
| `features/settings/`    | Configuration, the setting naming, the quality-profile screen, the field panel block                               | `pages/settings.tsx`, `settings-labels.ts`, `screens/profile.tsx`, the field half of `panel.tsx`  |
| `features/system/`      | Système                                                                                                            | `pages/system.tsx`                                                                                |
| `features/maintenance/` | Maintenance                                                                                                        | `pages/maintenance.tsx`                                                                           |
| `features/account/`     | the account page                                                                                                   | `pages/account.tsx`                                                                               |
| `ui/`                   | CVA-less primitives today: the icon, the sheet, the panel shell and its generic blocks                             | `components/icon.tsx`, `components/sheet.tsx`, the generic half of `panel.tsx`                    |
| `lib/`                  | domain-free, non-rendering: the store access hooks, the navigation door, the engine's drawing plumbing             | `data.ts`'s hooks, `go()` from `shell.tsx`, the shared `Reference` plumbing                       |
| `engine/`               | **legacy, dies at L13**                                                                                            | `engine/legacy.js` (unmoved), `states.js`, `seams.ts`                                             |
| `i18n/`                 | the resource bundle                                                                                                | unmoved (D-L04-5)                                                                                 |
| `styles/`, `mocks/`     | declared by the tree guard, created by L06/L07 and L08                                                             | —                                                                                                 |

> **What the measurement changed in this table, recorded rather than quietly edited.** Two
> features exist that this table did not name, and one screen moved. `features/media/` owns the
> media catalogue — `sheetFor`, `seasonsOf`, `ownedFor`, `EP_LABEL`, `TODAY` — because the season
> matrix and the media sheet read exactly that and nothing else of each other's subjects; leaving
> them apart made eight members look « shared between two features » when they are one subject
> read twice. `features/releases/` owns `RELEASES`, `RESOLUTIONS`, `AUDIOS` with the
> release-choice screen AND the quality-profile screen: the profile screen reads the release
> vocabulary and none of the settings one, so this table's original placement of it under
> Configuration was wrong. Both corrections come from the readership measurement, not from taste.

**Two placements that needed the rule rather than a habit.** `pages/not-found.tsx` renders the
shell's own answer to an unknown page id and belongs to no domain — it changes when the shell
changes, so it is `app/`, not a one-file feature. `screens/profile.tsx` is the quality-profile
screen, reached from Configuration and changed by it, so it is `features/settings/` even though
what it configures is later read on the acquisition path.

**`go()` leaves `shell.tsx`,** and that is what breaks the second cycle. It goes to
`lib/navigate.ts` — it takes a path and params, knows no domain, renders nothing — and the router
instance is handed to it at boot through a live binding, the pattern `seams.ts` already proves
here. `lib/` therefore never imports `app/`. **R76 moves with it**, in the same commit: the rule
pins `go()` to `shell.tsx` by file NAME today (`harness/navigation.py`), and a rule left pointing
at the old home is a rule that stops measuring.

---

## 4. The order inside the lot

The architecture file fixes it, and the reason is that a single-shot move is unreviewable.

| #   | Step                                                                                                       | Lands                                                                   | Proof                                                                 |
| --- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------- |
| 1   | **Break the two cycles** — the only real code change                                                       | alone                                                                   | the oracle, plus the cycle guard falling on a restored back-edge      |
| 2   | **Split `data.ts`** — types to their features, store hooks to `lib/`, the reference slices to their owners | after D-L04-3's panel split, which dissolves 8 of its 28 shared members | the oracle; `tsc`                                                     |
| 3   | **Move to the target tree** — no logic changes                                                             | after 2                                                                 | the oracle at zero divergence                                         |
| 4   | **Install the guards**, each mutation-tested                                                               | after 3                                                                 | each guard falls on a deliberate violation and names the right defect |
| 5   | **Record the files over the ceiling** with the lot that converts each                                      | last, so the list describes the tree that shipped                       | the list is regenerated by the guard itself, never hand-maintained    |

**Renames go through `scripts/rename-identifiers.py`** — a rename needs a parser, not a regex —
and **the tool is not the proof**: its read-back check is skipped for `--values` runs and for
Python files. Every batch is verified outside it, by re-reading the diff and re-running the rule
suite. Two corruptions in this repository were found exactly that way.

---

## 5. The seven guards

One script, `scripts/check-frontend-boundaries.py`, with one arm per guard — the house shape
(`check-no-french.py`, `check-markup-contracts.py`), and the entry point stays the gate's ONE
command. Wired into `make check` and into the CI `checks` job beside `check-markup-contracts.py`.

| #   | Guard                     | Refuses                                                                                                         | Floor                              |
| --- | ------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| 1   | **No import cycle**       | any cycle in the resolved graph under `design/src`                                                              | hard zero                          |
| 2   | **Fan-in ceiling**        | a module outside `ui/` and `lib/` imported by **more than 4 features**                                          | hard                               |
| 3   | **Layering**              | `ui/` or `lib/` importing `features/` or `routes/`; one feature importing another                               | hard zero                          |
| 4   | **Size**                  | ≥ 400 non-blank lines (`REPORT`), ≥ 250 (`WARN`), over `design/src` only (D-L04-1), engine bucket grandfathered | grandfathered list, never extended |
| 5   | **Typing ratchet**        | `any`, `as any`, `@ts-ignore`, `@ts-expect-error`                                                               | hard zero, from today's zero       |
| 6   | **No duplicate import**   | the same module imported twice by one file                                                                      | hard zero                          |
| 7   | **One address, one file** | a file under `routes/` declaring more than one `path:`; an address declared in two files                        | hard zero                          |

Plus the tree check: every file under `design/src` sits in a declared bucket, and `data.ts` does
not exist.

**Why 4 for the fan-in ceiling.** The architecture file states its own intent: « This is the one
that would have stopped `data.ts` at four importers instead of seventeen. » It counts FEATURES,
not modules, and `ui/` and `lib/` are exempt by its wording — which is why the store hooks and the
navigation door go to `lib/`: they are domain-free and non-rendering, so no exemption has to be
invented for them and the guard's sentence stands unamended.

**Each guard is mutation-tested**: break the behaviour on purpose, confirm the guard falls and
**names the right defect**, restore. A guard that never bit proves nothing. The mutations are
written into the plan, one per arm, and the restore is verified by the guard going green again.

---

## 6. What this lot does not touch, and what it reports

**Out of scope by the architecture file's own words:**

- **Bundle splitting.** It belongs to L12 — it changes loading behaviour, and nothing here may
  change anything observable. The measured `0 lazy() / 0 dynamic import()` is recorded, not fixed.
- **The harness's 52 flat `.py` files.** Named in the lot as a known defect « deliberately left
  alone »; it waits for a stronger reason than tidiness.
- **Everything the target tree reserves for later lots** — `styles/` (L06/L07), `mocks/` (L08).

**Reported, not repaired here** (§méthode rule 4 — a defect found is an open point, never an
« out of scope » of the agent's own initiative). These go to the pull request body and, where they
belong there, to `BUGS.md` or the architecture file:

- **No unit-level test** — measured, arbitrated by the operator (D-L04-2), recorded against L09 in
  the architecture file.
- **B-036** (two French state ids, and no arm of `check-no-french.py` reads the state table) and
  **B-040** (names in files no arm reads) are open and belong to their own waves. Not taken in
  passing.
- Anything else found while moving is written down and left.

**No audit of this lot happens inside it.** That office is the steward's
(`docs/reference/frontend-steward.md`), in a separate session, and an implementer auditing their
own lot compares their intention with their work.

---

## 7. Risks, and how each is met

| Risk                                                | Why it is real here                                                                                                 | Met by                                                                                                                         |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **A move hides an edit**                            | the lot touches 25 of 26 files; a one-character change inside a rename is invisible in a move diff                  | one kind of change per step (§ 4); the oracle green at every step; step 1 lands alone                                          |
| **The oracle cannot certify from elsewhere**        | its measurements are bound to this machine; `--check` refuses across a platform mismatch and it is never in CI      | the wave is executed and certified here, and the plan says so at every gate                                                    |
| **A harness rule points at a moved file**           | `navigation.py` pins `shell.tsx` by NAME; `check-no-french.py` pins `states.js`; `index.html` pins `/src/shell.tsx` | each is a three-ended contract moved in ONE commit, listed in the plan, and the full rule suite is the gate before merge       |
| **The block registry fails silently**               | an indirection that is not filled draws nothing rather than throwing                                                | `refuseBlock` keeps throwing on an unknown kind, and a rule holds that every declared kind is registered before the first open |
| **The `Reference` cut drops a member**              | 108 members, 7 of them read only by the engine                                                                      | the cut is verified by `tsc` (a dropped member fails at its reading site) and by the full rule suite, not by reading           |
| **A rename tool reports success over a corruption** | its read-back is skipped for `--values` and for Python                                                              | re-read the diff, not the « N file(s) touched » line; re-run the rule suite — the oracle outside the tool                      |

---

## 8. Acceptance

Every criterion is an executable command with a documented expected output; they are written in
full in the plan's `ACCEPTANCE.md`. The shape:

- the seven guards run in one command and exit 0 on the tree as it ships, and each one exits
  non-zero with the right message on its own recorded mutation;
- `python3 scripts/check-frontend-boundaries.py` reports **0 cycles**, **0 layering violations**,
  **0 duplicate imports**, **0** `any`/`ts-ignore`, and no module outside `ui/`/`lib/` above 4
  feature importers;
- `test ! -f frontend/maquette/design/src/data.ts`;
- `make maquette-oracle` → **0 divergence** over 2 739 measurements;
- `frontend/maquette/harness/run.sh` → the full suite green at **unchanged hold counts**;
- `make lint`, `make test` (no failure and no ERROR), `make check`, and the maquette typecheck.
