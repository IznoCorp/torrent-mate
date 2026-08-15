# SP4b — the fiche + the panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wave B of SP4 — the fiche (the most connected screen) becomes the real route
`/fiche/$titre` as a final React component, and the bottom panel (`openSheet` +
`panneauHTML`, the unique derived constructor — R56) migrates with it; every legacy
producer opens the panel through the shell. B-024/025/026 are treated in the wave
(operator arbitration 2026-08-16), B-027/028/029 as tooling hygiene.

**Architecture:** The React `<Feuille>` layer replaces the envelope's `#sheet` cluster
at IDENTICAL ids and class chains (`#scrim.scrim` + `#sheet.sheet > #sheetgrab.sheetgrab

- #sheetin.sheetin`), so the 21 harness scripts that read `.sheet`/`#sheet`measure the
React layer without one byte of rule change; z-index (sheet 47 > screen 45) carries the
paint order because`#coquille`creates no stacking context.`<PanneauContenu>`is the
React port of`panneauHTML`/`panneauBlocHTML`/`panneauActionHTML`— descriptors in, an
unknown block still throws (R56's refusal contract). The fiche transplants`openFiche`'s
template (refonte.html 39527-39697) into final JSX; its data reaches React through the
extended `window.__referentiel`publication; screen-over-screen return (fiche pushed on`/ajout?q=…`) is covered by a per-history-entry scroll memory in the shell.

**Tech Stack:** React 19, @tanstack/react-router ^1.170, @tanstack/store ^0.11, Vite 8,
Playwright harness (`command python3` = 3.12.4, chromium `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
**Recon:** all line numbers below were measured on `main` = `e89201bb` (recon session
2026-08-16); re-grep before editing — the anchor is the symbol, not the number.

## Global Constraints

- Gate of EVERY task that changes what is served: full suite green (48 scripts), with
  R59 (`retour.py`), R69 (`adresse_url.py`), R71 (`ecrans.py`) at UNCHANGED rule code.
  An exception is a recorded amendment in `regions.json`, never a workaround.
- Measurement ritual before ANY harness run (and after every source edit):
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
- One measuring process at a time. Static server stays `127.0.0.1:8899`; scratch ports
  8913/8917/8918 only. NEVER 8710/8711/8712.
- Python for harness: `command python3` (3.12.4). Node: `/Users/izno/.nvm/versions/node/v22.13.1/bin`.
- Comments in `design/` and `harness/`: English, timeless, no session references. UI
  copy quoted in comments stays French.
- Conventional Commits, scope `(shell-mobile)`, messages in French. Never chain
  commit/push to a gate in the same shell command. Verify the remote SHA after every
  push (SIGPIPE 141).
- Conversion at IDENTICAL markup and behaviour: same tag+class+id chains the legacy
  emitted. No visual change of any kind (SP5's question).
- `rg` on this repo ALWAYS carries a type/glob filter (`-g '*.html'`, `-g '*.py'`,
  `-g '*.tsx'`…) — an unfiltered rg scans a 14 GB fixture dir and crashes the machine.
- The store/hook conditions of the spec bind every task: domain hooks only door, alias
  keeps legacy reads, legacy `render()` never subscribed, world mutations notify via
  `render()`'s `magasin?.toucher()`.
- Local fast loop: `make test-impacte` exists since #440 for the python side; the
  harness has no impacted-mode — its fast smoke is the named-script subset per task.

---

### Task 1: Executed audits — B-024 reality post-SP4a, the sheet's reader map, the champ actions

No production code. Every finding lands in the task log (paste outputs) and, where a
registry entry changes, in `BUGS.md`.

**Files:**

- Modify: `BUGS.md` (B-024 entry: measured post-SP4a status)

**Interfaces:**

- Produces: the measured facts Tasks 3-6 build on. Specifically: (a) whether two layer
  history entries can be buried on any reachable walk today; (b) the exact list of
  fragment call sites of `openSheet`/`closeSheet`/`hideLayers` beyond the 10 producers;
  (c) the engine actions the `champ` block needs published.

- [ ] **Step 1: B-024 re-measure.** The claim (BUGS.md): `data-go` settles ONE entry
      while up to three layers close (refonte.html handler at `rg -n -g '*.html'
"dataset.go" frontend/maquette/design/refonte.html`, shape at ~17901-17927). Post-SP4a
      question: is any `data-go` control REACHABLE with ≥2 layer entries buried? Drive with a
      scratch probe (pattern of `harness/bugs.py`, port 8899, after the ritual): (i) open a
      sheet OVER a screen (fiche → long-press a cast/`data-panel` element, or `data-del` path);
      (ii) from that stack, locate any visible `[data-go]` control (`document.querySelector`
      in page context); (iii) if none is tappable, walk the four known producers (12174,
      12677, 12827, 12918 + user-sheet `cible:{go:"profil"}`) and record for each whether a
      second layer can sit under it. Paste the probe output. Verdict recorded in BUGS.md:
      « reproduisible » (walk pasted) or « latent, non atteignable » (each producer's reason).
- [ ] **Step 2: Sheet reader map.** `rg -n -g '*.py' "#sheet|\.sheet" frontend/maquette/harness/ | wc -l`
      and per-file list. Confirm every read is by SELECTOR (`.sheet`, `#sheet`, `#sheetin`,
      `#sheetgrab`, `#scrim`) and none asserts the element's PARENT (`.device > .sheet` or
      `nextElementSibling` chains). Any parent-shape assertion found = list it in the task
      log for Task 3's identical-emission checklist. Paste the grep.
