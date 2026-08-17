# SP4d wave 1 — Système, Maintenance, Configuration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The first of SP4d's four page waves. The three surfaces the legacy engine draws
with `viewSystem`, `viewMaintenance` and `viewReglages` leave the fragment and become final
React components. They are the right three to go first not because they are small — Réglages
is the largest data surface in the prototype — but because they **write almost nothing**:
Système and Maintenance are pure renderers, and Réglages' only writes are to `REG_ETAT`.
That is what makes them the place to pay for the PAGE machinery, exactly as SP4a paid for
the SCREEN machinery on the two smallest screens.

**Architecture — the page host, and why it is not the screen host.** Every surface migrated
so far is an overlay SCREEN with its own path, rendered inside the React root `#coquille`,
which sits as a sibling of `.stage`. A PAGE has no address of its own: `/` stays the pages'
route with its legacy query (`?page=&rub=`) and the LEGACY parser keeps owning it — the
spec's own law, ownership flips page by page only as pages migrate. A page's markup must
land inside `#view`, where the stylesheet, the harness selectors and the document-level
click delegation all expect it.

So the shell PORTALS into the legacy `#view`, and the fragment stops writing there for a
page that has moved:

- `PAGES_OF()` entries gain a `shellOwned` flag. `render()` (`refonte.html` ~14994) keeps
  doing `view.innerHTML = found.render()` for every page that has not migrated, and for a
  `shellOwned` page does **nothing to `#view`** — everything else it does (`fab.hidden`,
  `renderNav()`, `mountLoaders()`, `mountSearch()`, `monterBarreEnregistrer()`) still runs,
  because the bar, the nav and the save bar are shared furniture.
- The shell reads `state.page` through `useUiState()` and renders the matching component
  through `createPortal(…, view)`. **Taking ownership clears what the legacy left**: the
  effect that mounts the portal empties `#view` first, once, on the transition — otherwise
  the previous legacy page's DOM stays underneath and two pages are drawn at once.
- Handing ownership BACK needs nothing: the legacy's own `view.innerHTML = …` removes the
  portal's nodes, and React unmounts the portal in the same state change.

This is the wave's principal arbitration and it is **open to contest**. The alternative —
a new container of the shell's own, outside `#view` — was rejected because it moves the
page's markup out of `.stage`'s layout context and forces a CSS amendment, which the spec
reserves for SP5; and because every harness selector reading `#view …` would have to move
with it, which is the opposite of conversion at identical markup.

**What does NOT move.** The DATA stays in the fragment and reaches React through
`window.__referentiel`, as every wave since SP4a has done: `REGLAGES` (1453 lines, 153
settings), `SECRETS`, `MAINT_ACTIONS`, `SERVICES`, `PLANIFICATEURS`, `DISQUES`, `INDEX`,
`DEPENDANCES`, `ERREURS`, `EXECUTIONS`, `JOURNAL` — 2202 lines of embedded référentiel. So
do the shared emitters `listeFaitsHTML`, `skelCards`, `surfErr`, `emptyHTML`, `chipHTML`,
`svgIcon`: they are called by pages this wave does not touch, and a component calls the
published helper verbatim rather than re-deriving its markup — the same discipline
`add.tsx` already applies to `cardHTML`, and for the same reason (the delegated click
handlers depend on that markup being byte-exact).

**And `REG_ETAT` stays the source of truth.** R60 reads `REG_ETAT.modifs` in five holds,
calls `render()` and `ouvrirReglage()`, and sets `REG_ETAT.rubrique` directly. Making the
settings state React-owned would leave those holds reading nothing — green, measuring
nothing. The store conditions already say it: the legacy owns the mutable, React subscribes.

