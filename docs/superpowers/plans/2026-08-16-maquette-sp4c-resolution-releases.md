# SP4c — resolution + releases — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wave C of SP4 — the two arbitration-flow screens (`openResolve`, `openReleases`)
become the real routes `/resolution/$dossier` and `/releases/$titre` as final React
components; M11 (the Associer flow's double `history.back()` in one task) dies with the
rewrite; the rule ladders gain the two identities the day the screens move (SP4b lesson:
green blindness is fixed the same wave, never later).

**Architecture:** Same strangler pattern as SP4b: transplant at identical emission, the
document-level delegated click handler stays the seam (`data-resolve`, `data-laisser`,
`data-suivante`, `data-manual`, `data-prendre`, `data-profil` attributes verbatim), the
screens read through `useReferentiel()`/`useEtat()`/`useMonde()`; the mutable queue
(`derived.blocked()/stuck()`) and the actions (`actionResoudre`, `actionLaisser`,
`actionRecuperer`, `toast`) are published as FUNCTIONS on the référentiel (functions are
stable references; their return values track the live world, and every action already
ends in `render()` → `magasin.toucher()`, so React re-renders). Both screens gain the
identity `data-cle` they never had (`resolution:<dossier>`, `releases:<titre>`), which
is also what the harness ladders read.

**Tech Stack:** React 19, @tanstack/react-router ^1.170, @tanstack/store ^0.11, Vite 8,
Playwright harness (`command python3` = 3.12.4, chromium `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
(§Addresses names `/resolution/:dossier`, `/releases/:titre`).
**Recon:** measured 2026-08-16 on `main` = `9842e44d`; every line number below is an
anchor hint — re-grep the SYMBOL before editing.

## Global Constraints

- Gate of EVERY task that changes what is served: full suite green (48 scripts), R59
  (`retour.py`) / R69 (`adresse_url.py`) / R71 (`ecrans.py`) at UNCHANGED rule code —
  R71 does not traverse these screens, so no amendment is expected this wave; any
  exception is a recorded amendment in `regions.json`, never a workaround.
- Measurement ritual after every source edit, before any harness run:
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
- `command python3` for harness scripts; static server 127.0.0.1:8899 (already running);
  scratch ports 8913/8917/8918 only; NEVER 8710/8711/8712. One measuring process at a
  time. FOREGROUND every run — never background a suite and end a turn.
- `rg` ALWAYS with a glob filter (`-g '*.html'`, `-g '*.py'`, `-g '*.tsx'`);
  refonte.html ~40k lines: rg -n then narrow reads only.
- Conversion at IDENTICAL markup and behaviour: same tags/classes/attributes/texts;
  restore the whitespace text nodes at every legacy line-break point in inline
  containers (SP4b paid this three times — « Saison 33/13 »); `{" "}` where the legacy
  template broke lines inside flex/inline parents.
- Persistent-node discipline (SP4b lesson): any input/scrollable inside a route
  component keyed by business identity; scroll reset where legacy rebuilt innerHTML.
- Publication discipline: `function` declarations hoist; a `const` declared after the
  `__referentiel` site is published as a getter (TDZ — SP4b lesson). Never approximate
  an unpublished helper — publish the real one.
- Store conditions bind: hooks are the only component door; legacy `render()` stays
  explicitly called, never subscribed; world mutations notify via `render()`'s
  `magasin?.toucher()`.
- Comments English, timeless. Commits French Conventional, scope `(shell-mobile)`.
  Never chain commit/push with a gate in one command. Verify remote SHA after push.

---

### Task 1: The référentiel widens for the arbitration flow

**Files:**

- Modify: `frontend/maquette/design/refonte.html` (the `window.__referentiel` literal, ~15175)
- Modify: `frontend/maquette/design/src/donnees.ts`

**Interfaces:**

- Produces (consumed by Tasks 2-3): published on `__referentiel` —
  `DECISIONS_ATTENTE` (~10582), `DECISIONS_REGLEES` (~10448) — both `const` AFTER the
  publish site? CHECK POSITION: they are at ~10448-10651, publish site ~15175, so they
  are BEFORE it — plain shorthand OK; re-verify each. `MOTIF_LABEL`/`MOTIF_TON`/
  `MOTIF_POURQUOI` (~10407-10419), `ETAT_DECISION`/`ETAT_DECISION_POURQUOI`/`VIA_LABEL`
  (~10432-10442), `decisionEnAttente` (function ~39480, hoists), `derivedBlocked: () => …`
  and `derivedStuck: () => …` (thin arrows over `derived.blocked`/`derived.stuck`,
  ~11995 — publish as functions so the reference is stable and the return value live),
  `actionResoudre` (~11861), `actionLaisser` (~11843), `actionRecuperer` (~11799),
  `toast` (find it), `posterBox` (~4593), `chipHTML`.
- `donnees.ts`: types `DecisionCandidat { t; y; p; id; s; sans?; resume? }`,
  `DecisionAttente { d; k: "movie"|"show"; t; y?; motif; quand; c: DecisionCandidat[] }`,
  `DecisionReglee` (same + `etat`, `choix`), the label maps as `Record<string,string>`,
  the functions typed. Document in one comment that `etat.resolveTarget` and
  `etat.relTitre` are `string | null` (EtatUI stays loose; the readers cast as
  ajout.tsx:91 already does).

- [ ] **Step 1:** Verify each symbol's declaration position and kind (paste the rg
      lines); publish (getters ONLY where TDZ demands — expected: none, all are before
      the site or hoisting functions; prove it, don't assume it).
- [ ] **Step 2:** Type in donnees.ts; `npm run typecheck` zero errors.
- [ ] **Step 3:** Rebuild + ritual + `command python3 frontend/maquette/harness/sweep.py` green.
- [ ] **Step 4:** Commit: `feat(shell-mobile): le référentiel s'élargit au flux d'arbitrage — décisions, motifs, file vivante, actions`

### Task 2: `ReleasesEcran` — the simpler screen first

**Files:**

- Create: `frontend/maquette/design/src/ecrans/releases.tsx`
- Modify: `frontend/maquette/design/src/coquille.tsx` (route `/releases/$titre`,
  `__ecrans.releases`)
- Modify: `frontend/maquette/design/refonte.html` (delete `openReleases` ~39946-39982;
  rewire callers)

**Interfaces:**

- Consumes: `RELEASES` (already published), `baseTitle`, Task 1's `actionRecuperer`/`toast`.
- Produces: route `/releases/$titre` (percent-encoded, NFC) rendering `ReleasesEcran`
  emitting the EXACT legacy chains (~39949-39978): `.screen open` +
  `data-cle={"releases:" + titre}` wrapper (the identity the screen never had) >
  `.fichebar > button.fback` (onClick `window.__pont.retour()` — mirror fiche.tsx) +
  the right-aligned span; `.port > .body` > `.note`, `p.rescount` (hard-coded counts
  verbatim), `article.rel[.best on index 0]` rows (span.rn, span.rt chips, p.qhint on 0,
  `button.cfoot[data-prendre=index]` `.solid` on 0), `.empty > button.cfoot[data-profil]`.
  `window.__ecrans.releases(titre)` → `aller({ to: "/releases/$titre", params:
{ titre: titre.normalize("NFC") } })` — it ALSO writes `ecrire({ relTitre: titre })`
  first (the legacy first line, ~39947; the data-prendre branch reads it).

- [ ] **Step 1:** Transplant (read ~39946-39982 in full first). Typecheck.
- [ ] **Step 2:** Rewire the fragment (re-grep each): states table `ecran-releases`
      (~16851) → `window.__ecrans.releases("Silo")`; panel `data-releases` branch (~18030)
      → `window.__panneau.fermer(); setTimeout(() => window.__ecrans.releases(...), 260)`
      (keep the exact choreography); the `data-prendre` branch (~18052): `closeScreen()`
      becomes `window.__pont.retour()` (ONE router pop — the dispatcher no-ops it, the
      screen unmounts), keep `setTimeout(260)` → `actionRecuperer(state.relTitre)` + toast
      verbatim; the `data-profil` branch (~18033-18051): its legacy-vs-shell test
      `#screen.classList.contains("open")` no longer sees releases — rewrite the branch:
      if the RELEASES route is open (`window.__panneau.ouverte()`-style check is wrong
      here; test `document.querySelector('.screen.open[data-cle^="releases:"]')`),
      `window.__pont.retour()` then `setTimeout(260)` → `__ecrans.profil(profil)`; the
      sheet case keeps `__panneau.fermer()` + 260ms. Behaviour identical: grab closes the
      screen then acts; profil exits the screen then opens the route. Delete
      `function openReleases`. `rg -n -g '*.html' "openReleases"` → zero (paste).
- [ ] **Step 3:** Rebuild + ritual + targeted smoke:
      `command python3 frontend/maquette/harness/cartes.py && command python3 frontend/maquette/harness/actions.py && command python3 frontend/maquette/harness/retour.py` — zero FAILED.
- [ ] **Step 4:** Commit: `feat(shell-mobile): releases en route réelle — l'écran de choix de release tient dans la coquille`

### Task 3: `ResolutionEcran` — the arbitration centre

**Files:**

- Create: `frontend/maquette/design/src/ecrans/resolution.tsx`
- Modify: `frontend/maquette/design/src/coquille.tsx` (route `/resolution/$dossier`,
  `__ecrans.resolution`)
- Modify: `frontend/maquette/design/refonte.html` (delete `openResolve` ~39521-39595 +
  `decisionEnAttente`/`candidatsHTML` if they move; rewire the 6 call sites)

**Interfaces:**

- Consumes: Task 1's publications.
- Produces:
  - Route `/resolution/$dossier` (the folder name, percent-encoded, NFC) rendering
    `ResolutionEcran` at identical emission (~39542-39588): `.screen open` +
    `data-cle={"resolution:" + dossier}` > `.fichebar > .fback` (`__pont.retour()`);
    `.port > .body` with h2.h2>code (the folder), p.qhint (MOTIF_POURQUOI or the
    no-candidate line), .cmeta chips + « N sur M en attente », the candidate cards —
    `CarteRelease` component = `releaseCardHTML` (~11613-11637) at identical emission
    (`.card[data-nonmedia="candidat"]`, `button.cfoot.solid[data-resolve=<candidate t>]`)
    — or `p.rulenote`; `.empty > button.cfoot[data-manual=<dossier>]`;
    `.sheetacts.secondary` (data-laisser, data-suivante only when attente.length > 1);
    « Réglées récemment » via `CarteDecision` = `decisionCardHTML` (~11661-11694)
    identical. NO data-panel/data-fiche on any card (decision.py asserts it).
  - `window.__ecrans.resolution(dossier?)` → resolves the default like the legacy
    (`dossier ?? derivedStuck()[0]?.t` — same fallback, read through the published
    functions), writes `ecrire({ resolveTarget: <resolved> })` (legacy ~39522-39524),
    then `aller({ to: "/resolution/$dossier", params: { dossier: NFC } })`.
  - The screen's no-arg redraw semantics: the ROUTE param is the identity; an action
    that changes the queue re-renders via toucher (no reopen needed).

- [ ] **Step 1: Pre-read the data-resolve COLLISION** (mandatory, paste your finding):
      branch ~17973 (candidate title, reads state.resolveTarget) vs panel branch ~18367
      (folder). Read both AS THEY ARE and record what actually disambiguates them
      (order? a guard?). Your rewires must preserve exactly that.
- [ ] **Step 2:** Transplant (read the full ranges first: openResolve, candidatsHTML,
      releaseCardHTML, decisionCardHTML). Typecheck.
- [ ] **Step 3:** Rewire (re-grep each): states `arr-resolution` (~17023) →
      `__ecrans.resolution()` and `arr-decision` (~17036) → `__ecrans.resolution("Lucky")`;
      `data-suivante` (~17989): `closeScreen()` + `openResolve(suite.d)` becomes
      `aller`-with-replace via a new `__ecrans.resolutionSuivante(suite.d)`? NO — keep it
      one door: the branch calls `window.__ecrans.resolution(suite.d)` with `remplacer`
      semantics — extend `__ecrans.resolution(dossier, remplacer=false)` and pass true
      here (legacy = pop+push = net one entry; remplacer:true reproduces the depth).
      `data-resolve` candidate branch (~17973): `closeScreen()` → `window.__pont.retour()`,
      keep setTimeout(240) → actionResoudre(cible, …). `data-laisser` (~17981): same
      shape. `data-manual` (~17957): `closeScreen()` → `window.__pont.retour()`, keep the
      query-cleaning + `setTimeout(260)` → `__ecrans.ajout(trim, "identifier")`.
      `data-act="resolve"` (~18271) and the `.cfoot` text fallback (~18390) →
      `__ecrans.resolution(...)`. Panel `data-resolve` branch (~18367) keeps
      `__panneau.fermer()` + 260ms → `__ecrans.resolution(dataset.resolve)`.
      Delete `function openResolve`. `rg -n -g '*.html' "openResolve"` → zero (paste).
- [ ] **Step 4:** Rebuild + ritual + targeted smoke:
      `command python3 frontend/maquette/harness/decision.py && command python3 frontend/maquette/harness/actions.py && command python3 frontend/maquette/harness/bugs.py && command python3 frontend/maquette/harness/cartes.py` — zero FAILED (decision.py's journeys traverse the React screen).
- [ ] **Step 5:** Commit: `feat(shell-mobile): la résolution en route réelle — l'arbitrage tient dans la coquille`

### Task 4: M11 dies — one announced settlement, never two racing backs

**Files:**

- Modify: `frontend/maquette/design/src/coquille.tsx` (`__pont` gains `reculer(n)`)
- Modify: `frontend/maquette/design/refonte.html` (the `add:` identifier branch
  ~18276-18309)
- Modify: `frontend/maquette/harness/ident.py` (the history hold)
- Modify: `frontend/maquette/regions.json` (record)

**Interfaces:**

- Produces: `window.__pont.reculer(n: number): void` — announces n pops to the engine's
  latch (`deroulementEnCours += n` equivalent — expose the increment via a fragment
  export `window.__annoncerPops(n)` next to `window.__derouler`, since the latch lives
  engine-side) then `historique.go(-n)` + flush. R76's spirit: one logical navigation,
  one history operation.
- The Associer branch becomes: `state.added.add(index); magasin.toucher();` then ONE
  settlement for BOTH entries (the sheet layer entry + the `/ajout` route entry):
  `window.__panneau.fermer(true)` (DOM only, pop=true — no unwind) then
  `window.__pont.reculer(2)`; keep `setTimeout(260)` → `actionResoudre(cible, result.t)`
  - toast. (The legacy double-back popped sheet-then-ajout; reculer(2) settles the same
    two entries in one go, latched, no race.)

- [ ] **Step 1: Reproduce M11 first** (scratch probe, pasted): walk the Associer flow on
      the CURRENT build and measure the double-settlement (after Associer, read the
      address + one extra Back's landing — record what today does; this is the BEFORE).
- [ ] **Step 2:** Implement `reculer(n)` + `__annoncerPops(n)` + the branch rewrite.
      CAUTION: verify against the CURRENT branch code (Task 3 may have touched
      neighbours); the sheet entry exists only when the panel was open — read the branch's
      guards; if the panel entry is conditional, count n accordingly (read
      `window.__panneau.ouverte()` BEFORE fermer).
- [ ] **Step 3:** ident.py gains the history hold: after Associer, the address is what
      one stood on BEFORE `/ajout` (the arr page), and ONE further Back does exactly one
      step (no toast d'expulsion, no skipped entry — reuse retour.py's observed-state
      counting idiom). Run ident.py → green; paste.
- [ ] **Step 4: Mutation, executed and pasted:** restore the raw double `retour()` in
      the source (manual mutation per precedent), rebuild → the new hold falls naming the
      double settlement; restore, rebuild, rerun → green. Record in regions.json (the
      rule entry that owns ident.py) + note `reculer` under R76's entry (the helper is
      the sanctioned multi-entry navigation door; bare navigate/history stays forbidden).
- [ ] **Step 5:** Commit: `fix(shell-mobile): M11 — le flux Associer règle ses deux entrées d'un seul geste annoncé`

### Task 5: The ladders gain the two identities + R75 holds the two routes

**Files:**

- Modify: `frontend/maquette/harness/audit.py`, `audit2.py`, `dest.py`, `states.py`,
  `surfaces.py` (root ladders + R8 couches: add `.screen.open[data-cle^="resolution:"]`
  and `.screen.open[data-cle^="releases:"]`, ladder-LAST, mirroring the fiche/ajout rungs)
- Modify: `frontend/maquette/harness/ident.py` (the `#screen .h2`/`#screen #addq` reads
  → identity reads for the resolution screen; /ajout reads already identity-based? read
  the file — fix what still reads `#screen` for surfaces that are now routes)
- Modify: `frontend/maquette/harness/adresses_ecrans.py` (R75: deep entry
  `/resolution/<dossier-encodé>` renders the promised folder (h2 code text), back lands
  on `/`; deep `/releases/<titre>` renders the release list with the title in the bar;
  wrong deep values render the screens' honest empty cases at the address as typed —
  read what each screen does with an unknown param and assert THAT)
- Modify: `frontend/maquette/regions.json` (records for every touched rule)

- [ ] **Step 1:** Ladder rungs ×5 files + ident.py identity reads. Run the five + ident
      foreground; paste tails. Coverage proof for ONE ladder script on `arr-resolution`
      (before/after read counts, the SP4b proof shape).
- [ ] **Step 2:** R75 extension + one executed mutation (sever ONE of the two routes in
      the copy-source, the hold falls naming it; restore, green). Paste.
- [ ] **Step 3:** regions.json records. Commit:
      `test(shell-mobile): les règles suivent l'arbitrage à ses adresses — échelles, ident par identité, R75 aux deux routes`

### Task 6: Wave gate

**Files:**

- Modify: `IMPLEMENTATION.md`, `frontend/maquette/README.md` (the two routes, reculer),
  `personalscraper/__init__.py` (0.97.11 → 0.97.12)

- [ ] **Step 1:** `command python3 frontend/maquette/resynchro.py` (loud since SP4b) —
      review/commit as data if it changed anything.
- [ ] **Step 2:** FULL suite (48 scripts, sequential, foreground) — zero FAILED, tally
      pasted. `make check` green; `make check-frontend` green.
- [ ] **Step 3:** Residual greps, zero hits (paste):
      `rg -n -g '*.html' "openResolve|openReleases" frontend/maquette/design/refonte.html`.
      R59/R69/R71 byte-identical vs 9842e44d (`git diff --stat` on the three files — empty).
- [ ] **Step 4:** Docs + bump commit:
      `docs(shell-mobile): registre SP4c — l'arbitrage dans la coquille, bump 0.97.12`.
      (Push/PR/merge = controller, after the final adversarial review.)

---

## Self-review notes (executed)

- Spec coverage: waves table SP4c row ✔ (two screens as routes T2/T3); §Addresses'
  `/resolution/:dossier` + `/releases/:titre` ✔; M11's natural death ✔ (T4, with the
  announced-multi-pop replacing the racing backs); every-wave invariants ✔ (Global
  Constraints; R71 untouched — it does not traverse these screens per recon §5).
- The `data-resolve` collision is a named mandatory pre-read (T3 Step 1), not an
  assumption. The `data-profil` legacy-vs-shell branch flip is called out (T2 Step 2).
- Type consistency: `__ecrans.releases(titre)` / `__ecrans.resolution(dossier?,
remplacer?)` names used identically in T2/T3/T5; `reculer(n)`/`__annoncerPops(n)`
  defined T4, consumed nowhere else.
- SP4b lessons carried: identity rungs land the SAME wave (T5); whitespace text nodes
  and persistent-node keys are Global Constraints; publication TDZ check is T1 Step 1.