- [ ] **Step 3: Fragment sheet-call map.** `rg -n -g '*.html' "openSheet\(|closeSheet\(|hideLayers\(" frontend/maquette/design/refonte.html`
      — expected ~10 producers + closers at data-go (~17911), data-del (~18331), data-fiche
      (~18340), surRetourEngine (~16646), hideLayers body (16315-16322), drag release
      (~40867), plus `mountSearch` call inside `openSheet` (16304). Paste; Task 3 Step 6
      consumes this list verbatim.
- [ ] **Step 4: The champ block's engine actions.** Read the `champ` branch of
      `panneauBlocHTML` (11772-11801) and `mountSearch`'s `.champsaisie` binding
      (16230-16238). List the engine functions the React block must call:
      expected `tousLesReglages`, `reglageId`, `valeurSaisie`, `modifierReglage`,
      `ouvrirReglage`. Confirm each exists (`rg -n -g '*.html' "function <nom>"`). Paste.
- [ ] **Step 5: Commit** (BUGS.md update only): `docs(shell-mobile): B-024 re-mesuré après SP4a — constat enregistré`

### Task 2: The référentiel widens — the fiche's data reaches React

**Files:**

- Modify: `frontend/maquette/design/refonte.html` (the `window.__referentiel`
  publication — find with `rg -n -g '*.html' "__referentiel" frontend/maquette/design/refonte.html`)
- Modify: `frontend/maquette/design/src/donnees.ts` (the `Referentiel` type)

**Interfaces:**

- Consumes: the audit's champ-action list (Task 1 Step 4).
- Produces (used by Tasks 3, 4, 5):
  - `window.__referentiel` gains: `sheetFor(titre: string): Fiche | null`,
    `saisonsDe(titre: string): [number, number | null, number][]`,
    `possedesDe(titre: string, saison: number): Set<number> | null`,
    `plages(nums: number[]): string`, `HEROS`, `POSTERS`, `ACTEURS`,
    `trailerIds`, `EP_LABEL`, `initials(nom: string): string`,
    `dateFR(iso: string): string`, `AUJOURDHUI: string`, `svgIcon(nom: string): string`,
    plus the panel actions: `tousLesReglages`, `reglageId`, `valeurSaisie`,
    `modifierReglage`, `ouvrirReglage` (exact names re-checked in Task 1).
  - `useReferentiel()` in `donnees.ts` returns the widened type (loose index types are
    acceptable where the legacy shape is untyped — `Record<string, unknown>` over `any`).

- [ ] **Step 1: Extend the publication** in the fragment: add the symbols above to the
      existing `window.__referentiel = { … }` object literal, no reordering of what is
      already there.
- [ ] **Step 2: Type them** in `donnees.ts`'s `Referentiel` type. `npm run typecheck` —
      zero errors.