**Tech Stack:** React 19, @tanstack/react-router ^1.170, @tanstack/store ^0.11, Vite 8,
Playwright harness (`command python3` = 3.12.4, chromium `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
(§The waves — "SP4d… — the pages: one wave per page or pair, simplest first: sys/maint/config,
arr, lib, acq; the drawer migrates with its last consumer").

**Recon:** measured 2026-08-17 on `main` = `7ac230c8` (v0.97.17). Every line number below is
an anchor HINT — re-grep the SYMBOL before editing.

## Global Constraints

Repeated rather than referenced: a plan that points at another plan for its constraints is
a plan whose constraints nobody reads.

- **Conversion at IDENTICAL markup and behaviour**: same tags, classes, attributes and
  texts. Restore the whitespace text nodes at every legacy line-break point in inline
  containers (SP4b paid this three times — « Saison 33/13 »); `{" "}` where the legacy
  template broke a line inside a flex/inline parent.
- **Gate of EVERY task that changes what is served**: full suite green (48 scripts), R59
  (`back.py`) / R69 (`url_state.py`) / R71 (`screens.py`) at UNCHANGED rule code. Any
  exception is a recorded amendment in `regions.json`, never a workaround.
- **The rule ladders gain each surface's identity the SAME wave it moves.** This wave walks
  into two guards that are already primed to pass on nothing (Tasks 5 and 7) — closing them
  is not optional cleanup, it is what makes the rest of the wave's green mean anything.
- **Measurement ritual** after every source edit, before any harness run:
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
  (`/tmp/tm-refonte/` must also carry the `assets` symlink — a missing one reads as two
  broken-image failures in R75, not as a setup problem).
- `command python3` for harness scripts; static server 127.0.0.1:8899; scratch ports
  8913/8917/8918 only; **NEVER 8710/8711/8712**. One measuring process at a time.
  FOREGROUND every run — never background a suite and end a turn.
- `rg` ALWAYS with a glob filter: `refonte.html` is ~40k lines and an unfiltered `rg`
  crashes the machine on a 14 GB fixture directory.
- **Persistent-node discipline** (SP4b lesson): any input or scrollable inside a component
  is keyed by business identity; scroll resets where the legacy rebuilt `innerHTML`.
- **Publication discipline**: `function` declarations hoist; a `const` declared after the
  `window.__referentiel` site is published as a getter (TDZ — SP4b lesson). Never
  approximate an unpublished helper: publish the real one.
- **Store conditions bind**: domain hooks are the only door for components; the legacy
  `render()` stays explicitly called and never subscribed; world mutations notify through
  `render()`'s `magasin?.toucher()`.
- **The no-French rule is enforced, not remembered** (`scripts/check-no-french.py`, in
  `make check` and CI): every name this wave writes is English on the day it is written,
  and every French string it renders is EXTRACTED into `design/src/i18n/fr.json` under
  `screens.system.*` / `screens.maintenance.*` / `screens.settings.*` — never retyped. A
  data value or an address that stays French carries a `french-ok: <reason>` pragma.
- Comments English and timeless. Commits French Conventional, scope `(shell-mobile)`.
  Never chain a commit or a push with a gate in one command. Verify the remote SHA after
  every push.

## What the recon settled, and must not be re-litigated

- **`state.maintBlanc` has no writer anywhere.** Initialised `true` (~11456), never mutated,
  so `ouvrirActionMaintenance`'s guard (~12579) is always true. Port it LITERALLY; "fixing"
  it changes rendered output.
- **`#qreg` has no `oninput` handler.** `mountSearch` (~16031) binds `#libq` and `#follq`
  only, so the settings search is inert except for its clear button and programmatic
  `REG_ETAT.q`. Port it literally.
- **`#savebar` is not inside `#view`.** `monterBarreEnregistrer` (~15006) removes and
  re-inserts it into `#device`, and R60 asserts it sits inside `#device`'s rect. It is a
  SECOND host for the settings page — Task 6.
- **This wave is NOT the drawer's last consumer**: the topbar burger (~4258, static app
  shell) and `viewIntrouvable` (~12652) still open it. The drawer stays in the fragment;
  what this wave owes it is that `data-navgo` keeps landing on all three pages (R65, 26
  holds).
- **`LIBELLES_REGLAGES` (94), `NOMS_SUJETS` (54), `CONTENANTS_REGLAGES` (7) and `UNITES`
  (8) are exact duplicates** of `fr.json`'s `settings.labels` / `subjects` / containers /
  `units`, already reimplemented in `panel.tsx`. This wave is the one that gets to delete
  the fragment's 179 duplicated lines — Task 8.

---

### Task 1: The page host — `shellOwned`, the portal, and the ownership transition

**Files:**

- Modify: `frontend/maquette/design/refonte.html` (`PAGES_OF()` ~14921/14946/14952 gain
  `shellOwned: true`; `render()` ~14994 stops writing `#view` for such a page)
- Modify: `frontend/maquette/design/src/shell.tsx` (the page host: read `state.page`,
  portal the matching component into `#view`, clear on taking ownership)
- Create: `frontend/maquette/design/src/pages/host.tsx` (the host and its ownership effect)

**Interfaces:**

- Produces: `<PageHost>` — reads `useUiState().page`, looks the id up in a table of
  migrated pages, and renders `createPortal(<Component />, view)`. The table is the ONE
  place a future wave adds a page.
- The clearing effect runs on the transition INTO ownership only, never on every render:
  clearing while React holds children would remove nodes React still believes it owns.

- [ ] **Step 1:** `shellOwned` on the three entries; `render()`'s `#view` write becomes
      conditional. Everything else in `render()` still runs — prove it by reading the
      function, not by assuming.
- [ ] **Step 2:** The host component and its portal, with `sys` alone wired to a placeholder
      that renders the legacy `viewSystem()` string through `dangerouslySetInnerHTML` — the
      SAME markup, drawn by React. This is the machinery test: identical bytes, different
      owner.
- [ ] **Step 3:** Ownership both ways, measured: `applyState({page:"lib"})` →
      `applyState({page:"sys"})` → `applyState({page:"lib"})`, asserting `#view` holds
      exactly one page's markup at each step and no orphan from the other side.
- [ ] **Step 4:** NEW RULE **R77** (`harness/page_host.py`) — the ownership law: a migrated
      page's markup is in `#view`; leaving it and coming back leaves no residue; the legacy
      pages still draw. Mutation: removing the clearing effect must fell the residue hold
      alone. Record R77 in `regions.json` and in the README's rule table.
- [ ] **Step 5:** Full suite. Zero FAILED. Commit:
      `feat(shell-mobile): la coquille peut posséder une PAGE — hôte, portail, et la loi de propriété (R77)`

### Task 2: The référentiel widens for the three pages

**Files:**

- Modify: `frontend/maquette/design/refonte.html` (the `window.__referentiel` site ~15094)
- Modify: `frontend/maquette/design/src/data.ts` (the hook and its types)

**Interfaces:**

- Publishes, as FUNCTIONS where the value is live and as values where it is frozen:
  `listeFaitsHTML`, `skelCards`, `surfErr`, `emptyHTML`, `chipHTML` (frozen emitters);
  `SERVICES`, `SERVICES_PANNE`, `PLANIFICATEURS`, `PLANIFICATEURS_PANNE`, `EXECUTIONS`,
  `DISQUES`, `INDEX`, `DEPENDANCES`, `ERREURS`, `MAINT_RUBRIQUES`, `MAINT_ACTIONS`,
  `RISQUES`, `JOURNAL`, `SECRETS` (data); `REG_ETAT` (live, read through a getter);
  `ouvrirActionMaintenance`, `ouvrirSecret`, `fichiersModifies`, `nomDeFichier`,
  `vueRubrique`, `vueSecrets`, `chercheReglagesHTML`, `ligneReglageHTML`, `valeurCourante`,
  `uniteDe` (verbs and emitters the components call).
- The six settings helpers `tousLesReglages`, `reglageId`, `valeurEnCours`, `valeurSaisie`,
  `modifierReglage`, `ouvrirReglage` are ALREADY published — do not duplicate them.

- [ ] **Step 1:** Publish; TDZ check on every `const` (declared after the site → getter).
- [ ] **Step 2:** Type them in `data.ts` beside the existing `Setting` contract.
- [ ] **Step 3:** Full suite. Commit:
      `feat(shell-mobile): le référentiel publie les trois pages — données, émetteurs, verbes`

### Task 3: `SystemPage` — the pure renderer

**Files:**

- Create: `frontend/maquette/design/src/pages/system.tsx`
- Modify: `frontend/maquette/design/src/i18n/fr.json` (`screens.system.*` — 18 strings)
- Modify: `frontend/maquette/design/refonte.html` (delete `viewSystem` once it has no caller)

**Interfaces:**

- Renders the seven `listeFaitsHTML` blocks, the three `.note`s, the eight `.h2` headings,
  the two `.crossref` buttons (`data-page="cfg"`, `data-page="maint"`) and the `data-go="arr"`
  row — every attribute verbatim, every inline style verbatim
  (`min-width:0;flex:1`, `margin-top:0`).