- [ ] **Step 3: Rebuild + ritual + fast smoke** `command python3 frontend/maquette/harness/sweep.py` — green.
- [ ] **Step 4: Commit.** `feat(shell-mobile): le référentiel s'élargit — les données de la fiche joignables depuis React`

### Task 3: `<PanneauContenu>` — the unique constructor becomes a component

**Files:**

- Create: `frontend/maquette/design/src/composants/panneau.tsx`

**Interfaces:**

- Consumes: `useReferentiel()` (Task 2), `useEtat()`/`useMonde()` (SP4a).
- Produces (consumed by Task 4):
  - `type Descripteur = { titre?: string; sousTitre?: string; meta?: string;
puce?: unknown; affiche?: { t: string; k?: string }; avatar?: string;
blocs?: Bloc[] }` — mirror the exact key set `panneauHTML` reads (11808-11825);
    re-read the source before writing the type, the list above is the recon's.
  - `type Bloc` — the four declared kinds `note | faits | actions | saisons | champ`
    exactly as `panneauBlocHTML` (11772-11801) switches on them.
  - `function PanneauContenu({ descripteur }: { descripteur: Descripteur }): JSX.Element`
    — emits the SAME chains `panneauHTML` emits: `h3.sheettitle`, `span.sheetsub`,
    `p.sheetmeta`, chip, `.sheethead[.avecaffiche]` with `span.sheetposter` /
    `span.avatar.big`, then the blocks. **An unknown block type THROWS** (R56's refusal;
    the error surfaces through the layer's error boundary, and the existing
    `window.__panneauInconnu` probe keeps firing — read how the legacy sets it at 11805
    and reproduce the same signal before throwing).
  - Action rendering keeps the `cible` vocabulary verbatim: `cible: { fiche: X }` →
    `data-fiche="X"`, `cible: { go: X }` → `data-go="X"`, etc. — copy the mapping from
    `panneauActionHTML` (11756-11770). The document-level delegation stays the seam;
    the component adds NO onClick of its own for those.
  - The `saisons` block emits the same `button.ep[data-ep="titre|s|e|état"]` matrix as
    `seasonHTML` (39878-39904) so the episode popover path (delegated, `.eppop`
    appended to `#device` at ~39968) keeps working unchanged.
  - The `champ` block renders the input with an `onChange` calling the published
    engine actions (Task 2) — the one place mountSearch's `.champsaisie` binding
    (16230-16238) is replaced by a component-owned handler, same behavior: commit value,
    `modifierReglage`, reopen via `ouvrirReglage`.

- [ ] **Step 1: Read the three legacy builders in full** (`panneauActionHTML` 11756,
      `panneauBlocHTML` 11772, `panneauHTML` 11808; `richText`/`chipHTML`/`posterBox` as
      referenced). Transplant, do not translate: same tags, classes, attribute names,
      text-shaping helpers via the référentiel.
- [ ] **Step 2: Typecheck** (`npm run typecheck`) — zero errors. The component is not
      yet mounted anywhere; the build must stay green.
- [ ] **Step 3: Commit.** `feat(shell-mobile): PanneauContenu — le constructeur dérivé unique en composant (blocs déclarés, refus conservé)`

### Task 4: `<Feuille>` — the layer, the drag, the cutover of every producer

The atomic cutover: the React layer takes the ids, the envelope's originals leave, the
engine's sheet verbs route to the shell. One task, several commits, full suite at the end.

**Files:**

- Create: `frontend/maquette/design/src/composants/feuille.tsx`
- Modify: `frontend/maquette/design/src/coquille.tsx` (mount `<Feuille>`, expose
  `window.__panneau`)
- Modify: `frontend/maquette/design/src/magasin.ts` — NO shape change needed: the panel
  state lives in `etat` keys (`panneauDescripteur`, `panneauOuvert`) via `ecrire`
- Modify: `frontend/maquette/design/src/donnees.ts` (declare `__panneau` in the global
  block)