- Reads `state.phase` (skeleton / error) and `state.panne` exactly as the legacy did.

- [ ] **Step 1:** Extract the 18 strings into `fr.json` by COPY, never retyping.
- [ ] **Step 2:** The component, at identical emission. Typecheck.
- [ ] **Step 3:** Fidelity oracle: drive each of the four `systeme-*` states and diff the
      rendered `#view` innerHTML against the legacy's, byte for byte, before deleting
      `viewSystem`. Paste the diff (expected: empty).
- [ ] **Step 4:** R67's 56 Système holds green at UNCHANGED rule code. Full suite.
- [ ] **Step 5:** Commit: `feat(shell-mobile): Système passe à la coquille — rendu identique, 56 tenues inchangées`

### Task 4: `MaintenancePage` + the action panel

**Files:**

- Create: `frontend/maquette/design/src/pages/maintenance.tsx`
- Modify: `frontend/maquette/design/src/i18n/fr.json` (`screens.maintenance.*` — 8 strings)
- Modify: `frontend/maquette/design/refonte.html` (delete `viewMaintenance`; keep
  `ouvrirActionMaintenance` until Task 4 Step 3 proves the component's call site)

**Interfaces:**

- The rubric list, the back link (`data-maintrub=""`), the six rubric rows
  (`data-maintrub="<id>"`), the action rows carrying `data-maintact` — which the legacy
  never writes literally: it is synthesised by `listeFaitsHTML` from `cible:{maintact:…}`,
  so the component passes the same `cible` and lets the published emitter write it.
- Destructive rows keep `etat:"danger"` → `li.fx.fblocked.fclick`.
- `state.maintBlanc` ported literally (always true — see the recon).

- [ ] **Step 1:** Strings into `fr.json`; the component at identical emission.
- [ ] **Step 2:** Fidelity oracle over the four `maintenance-*` states, byte for byte.
- [ ] **Step 3:** R67's 18 Maintenance holds green at unchanged rule code — note that
      `machine.py` drives Maintenance through `applyState({page:'maint', maintRub:…})` with
      the six rubric ids hard-coded, and never through `data-maintrub`; the delegation path
      therefore needs its own hold (Task 7).
- [ ] **Step 4:** Full suite. Commit:
      `feat(shell-mobile): Maintenance passe à la coquille — les 26 actions et leurs six rubriques`

### Task 5: `SettingsPage` — with `REG_ETAT` still the owner

**Files:**

- Create: `frontend/maquette/design/src/pages/settings.tsx`
- Modify: `frontend/maquette/design/src/i18n/fr.json` (`screens.settings.*` — 15 strings)
- Modify: `frontend/maquette/design/refonte.html` (delete `viewReglages`, `vueRubrique`,
  `vueSecrets`, `chercheReglagesHTML` once published and called)

**Interfaces:**

- The six rubric rows (`data-rubrique="<id>"`) plus the literal `"secrets"` rubric, the
  search field `#qreg` (inert, with its `data-qreg` clear button), the per-file `<h2><code>`
  headings, the `.settingrow[.modified]` rows carrying `data-reglage="<f>:<c>"`, the
  secrets list (`data-secret`), `data-profil="global"`, `data-redemarrer="1"`.
- **`REG_ETAT` is read, never replaced**: the component subscribes through the store's
  `version` bump (the same mechanism `add.tsx` uses for the in-place `state.added` Set) so
  a legacy delegation write redraws the page without React owning the state.

- [ ] **Step 1:** Strings into `fr.json`; the component at identical emission.
- [ ] **Step 2:** Fidelity oracle over all 16 `reglages-*` states, byte for byte.
- [ ] **Step 3:** **Close the primed false-green.** `panel.tsx` deliberately dropped
      `window.__sujetsSansNom.add(s)`; the set is created empty and filled only inside
      `sujetReglage`. Delete `sujetReglage` from the fragment and the set stays EMPTY —
      which `settings.py:250`'s "every subject carries a written name" hold SATISFIES. Fix
      the rule the same wave: the hold must first assert the set was POPULATED (a non-empty
      denominator), then that it is empty of nameless subjects. Mutation: an unnamed subject
      must fell it, and an unpopulated set must fell it too. Record the amendment in
      `regions.json`.
- [ ] **Step 4:** R60's 44 holds green, at rule code changed ONLY by Step 3's rung.
- [ ] **Step 5:** Full suite. Commit:
      `feat(shell-mobile): Réglages passe à la coquille — REG_ETAT reste la source, et la tenue des sujets cesse de passer sur du vide`

### Task 6: The save bar — the page's second host

**Files:**

- Modify: `frontend/maquette/design/src/pages/settings.tsx` (a second portal, into `#device`)
- Modify: `frontend/maquette/design/refonte.html` (`monterBarreEnregistrer` ~15006 stops
  mounting it for the migrated page)

**Interfaces:**

- `#savebar` renders through a portal into `#device`, appearing only when
  `state.page === "cfg"` and `REG_ETAT.modifs.size > 0`, disabled when
  `REG_ETAT.lectureSeule` — the legacy's exact conditions, and its exact markup
  (`data-enregistrer="1"`, the `.sn` file list from `fichiersModifies()`).

- [ ] **Step 1:** The portal and its conditions.
- [ ] **Step 2:** R60's save-bar holds green — including the one that asserts it sits inside
      `#device`'s rect.
- [ ] **Step 3:** Full suite. Commit:
      `feat(shell-mobile): la barre d'enregistrement suit sa page — un second portail, dans #device`

### Task 7: The identity rungs these three pages never had

**Files:**

- Modify: `frontend/maquette/harness/machine.py` (R67)
- Modify: `frontend/maquette/regions.json` (the amendments)

**Interfaces:**

- **R67 finds the five Système lists by their French `<h2>` TEXT.** With the headings now
  read from `fr.json`, a one-character shift makes `block()` return `None`, `rows or []`
  makes the badge holds pass on an EMPTY list, and only the `rendered == declared`
  comparison catches it. Add the rung: each named block must be FOUND, with a non-zero row
  count, before its contents are judged.
- The delegation attributes `data-maintrub`, `data-maintact`, `data-reglage`,
  `data-rubrique`, `data-secret`, `data-enregistrer`, `data-qreg`, `data-profil` are
  asserted by NO rule today (recon §6). This wave moves the code that emits them, so it owes
  them a hold: a real tap on a rubric row changes the rubric, and a real tap on an action row
  opens its panel.

- [ ] **Step 1:** The found-and-non-empty rung, with a mutation that fells it (rename a
      heading in the COPY only) and one that does not (an unrelated hold stays green).
- [ ] **Step 2:** The delegation holds, driven by real taps, not by `applyState`.
- [ ] **Step 3:** Record both amendments in `regions.json`. Full suite.
- [ ] **Step 4:** Commit: `test(shell-mobile): R67 cesse de juger une liste qu'elle n'a pas trouvée, et les attributs de délégation gagnent leur tenue`

### Task 8: The fragment gives up its duplicated maps

**Files:**

- Modify: `frontend/maquette/design/refonte.html` (delete `LIBELLES_REGLAGES`,
  `NOMS_SUJETS`, `CONTENANTS_REGLAGES`, `UNITES`, `libelleReglage`, `sujetReglage`,
  `uniteDe` once no caller remains — 179 lines)

- [ ] **Step 1:** Prove zero callers remain (grep each symbol, paste the empty result).
- [ ] **Step 2:** Delete. Full suite — R60 in particular, whose subject-name hold now reads
      only the React side.
- [ ] **Step 3:** Commit: `refactor(shell-mobile): le fragment rend ses quatre tables dupliquées — fr.json est la seule source`

### Task 9: Wave gate

- [ ] `resync.py` (live counters drift during a wave), review, commit as data if it changed
- [ ] Full suite 48/48, zero FAILED, hold total recorded and explained if it moved
- [ ] `make check` and `make check-frontend` green; `scripts/check-no-french.py` green
- [ ] R59/R69/R71 byte-identical against the merge point (`git diff` on the rule sources)
- [ ] `IMPLEMENTATION.md` + `docs/superpowers/shell-mobile-wave-log.md` wave record;
      `frontend/maquette/README.md` rule table gains R77
- [ ] Adversarial review of the whole branch diff, then PR, CI green, squash merge
- [ ] Post-merge: `pm2 restart torrentmate-design` is NOT needed (no `serve.py` change) —
      but the design host serves this checkout, so confirm the three pages live