- Modify: `frontend/maquette/design/refonte.html` (markup: remove `#scrim`/`#sheet`
  cluster ~4484-4487; code: `openSheet`/`closeSheet` bodies, `hideLayers`,
  `surRetourEngine` sheet guard, drag block ~40850-40883, the 10 producers, closers per
  Task 1 Step 3's map)

**Interfaces:**

- Consumes: `PanneauContenu` (Task 3), `Descripteur`, the bridge (`__pont.coucher`),
  `deroulerCouche` semantics (engine-side latch — stays in the fragment).
- Produces:
  - `window.__panneau = { ouvrir(d: Descripteur): void; fermer(pop?: boolean): void;
ouverte(): boolean }` — the shell's sheet API. `ouvrir` writes
    `ecrire({ panneauDescripteur: d, panneauOuvert: true })` then
    `__pont.coucher("sheet")` (same order as legacy openSheet 16302-16310: DOM first,
    history second). `fermer(pop)` mirrors `closeSheet(pop)` 16353-16360: no-op when
    closed; `ecrire({ panneauOuvert: false })`; `if (!pop) window.__derouler("sheet")`.
  - `window.__derouler(nom: "sheet"): void` — thin fragment export of the existing
    `deroulerCouche` (16342-16351) so the latch bookkeeping stays engine-owned until
    SP4-end. (One line in the fragment: `window.__derouler = deroulerCouche;`)
  - `<Feuille>` renders ALWAYS (mounted with the shell), emitting EXACTLY:
    `<div id="scrim" className={"scrim" + (ouvert ? " open" : "")} />`
    `<aside id="sheet" className={"sheet" + (ouvert ? " open" : "") + (glisse ? " dragging" : "")}>`
    `  <div id="sheetgrab" className="sheetgrab" …pointer handlers… />`
    `  <div id="sheetin" className="sheetin"><PanneauContenu …/></div>`
    `</aside>`
    Content persists while closed (legacy keeps `#sheetin` innerHTML) — render the last
    descriptor when `panneauDescripteur != null`, even closed.
  - Drag port (from 40850-40883, threshold `SEUIL_FERMETURE = 70`): pointerdown on the
    grab → `setPointerCapture`, add `dragging` (kills the CSS transition, 2196);
    pointermove → inline `transform: translateY(dy)px` for dy > 0; release → clear
    `dragging` + inline transform, and `dy > 70 ? window.__panneau.fermer() : rien`
    (the CSS transition carries the settle both ways). Scrim click closes
    (`onClick={() => __panneau.fermer()}` — verify the legacy scrim does this:
    `rg -n -g '*.html' "scrim" frontend/maquette/design/refonte.html`, reproduce exactly
    what it does, including nothing).

- [ ] **Step 1: Write `<Feuille>` + `__panneau`** as above; mount `<Feuille>` in the
      root render next to the route outlet in `coquille.tsx`. Typecheck green. (Both sheet
      systems coexist for the next few minutes — never committed in that state.)
- [ ] **Step 2: The engine hands over.** In the fragment, following Task 1 Step 3's map:
      `openSheet(html)` body becomes a THROW (« openSheet est mort — passer par
      __panneau ») so any missed producer fails loud in dev, and every call site converts:
      the 10 producers `openSheet(panneauHTML({…}))` → `window.__panneau.ouvrir({…})`
      (the descriptor literal is ALREADY there — delete the `panneauHTML(` wrapper, keep
      the object); `closeSheet(pop)` calls → `window.__panneau.fermer(pop)`; `hideLayers`'s
      sheet lines → `window.__panneau.fermer(true)` equivalent (no history — check the
      legacy body 16315-6322 does DOM-only and mirror through a `fermer(true)`);
      `surRetourEngine`'s guard `#sheet` branch (~16646) → `if (window.__panneau?.ouverte()) { window.__panneau.fermer(true); return; }`
      keeping the guard ORDER (drawer → screen → sheet) untouched; the legacy drag block
      (~40850-40883) and `panneauHTML`/`panneauBlocHTML`/`panneauActionHTML`/`mountSearch`'s
      `.champsaisie` binding are DELETED (the component owns them); the envelope markup
      `#scrim/#sheet/#sheetgrab/#sheetin` (~4484-4487) is DELETED.
      `deroulerCouche` stays; add `window.__derouler = deroulerCouche;` next to the other
      window exports.
- [ ] **Step 3: Rebuild + ritual + targeted smoke:**
      `command python3 frontend/maquette/harness/panneau.py && command python3 frontend/maquette/harness/bugs.py && command python3 frontend/maquette/harness/glisse.py && command python3 frontend/maquette/harness/doigt.py && command python3 frontend/maquette/harness/retour.py`
      — R56's panel holds, the B-021/022 journeys, the sheet drag, gestures, and the
      unwind ladder, all against the React layer. Zero FAILED, zero rule-code edits.
- [ ] **Step 4: Cross-world stack proof** (scratch probe, pasted): open a LEGACY screen
      (releases via `__go("releases-suivi")` or the states table), long-press a card →
      panel opens; `document.elementFromPoint(195, 700)` names the sheet, not the screen
      (z-47 over z-45 across the #coquille boundary). Back closes the sheet, the screen
      stays. Paste both.
- [ ] **Step 5: FULL suite** (sequential, background, 48 scripts). Zero FAILED;
      R59/R69/R71 byte-identical (`git diff --stat frontend/maquette/harness/` empty).
- [ ] **Step 6: Commit.** `feat(shell-mobile): la feuille passe à la coquille — mêmes ids, mêmes chaînes, la glisse portée, dix producteurs recâblés`

### Task 5: `FicheEcran` — the route, the transplant, the scroll memory

**Files:**

- Create: `frontend/maquette/design/src/ecrans/fiche.tsx`
- Modify: `frontend/maquette/design/src/coquille.tsx` (route `/fiche/$titre`,
  `__ecrans.fiche`, scroll memory)
- Modify: `frontend/maquette/design/refonte.html` (delete `openFiche` 39527-39697;
  rewire its call sites; the `data-fiche` delegated branch 18336-18349; the
  `data-refiche` reopen at ~18035 and the `data-refiche` attribute emission die with
  the template)

**Interfaces:**

- Consumes: référentiel (Task 2), `__panneau` (Task 4), `aller()`/`__ecrans` (SP4a).
- Produces:
  - Route `/fiche/$titre` (percent-encoded, NFC) rendering `FicheEcran` inside the
    React root; NO search params in SP4b — measured fact: the legacy fiche has no open-
    season state, `<details open>` is computed per render (39504) and toggled natively.
  - `window.__ecrans.fiche(titre: string): void` →
    `aller({ to: "/fiche/$titre", params: { titre: titre.normalize("NFC") } })`.
  - `FicheEcran` emits the SAME chains as `openFiche`'s template:
    `<section className="screen open" data-cle={"fiche:" + titre}><div className="fichebar">…<button className="fback" onClick={() => window.__pont.retour()}>` then
    `.port > .body` with: `.herowrap[.noaffiche] > .herobg + .hero > h2.ht/p.hm/span.hn`;
    the trailer `<a className="trailer" href={youtube} target="_blank" rel="noopener" data-yt={key}>`
    (an `<a>` WITHOUT `data-navgo` — the delegated handler must not preventDefault it)
    or `p.nofiche`; synopsis `h2.h2 + p`; cast `.panel > .kv` + `div.cast[data-noswipe]`
    (attribute kept verbatim though it has no reader — identical markup); médiathèque
    `.panel > .kv` + the seasons; informations `.panel > .kv`; actions `.sheetacts.secondary`
    with `data-toast`/`data-del`/`data-follow`+`data-fkind` attributes VERBATIM (the
    delegation is the seam — no onClick), and the `ficheadd.done[disabled]` state.
    The dead `false ? … : ""` branch (39646-39665) is NOT ported (it emits nothing).
    The two DIFFERENT follow tests (baseTitle match at 39551 vs strict `t` at 39670)
    are ported faithfully, each with a one-line comment naming the asymmetry.
  - `SaisonsFiche` child component = `saisonsFicheHTML` (39415-39525) at identical
    emission (`details.season[open] > summary > span.sfr/span.miss`, `p.manquants`,
    `.panel > .eprow.<état> > .epdot/.en/.et/.ed`), `open` computed exactly as 39504.
  - `data-refiche` disappears: the React fiche re-renders from the store (the follow
    action ends in `render()` → `magasin.toucher()`), so the button flips without a
    reopen; the delegated branch's `if (closest.dataset.refiche) openFiche(...)` is
    deleted with it.
  - **Scroll memory** in `coquille.tsx`: a module map `Map<string, number>` keyed by the
    history entry key (`historique.location.state.key ?? pathname+search`); before each
    navigation commit (subscribe to `historique`), store the active screen `.port`'s
    `scrollTop`; after a POP back onto a stored key, restore in `requestAnimationFrame`
    and once more after pending `img` loads — mirror of the legacy re-apply
    (16428-16443). This is what makes fiche-over-ajout return land on the same scroll
    (the brief's « query et scroll compris »; the query is already carried by the URL).

- [ ] **Step 1: Transplant the template** (read 39527-39697 in full first) into
      `fiche.tsx` + `SaisonsFiche`. Data via `useReferentiel()`/`useMonde()`/`useEtat()`
      selections only. Typecheck green.
- [ ] **Step 2: Route + `__ecrans.fiche` + scroll memory** in `coquille.tsx`. The pop
      dispatcher needs NO change (ownership by entry shape — a router entry carries no
      `layer`/`tm`, `surRetourEngine` line ~16673 already no-ops it).
- [ ] **Step 3: Rewire the fragment.** Delete `function openFiche` (whole range) and its
      redraw registration; call sites: the delegated `data-fiche` branch (18336-18349)
      becomes `window.__panneau.fermer(); setTimeout(() => window.__ecrans.fiche(fiche), couche ? 260 : 0)`
      — keep the EXACT choreography (sheet-close before open, 260 ms only when a layer
      was open; re-read the branch and mirror it); the harness `__go` states
      (17145-17177) → `window.__ecrans.fiche(...)`; the `data-refiche` reopen (~18035)
      deleted. `rg -n -g '*.html' "openFiche" frontend/maquette/design/refonte.html`
      afterwards → zero hits.
- [ ] **Step 4: Rebuild + ritual + targeted smoke:**
      `command python3 frontend/maquette/harness/ecrans.py && command python3 frontend/maquette/harness/retour.py && command python3 frontend/maquette/harness/states.py && command python3 frontend/maquette/harness/images.py && command python3 frontend/maquette/harness/scroll.py`
      — the R71 journeys traverse the React fiche (fiche→profil stacks React-over-React
      now; releases→fiche legacy-over-React), the 74 states still drive, images draw.
- [ ] **Step 5: Screen-over-screen proof** (scratch probe, pasted): `/ajout?q=lucky`,
      scroll the results list to a non-zero offset, open a result's fiche (`data-fiche`
      tap), back → `/ajout?q=lucky` re-rendered, field filled, `.port.scrollTop` within
      ±2px of the stored offset. Paste the numbers.
- [ ] **Step 6: FULL suite. Zero FAILED; R59/R69/R71 byte-identical.**
- [ ] **Step 7: Commit.** `feat(shell-mobile): la fiche en route réelle — le centre du produit tient en React, mémoire de défilement au retour`

### Task 6: B-024 / B-025 / B-026 — the data-go debt, measured then paid

Shape depends on Task 1 Step 1's verdict; both branches are written here so the
implementer never improvises.

**Files:**

- Modify: `frontend/maquette/design/refonte.html` (the `data-go` handler ~17901-17927)
- Modify: `frontend/maquette/harness/bugs.py` (check 10b + the new holds)
- Modify: `frontend/maquette/regions.json` (record the amendment on the B-021/022 rule
  entry)
- Modify: `BUGS.md` (close or re-status the three entries)

**Interfaces:**

- Consumes: Task 1's B-024 verdict; `__panneau.fermer` (Task 4).
- Produces: a `data-go` that settles EXACTLY one history entry per buried layer entry,
  a Back-guarded 10b, a loud navigation-write failure.

- [ ] **Step 1 (B-026 first — smallest):** the handler's tail `catch (error) {}` (~17925)
      becomes `catch (error) { console.error("data-go: écriture de navigation échouée", error); window.__navEchec = true; }`
      and `noterLeChemin`'s own swallow (~16621) logs the same way. `window.__navEchec`
      is the probe the harness reads (initialised `false` next to the other probe flags —
      find them with `rg -n -g '*.html' "__panneauInconnu" frontend/maquette/design/refonte.html`).
- [ ] **Step 2 (B-024):** per the verdict: **if reproducible** — the close block counts
      the buried layer entries as it closes (drawer entry? sheet entry? each `coucher`-ed
      layer that is open = one entry) and, when N > 1, settles the extras with
      `history.go(-(N-1))` THROUGH a `__pont` helper (add `__pont.regler(n)` calling
      `historique.go(-n)`; a raw history call in the fragment would fall R74) BEFORE the
      final `remplacer` — with the `deroulementEnCours` latch raised so `surRetourEngine`
      ignores the announced pops (mirror `deroulerCouche`'s latch discipline). **If latent**
      (not reachable): the fix is NOT applied; the handler instead gains one comment line
      stating the single-entry assumption and the BUGS.md entry records « latent, tenu par
      le constat Task 1 — se règle avec la loi de propriété quand data-go migre (SP4d) ».
      Either way the comment overclaim named by the review (« handles screen over
      screen ») is corrected to what is true.
- [ ] **Step 3 (B-025):** `bugs.py` 10b extends: after the landing assertion, press Back
      once (`await pg.go_back()` idiom used by check 9b — copy it), assert the address
      and page are what one stood on BEFORE the add screen (the entry-count half of the
      fix). New sub-check label `10c. « …et un Back règle l'entrée »`.
- [ ] **Step 4: Mutations, executed and pasted.** (a) In the COPY's bundle is
      impractical — mutate at source per the R74/R76 precedent (recorded as manual):
      re-introduce a push instead of `remplacer` in the `data-go` layer branch → 10c
      falls naming the extra entry; restore. (b) Set the catch back to silent → drive a
      forced failure (stub `__pont.remplacer` to throw in page context) → the probe hold
      falls. Restore.
- [ ] **Step 5: Full suite** (bugs.py changed: its OWN diff is the amendment, recorded
      in `regions.json`). R59/R69/R71 untouched.
- [ ] **Step 6: Commit.** `fix(shell-mobile): B-024/025/026 — l'entrée par couche mesurée, le Back gardé au 10b, l'échec d'écriture parle`

### Task 7: B-027 / B-028 / B-029 — the tooling stops lying

**Files:**

- Modify: `frontend/maquette/resynchro.py` (title extraction + unmatched report)
- Modify: `frontend/maquette/harness/contenu.py` (counter rule word boundary)
- Modify: `BUGS.md` (close the three entries)

**Interfaces:**

- Produces: `resynchro.py` that extracts `t:` as the object's FIRST key with a
  string-aware scan and EXITS 1 listing unmatched titles; a `contenu.py` counter hold
  immune to « 1 » in « 11 ».

- [ ] **Step 1 (B-027):** the extraction anchors on the object's opening brace:
      `re.match(r'\s*\{\s*t:\s*"((?:[^"\\]|\\.)*)"', objet)` — first key must be `t`,
      escaped quotes handled; a non-`t` first key or a failed match RAISES with the
      object's head quoted (loud, not skipped).
- [ ] **Step 2 (B-028):** after the DB lookup pass, every FOLLOWS title with no DB row
      is collected; if any: print `N titre(s) jamais retrouvé(s): …` and `sys.exit(1)`.
      « 0 correction(s) » is only printed when every title matched.
- [ ] **Step 3 (B-029):** the counter hold compares NUMBERS, not substrings: extract
      with `re.search(rf'\b{n}\s+recherche', faits)` (word boundary) or parse the count
      out and compare `==`. Read the actual hold first (`rg -n -g '*.py' "recherche" frontend/maquette/harness/contenu.py`)
      and keep its message shape.
- [ ] **Step 4: Prove all three** (executed, pasted): (a) feed resynchro a scratch
      fragment copy whose first object key is not `t` → raises naming the object; (b)
      run against the real tree with one FOLLOWS title temporarily misspelled in a COPY →
      exit 1 naming it; (c) contenu.py against a copy where the embedded count is « 11 »
      and the real count 1 → the hold falls. Restore everything (`git status --short`
      clean).
- [ ] **Step 5: Run the real `resynchro.py`** (it may name true live drift after the
      wave's edits) — review, commit as data if it changed anything.
- [ ] **Step 6: Commit.** `fix(shell-mobile): B-027/028/029 — resynchro string-aware et bruyant sur l'inconnu, le compteur compare des nombres`

### Task 8: R75 extends to the fiche — deep entry measured

**Files:**

- Modify: `frontend/maquette/harness/adresses_ecrans.py` (R75)
- Modify: `frontend/maquette/regions.json` (record the extension)

**Interfaces:**

- Consumes: `harness/serveur.py` (SP4a) on port 8917; the fiche route (Task 5).
- Produces: R75 holds (f)-(j) for `/fiche`.

- [ ] **Step 1: New holds.** (f) deep `http://127.0.0.1:8917/fiche/<titre-réel-encodé>`
      cold → the fiche renders its promised title (`h2.ht` text equals the title) above
      the default page; (g) its hero/poster images draw (`complete && naturalWidth > 0`);
      (h) one Back lands on the default page `/`, screen gone, address `/`;
      (i) `/fiche/N'Existe%20Pas` renders the honest empty case at the address as typed
      — mirror what the legacy did for an unknown title: `sheetFor` null → re-read
      `openFiche` 39528-39533's null path and assert THAT, not an invented one;
      (j) a fiche with no trailer (`fiche-sans-trailer`'s title from the states table
      17173-17179) renders `p.nofiche`.
- [ ] **Step 2: Run R75** — all holds green against the rebuilt copy.
- [ ] **Step 3: Mutation, executed and pasted:** in the COPY, sever the route (rename
      the path to `/fiche2/$titre` in a scratch source build — the R76 manual-mutation
      precedent) → (f) falls naming the dead address; restore, rebuild.
- [ ] **Step 4: Record in `regions.json`** (R75 entry gains the fiche holds + the manual
      mutation note). Commit: `test(shell-mobile): R75 tient l'adresse de la fiche — entrée profonde, retour, cas vide honnête`

### Task 9: Wave gate — suite, docs, bump, PR

**Files:**

- Modify: `IMPLEMENTATION.md` (SP4b state), `frontend/maquette/README.md` (the panel
  API `__panneau`, the fiche route, the scroll memory — a short paragraph each),
  `personalscraper/__init__.py` (0.97.10 → 0.97.11)

- [ ] **Step 1: `resynchro.py`** once more (live counters drift during a wave) — review,
      commit as data if changed.
- [ ] **Step 2: FULL suite, sequential, output pasted.** Zero FAILED. `make check` green
      (unchanged python except the bump ⇒ fast). `make check-frontend` green.
- [ ] **Step 3: Residual greps, zero hits each** (paste):
      `rg -n -g '*.html' "openFiche|openSheet\(|panneauHTML|closeSheet\(" frontend/maquette/design/refonte.html`
      (only `__panneau`/`__ecrans` calls may remain), and `rg -n -g '*.py' "data-refiche" frontend/maquette/harness/`.
- [ ] **Step 4: Docs + bump commit.** `docs(shell-mobile): registre SP4b — la fiche et la feuille en composants, bump 0.97.11`
- [ ] **Step 5: Push (verify remote SHA), PR** titled
      `feat(shell-mobile): SP4b — la fiche et le panneau passent à la coquille`, CI green
      (the changes job should show python=false unless Task 7 touched `frontend/maquette`
      python only — resynchro/harness are NOT under `personalscraper/`; expect the fast
      lane: maquette=true, python=false — the first live proof of #440), adversarial
      review on the WHOLE diff (the orchestrator's own arbitrations are findings to
      contest), squash-merge on the standing instruction, post-merge live check on the
      design host (no `serve.py` change expected — restart only if it changed).

---

## Self-review notes (executed)

- Spec coverage: SP4b row of the waves table ✔ (fiche T5, panel-with-fiche T3/T4,
  legacy-sites-through-shell T4 Step 2); operator arbitrations 2026-08-16 ✔ (panel React
  = T3/T4; B-024/025/026 treated = T6; hygiene = T7); R75 extension ✔ (T8); every-wave
  invariants ✔ (store conditions in Global Constraints, R59/R69/R71 gates in T4/T5/T6).
- The `?saison=` search param the spec sketches is deliberately absent — measured: no
  such legacy state exists; recorded in T5's interface block.
- Type consistency: `Descripteur`/`Bloc` (T3) consumed by `__panneau.ouvrir` (T4);
  `__ecrans.fiche` name identical in T5 Steps 2-3 and T8; `window.__derouler` defined
  T4, consumed nowhere else (engine-internal latch stays).
- Placeholder scan: none — every step names its code, command, or the exact legacy
  range to transplant.
