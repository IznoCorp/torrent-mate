# SP4a — the machinery + the Profil/Ajout pilots — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wave A of SP4 — the state store, the boot inversion, real routes with SPA
fallback, the navigation helper, the two pilot screens (Profil then Ajout) as final React
components, and the rules that hold all of it.

**Architecture:** The TanStack Store (typed, in `design/src/`) owns the state from this
wave; the legacy engine receives it through an explicit boot handshake
(`window.__demarrerMoteur(deps)`) that replaces SP3's queue-and-replay pre-bridge. Screens
become path routes (`/profil/$titre`, `/ajout`); the shell's `aller()` helper is the only
programmatic navigator; migrated screens render inside the React root at markup identical
to what the legacy emitted, so the 45 rules stay green with unchanged rule code.

**Tech Stack:** React 19, @tanstack/react-router ^1.170, @tanstack/store ^0.11 (synchronous
notification PROVEN at plan time: subscriber runs inside `setState`, read-after-write via a
module alias is correct in the same function), Vite 8, Playwright (command python3 =
3.12.4, chromium `channel="chrome"`).

**Spec:** `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`

## Global Constraints

- Gate of EVERY task that changes what is served: full suite green, with R59
  (`retour.py`), R69 (`adresse_url.py`), R71 (`ecrans.py`) at UNCHANGED rule code. An
  exception is a recorded amendment in `regions.json`, never a workaround.
- Measurement ritual before ANY harness run (and after every source edit):
  `cd frontend/maquette/design && npm run build && cp dist/index.html /tmp/tm-refonte/wrapped.html && rm -rf /tmp/tm-refonte/vite && cp -R dist/vite /tmp/tm-refonte/vite`
- One measuring process at a time. Static server stays `127.0.0.1:8899`; scratch ports
  8913/8917/8918 only. NEVER 8710/8711/8712.
- Python for harness: `command python3` (3.12.4). Node: `/Users/izno/.nvm/versions/node/v22.13.1/bin`.
- Comments in `design/` and `harness/`: English, timeless, no session references. UI copy
  quoted in comments stays French.
- Conventional Commits, scope `(shell-mobile)`, messages in French. Never chain
  commit/push to a gate in the same shell command. Verify the remote SHA after every push.
- Source of truth being edited: `design/refonte.html` (fragment), `design/index.html`
  (envelope), `design/src/*` (shell). The host serves this checkout live — leave the tree
  buildable at every commit.
- `state` in the fragment is module-global to its IIFE but readable from page context in
  probes (`state.page`) — existing rules rely on that; keep the alias named `state`.
- If a run of `contenu.py` names a search-count drift, run
  `command python3 frontend/maquette/resynchro.py`, review, commit as data — it is live
  drift, not your regression.

---

### Task 1: Konsta UI spike — verdict, throwaway

**Files:**

- Create (scratchpad only, NEVER committed): `konsta-spike/` in the session scratchpad
- Modify: `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`
  (append a « Spike verdicts » section)

**Interfaces:**

- Produces: a recorded verdict in the spec. No code survives.

- [ ] **Step 1: Build the probe.** In the scratchpad, `npm create vite@latest konsta-spike -- --template react-ts`, `npm i konsta`. Render ONE screen: a Konsta `Page` + `Navbar` + a list of 3 `ListItem` cards at 390×844, next to a hand-written div using the maquette's card metrics (poster 49×73.5, padding 9, radius 8, title 13.5px, gap 10 — R47's numbers).
- [ ] **Step 2: Measure, don't opine.** With a 10-line Playwright script (pattern of `harness/commun.py`, chromium `channel="chrome"`, 390×844): `getBoundingClientRect` + `getComputedStyle` (padding, border-radius, font-size) of the Konsta card vs the R47 numbers. Paste the numbers.
- [ ] **Step 3: Answer the two questions in the spec's terms.** (a) Can Konsta components carry the maquette's EXACT geometry and class chains without fighting the library? (b) What would R47/R50's oracles say about a Konsta-rendered list? Expected finding: Konsta imposes its own visual system (iOS/Material theming, own class vocabulary) — incompatible with a pixel-reference maquette whose markup IS the contract; adopting it would amend every geometry rule. Write the verdict either way — the numbers decide, not the prior.
- [ ] **Step 4: Record.** Append to the spec, under « Spike verdicts (wave A) »: the numbers, the verdict, one paragraph of why. Delete the scratchpad project. Commit: `docs(shell-mobile): verdict du spike Konsta UI`.

### Task 2: Motion spike — verdict, throwaway

**Files:**

- Modify: `docs/superpowers/specs/2026-08-15-maquette-sp4-vider-attrape-tout-design.md`

**Interfaces:**

- Produces: a recorded verdict. No dependency added in this wave.

- [ ] **Step 1: Inventory what animates today.** `grep -n "animation\|transition" frontend/maquette/design/refonte.html | grep -v "^\s*//"` — list the distinct animated mechanisms (screen slide, sheet rise, skeleton shimmer, splash bar, row swipe settle…) and note that every one is CSS (+ rAF for gesture-driven settles).
- [ ] **Step 2: State the adoption test.** Motion (the React animation library) earns entry only when a MIGRATED component needs an animation that CSS transitions + the existing gesture code cannot express (spring-physics interruptible transitions, layout animations). The pilots (Profil, Ajout) reuse the CSS `.screen` transitions — measured by the suite, unchanged.
- [ ] **Step 3: Record.** Append the verdict to the spec's « Spike verdicts (wave A) »: expected « pas d'adoption en SP4a; ré-évaluation au premier besoin réel nommé, par amendement ». Commit: `docs(shell-mobile): verdict du spike Motion`.

### Task 3: The store module — `magasin.ts`

**Files:**

- Modify: `frontend/maquette/design/package.json` (add `"@tanstack/store": "^0.11.1"` to dependencies)
- Create: `frontend/maquette/design/src/magasin.ts`

**Interfaces:**

- Produces (consumed by Tasks 4, 5, 6, 9):
  - `type EtatUI = { page: string; [cle: string]: unknown }` — the legacy UI-state shape,
    typed loosely on purpose: its keys belong to the engine until its surfaces migrate.
  - `creerMagasin(): Magasin` where `Magasin = { store: Store<Contenu>; lire(): Contenu;
ecrire(patch: Partial<EtatUI>): void; adopterEtat(initial: EtatUI): void;
adopterMonde(monde: unknown): void; toucher(): void }`
  - `Contenu = { etat: EtatUI; monde: unknown; version: number }`

- [ ] **Step 1: Install.** `cd frontend/maquette/design && npm i @tanstack/store@^0.11.1`
- [ ] **Step 2: Write the module.**

```ts
// design/src/magasin.ts
// The single owner of the mutable state. The legacy engine receives this
// through the boot handshake and keeps a synchronous read alias; React reads
// through the domain hooks. `version` exists because the simulated WORLD is
// mutated in place by the engine's actions — a bump is how a change that did
// not replace any reference still reaches every subscriber.
import { Store } from "@tanstack/store";

export type EtatUI = { page: string; [cle: string]: unknown };
export type Contenu = { etat: EtatUI; monde: unknown; version: number };

export type Magasin = {
  store: Store<Contenu>;
  lire(): Contenu;
  ecrire(patch: Partial<EtatUI>): void;
  adopterEtat(initial: EtatUI): void;
  adopterMonde(monde: unknown): void;
  toucher(): void;
};

export function creerMagasin(): Magasin {
  const store = new Store<Contenu>({
    etat: { page: "acq" },
    monde: null,
    version: 0,
  });
  return {
    store,
    lire: () => store.state,
    ecrire: (patch) =>
      store.setState((prev) => ({
        ...prev,
        etat: { ...prev.etat, ...patch },
        version: prev.version + 1,
      })),
    adopterEtat: (initial) =>
      store.setState((prev) => ({
        ...prev,
        etat: initial,
        version: prev.version + 1,
      })),
    adopterMonde: (monde) =>
      store.setState((prev) => ({ ...prev, monde, version: prev.version + 1 })),
    toucher: () =>
      store.setState((prev) => ({ ...prev, version: prev.version + 1 })),
  };
}
```

- [ ] **Step 3: Typecheck.** `npm run typecheck` — zero errors.
- [ ] **Step 4: Commit.** `git add design/package.json design/package-lock.json design/src/magasin.ts && git commit -m "feat(shell-mobile): le magasin — TanStack Store propriétaire de l'état"`

### Task 4: Boot inversion — the engine waits for the shell, the pre-bridge retires

**Files:**

- Modify: `frontend/maquette/design/refonte.html` (boot tail: the block starting at
  `Object.assign(state, etatDeLURL());` — find with `grep -n "etatDeLURL());" refonte.html`
  — through the final boot writes ending after the `__pont.noter(etatDeNavigation(), adresseDArrivee)` try-block)
- Modify: `frontend/maquette/design/index.html` (remove the `__rejouerLePont` recorder
  script block, around lines 80–95)
- Modify: `frontend/maquette/design/src/coquille.tsx`
- Modify: `frontend/maquette/harness/pont.py` (R74 amendment)
- Modify: `frontend/maquette/regions.json` (record the amendment)

**Interfaces:**

- Consumes: `creerMagasin` from Task 3.
- Produces: `window.__demarrerMoteur(deps: { magasin: Magasin }): void` defined by the
  fragment; called EXACTLY ONCE by the shell after `window.__pont` is real. The startup
  screen (already first in the frame) stays up until the engine's first render — a module
  that never evaluates leaves it visible, which is the truthful failure state.

- [ ] **Step 1: Amend R74 first (TDD at rule level).** In `pont.py`: retire the `pret` probe holds (the replay is about to not exist); add hold (e′): with the copy's module entry severed (the mutation replaces the `<script type="module"...>` src with a non-existent file IN THE COPY), the startup screen `#splash` is still visible after load — the fail-silent path is dead. Add hold (f′): on the intact copy, `typeof window.__demarrerMoteur === "function"` AND `#splash` is hidden after `__chargementTermine` — the handshake exists and was called. Run `command python3 pont.py` — the new holds FAIL against the current build (no `__demarrerMoteur` yet). Paste the failure.
- [ ] **Step 2: Wrap the boot tail.** In `refonte.html`, wrap the boot block in:

```js
/* The engine no longer boots itself. The shell — store created, bridge
     real — starts it, so no write ever needs recording and replaying, and a
     module that never evaluates leaves the startup screen on screen: a
     visible, truthful failure instead of an app with mute verbs. */
window.__demarrerMoteur = function (deps) {
  magasin = deps.magasin;
  magasin.adopterEtat(state);
  magasin.adopterMonde(world);
  state = magasin.lire().etat;
  magasin.store.subscribe(() => {
    state = magasin.lire().etat;
  });
  /* …the existing boot tail, verbatim: Object.assign(state, etatDeLURL());
       adresseDArrivee; render(); __pont.remplacer(...); __chargementTermine();
       guard entry; __pont.noter(...); the welcome hint block… */
};
```

with, near the top of the IIFE (next to `let world = null;`): `let magasin = null;`.
NOTE: `Object.assign(state, etatDeLURL())` mutates the etat object in place at boot —
acceptable for the boot instant (before any subscriber exists it is invisible); every
POST-boot write converts in Task 5.

- [ ] **Step 3: Remove the pre-bridge from the envelope.** Delete the recorder
      `<script>` block (`window.__pont` queue + `window.__rejouerLePont`) from `index.html`.
- [ ] **Step 4: The shell starts the engine.** In `coquille.tsx`: delete the
      `__rejouerLePont` replay block and the `pret` marker; after `window.__pont = {...}` and
      BEFORE `ReactDOM.createRoot(...)`, add:

```tsx
import { creerMagasin } from "./magasin";
// …
const magasin = creerMagasin();
window.__magasin = magasin; // the domain hooks and the probes read through this
const demarrer = window.__demarrerMoteur;
if (typeof demarrer === "function") demarrer({ magasin });
```

and extend the `declare global` block: `__demarrerMoteur?: (deps: { magasin: Magasin }) => void; __magasin: Magasin;`. Remove `__rejouerLePont` from it.

- [ ] **Step 5: Rebuild + ritual + run the amended R74.** `command python3 pont.py` — all holds green, including the two new ones. Run the severed-module mutation by hand on the copy; paste the fall naming `#splash`.
- [ ] **Step 6: Record the amendment** in `regions.json` under R74's entry: pre-bridge
      retired with the boot inversion; `pret` probe replaced by the splash-visible hold.
- [ ] **Step 7: Full suite** (background, sequential). Zero FAILED. R59/R69/R71 untouched.
- [ ] **Step 8: Commit.** `git commit -m "refactor(shell-mobile): l'inversion du démarrage — le moteur attend la coquille, le pré-pont se retire"`

### Task 5: The write sites — the store owns every post-boot write

**Files:**

- Modify: `frontend/maquette/design/refonte.html`

**Interfaces:**

- Consumes: `magasin` (Task 4's handshake).
- Produces: zero direct post-boot writes to `state`; the invariant later tasks (hooks,
  pilots) build on. The alias keeps every read working unchanged.

- [ ] **Step 1: Inventory, exactly.** `grep -nE 'state\.[a-zA-Z]+ *[-+]?=[^=]|Object\.assign\(state' frontend/maquette/design/refonte.html` — expect ≈64 direct writes + 3 `Object.assign` (one is the boot-time one from Task 4, which stays). Paste the list into the task log.
- [ ] **Step 2: Convert in bounded batches** (≤15 sites per batch, one commit each).
      `state.x = v;` → `magasin.ecrire({ x: v });` · compound (`state.libCount -= …`,
      `state.n += 1`) → read-then-write via the alias: `magasin.ecrire({ libCount: state.libCount - PAGE });` ·
      `Object.assign(state, patch)` in `applyState` → `magasin.ecrire(patch);` · Set/Map
      mutations on state fields (`state.added.add(i)`, `state.sugGone.add(…)`) keep the
      in-place call and follow it with `magasin.toucher();` (the reference did not change;
      the bump is what reaches React). `world.*` in-place mutations (`follows.splice`…)
      need NO per-site edit: `render()` gets ONE line at its top — `magasin?.toucher();` —
      every action already ends in `render()`, so every simulated mutation notifies (spec
      condition 4) while the legacy render stays explicitly called (condition 3).
- [ ] **Step 3: After each batch:** rebuild + ritual + `command python3 bugs.py && command python3 actions.py && command python3 retour.py` (the fast behavioral smoke), then the FULL suite once per 2-3 batches and at the end. Zero FAILED, rule code unchanged.
- [ ] **Step 4: Prove the alias invariant.** One scratch probe: drive `acq-suivis-liste`,
      in page context run `magasin = window.__magasin; const avant = state.page;
magasin.ecrire({page:'lib'}); state.page` → must answer `'lib'` synchronously. Paste.
- [ ] **Step 5: Final commit** of the batch series: `refactor(shell-mobile): les écritures d'état passent au magasin, l'alias garde les lectures`

### Task 6: Domain hooks — `donnees.ts`

**Files:**

- Create: `frontend/maquette/design/src/donnees.ts`

**Interfaces:**

- Consumes: `window.__magasin` (Task 4).
- Produces (the ONLY door components may use — spec condition 1):
  - `useContenu<T>(selection: (c: Contenu) => T): T`
  - `useEtat(): EtatUI` and `useMonde(): unknown` (thin wrappers)

- [ ] **Step 1: Write the module.**

```ts
// design/src/donnees.ts
// The domain hooks are the single door between components and the store.
// Their IMPLEMENTATION is what the backend-binding mission will replace;
// components must never reach around them to the store or the engine.
import { useSyncExternalStore } from "react";
import type { Contenu, EtatUI } from "./magasin";

function sabonner(rappel: () => void): () => void {
  return window.__magasin.store.subscribe(rappel);
}

export function useContenu<T>(selection: (c: Contenu) => T): T {
  // `version` bumps on every write INCLUDING in-place world mutations, so a
  // selector over a mutated-in-place object still re-reads: the snapshot the
  // comparison sees is the selected value, re-derived per notification.
  return useSyncExternalStore(sabonner, () =>
    selection(window.__magasin.lire()),
  );
}

export const useEtat = (): EtatUI => useContenu((c) => c.etat);
export const useMonde = (): unknown => useContenu((c) => c.monde);
```

CAUTION (React contract): `useSyncExternalStore` compares snapshots by `Object.is`.
A selector must return a STABLE reference for unchanged data — selecting `c.etat` is
stable (the store replaces it only on `ecrire`); selecting a fresh object/array literal
per call would loop. Components select the narrowest stable slice.

- [ ] **Step 2: Typecheck** (`npm run typecheck`), rebuild, ritual, quick sweep (`command python3 sweep.py`).
- [ ] **Step 3: Commit.** `feat(shell-mobile): les hooks de domaine — la seule porte des composants`

### Task 7: The host serves any address — SPA fallback, `<base>`, favicon, the /assets/ portal hold

**Files:**

- Modify: `frontend/maquette/serve.py` (the `if chemin not in ("/", "/index.html"):` block
  currently answering 303 → `/`)
- Modify: `frontend/maquette/design/index.html` (add `<base href="/" />` as the FIRST
  element of `<head>`, before the PWA block; add `<link rel="icon" href="/favicon.svg" />`
  inside the pwa markers if absent)
- Modify: `frontend/maquette/harness/bascule.py` (R73 amendment)
- Modify: `frontend/maquette/regions.json`

**Interfaces:**

- Produces: GET on an unknown non-asset, non-reserved path answers the DOCUMENT (200,
  session-gated exactly like `/`); `/favicon.svg` answers 200 with the brand icon;
  unauthenticated `/assets/…` answers 401 (the permanent portal rule, now held).

- [ ] **Step 1: Amend R73 first.** In `bascule.py` (it already boots `serve.py` against a
      scratch root with `TM_DESIGN_RACINE`): add holds — (fallback) GET `/fiche/Quoi%20Que`
      with a session answers 200 and the SAME bytes as `/`; without a session answers the
      login page like `/` does; (favicon) GET `/favicon.svg` answers 200 `image/svg+xml`;
      (portal) GET `/assets/x.webp` WITHOUT a session answers 401 — never the login page,
      never the file. Run → the fallback and favicon holds FAIL (303/404 today). Paste.
- [ ] **Step 2: Implement in `serve.py`.** Replace the 303 tail: reserved paths keep
      their routes (everything already matched above the block); `/connexion` GET keeps
      redirecting to `/` (a reload after POST must not 200 a phantom page — keep exactly the
      current special case by matching it BEFORE the fallback). Unknown paths fall through to
      the same code that serves `/` (session check → login page or document). Add
      `favicon.svg` to the no-session brand `ASSETS` map, serving the existing brand SVG
      (`frontend/` icon set — reuse the file the manifest's icons derive from; if only PNGs
      exist, serve the maskable SVG source used by `make-design-icons.py`, checked at
      implementation).
- [ ] **Step 3: `<base href="/">` in the envelope.** The fragment's 924 image references
      are RELATIVE (`assets/…`); at `/fiche/X` they would resolve to `/fiche/assets/…`. The
      base element pins resolution to the root for every relative URL in the document —
      one line, covering markup and future route depths alike.
- [ ] **Step 4: Rebuild + ritual + R73 green + full suite** (the base element changes URL
      resolution everywhere — the whole suite is the only honest gate). `pm2 restart torrentmate-design` afterwards, live check `curl --connect-timeout 10 --max-time 30 -s -o /dev/null -w '%{http_code}' https://tm-design.iznogoudatall.xyz/fiche/test` → 401 (login, not 404).
- [ ] **Step 5: Record R73's amendment in `regions.json`; commit.** `feat(shell-mobile): l'hôte sert toute adresse — fallback SPA, base, favicon, portail /assets/ tenu`

### Task 8: The harness server — deep paths measurable

**Files:**

- Create: `frontend/maquette/harness/serveur.py`

**Interfaces:**

- Produces: `demarrer_serveur(port: int, racine: pathlib.Path) -> contextmanager` — a
  thread-backed static server: files under `racine` served as-is; any extensionless path
  answers `racine/wrapped.html`. Consumed by R75 (Task 10) on scratch port 8917. The
  global 8899 server stays untouched — 45 rules point at it.

- [ ] **Step 1: Write it** (http.server ThreadingHTTPServer subclass, ~40 lines: override
      `translate_path`; if the resolved file does not exist and the path has no `.`, serve
      `wrapped.html`; else defer to the parent).
- [ ] **Step 2: Prove it inline** (its own `__main__`: start on 8917, GET `/profil/X%20Y`
      → 200 + wrapped bytes; GET `/vite/<bundle>.js` → 200 js; GET `/absent.png` → 404), run
      it, paste, stop.
- [ ] **Step 3: Commit.** `feat(shell-mobile): serveur du harnais — le fallback qui rend la table de routes mesurable`

### Task 9: The Profil pilot — first real route, `aller()`, the screen leaves the fragment

**Files:**

- Modify: `frontend/maquette/design/src/coquille.tsx` (route `/profil/$titre`, `aller()`,
  `window.__ecrans`)
- Create: `frontend/maquette/design/src/ecrans/profil.tsx`
- Modify: `frontend/maquette/design/refonte.html` (remove `openProfil`'s body; rewire its
  call sites — `grep -n "openProfil" refonte.html`)

**Interfaces:**

- Consumes: hooks (Task 6), handshake (Task 4).
- Produces:
  - `aller(vers: { to: string; params?: Record<string,string>; search?: Record<string,unknown>; remplacer?: boolean }): void`
    — the ONLY programmatic navigator in `src/`; navigates then `historique.flush()`.
  - `window.__ecrans.profil(titre: string): void` — what legacy call sites invoke.
  - Route `/profil/$titre` (percent-encoded, NFC-normalised param) rendering
    `ProfilEcran` INSIDE the React root, markup identical to the legacy screen
    (`.screen.open > .port` chain with the same classes, so the CSS and the rules apply
    unchanged).

- [ ] **Step 1: Transplant, do not translate.** Read `openProfil`'s template
      (`refonte.html`, `grep -n "function openProfil"` — through its `openScreen(...)` call).
      Write `ProfilEcran` as final JSX emitting the SAME tag+class chains; data via
      `useMonde()`/`useEtat()` selections, never via the engine. The screen container: the
      route component renders `<section className="screen open" data-cle="profil"><div className="port">…`
      — the same element shape `#screen` carries, as a SIBLING layer inside `#coquille`
      (z-index between the page and the legacy `#screen` overlay; verify against BLOCK 2's
      `.screen` z-index and set the root's stacking context accordingly — measured by R71's
      probes, which is the point).
- [ ] **Step 2: `aller()` + route table in `coquille.tsx`.**

```tsx
const profil = createRoute({
  getParentRoute: () => racine,
  path: "/profil/$titre",
  component: ProfilEcran,
});
// routeTree: racine.addChildren([attrape, profil])

export function aller(vers: {
  to: string;
  params?: Record<string, string>;
  search?: Record<string, unknown>;
  remplacer?: boolean;
}): void {
  // One history entry per logical navigation: the router batches its commits
  // into a microtask, and the legacy unwinding logic COUNTS entries — the
  // flush is what keeps native semantics. R76 forbids bare navigate() here.
  void routeur.navigate({
    to: vers.to,
    params: vers.params,
    search: vers.search,
    replace: vers.remplacer ?? false,
  });
  historique.flush();
}
window.__ecrans = {
  profil: (titre: string) =>
    aller({ to: "/profil/$titre", params: { titre: titre.normalize("NFC") } }),
};
```

- [ ] **Step 3: The pop dispatcher (ownership law).** In `coquille.tsx`, the
      `surRetour` forwarding gains the address filter: on BACK/FORWARD/GO, if
      `location.pathname` matches a screen route (`routeur.matchRoute` on `/profil/$titre`,
      extended per wave), do NOT invoke the legacy callback — the router renders by URL; else
      forward as today. (The legacy popstate logic keeps handling `/` pops unchanged.)
- [ ] **Step 4: Rewire the legacy call sites.** Every `openProfil(x)` call site becomes
      `window.__ecrans.profil(x)`; delete `function openProfil` from the fragment. The
      user-sheet action `cible: { go: "profil" }` — decide from the code which it is: if the
      profile the sheet opens is the SCREEN (openProfil), route it via `__ecrans.profil`;
      if it is the PAGE `?page=profil`, leave it to the fixed data-go handler. Read the
      handler, decide, note the decision in the commit body.
- [ ] **Step 5: Gate.** Rebuild + ritual + FULL suite. R71's journeys traverse the new
      screen (fiche→profil stacks legacy-over-React and React-over-legacy) — green with
      unchanged rule code is the wave's proof. Live smoke on the host.
- [ ] **Step 6: Commit.** `feat(shell-mobile): Profil — premier écran en route réelle, aller() seul navigateur`

### Task 10: R75 + R76 — the new rules

**Files:**

- Create: `frontend/maquette/harness/adresses_ecrans.py` (R75)
- Create: `frontend/maquette/harness/navigation.py` (R76)
- Modify: `frontend/maquette/regions.json` (register both, with mutations)

**Interfaces:**

- Consumes: `serveur.py` (Task 8) on port 8917; the Profil route (Task 9).

- [ ] **Step 1: R75 — screen addresses.** Holds: (a) deep entry: open
      `http://127.0.0.1:8917/profil/<titre-réel-encodé>` cold → the profil screen renders its
      promised content; (b) its images draw (`img.complete && naturalWidth > 0` — the
      `<base>` proof at depth); (c) one back lands on the default page `/` with the screen
      gone; (d) the path is written only while a screen is open: walking `acq → profil`
      writes `/profil/…`, closing it returns the address to what it was; (e) a wrong deep
      address (`/profil/N'Existe%20Pas`) renders the screen's honest empty case, address
      left exactly as typed (R68's spirit at depth).
- [ ] **Step 2: R75 mutations, executed and pasted.** Sever the harness server's fallback
      (serve 404 instead of wrapped.html) → (a) falls naming the fallback. Remove `<base>`
      from the COPY → (b) falls naming the image resolution.
- [ ] **Step 3: R76 — framed navigation.** Holds: (a) source-read on `design/src/`: zero
      `navigate(` outside `aller`'s implementation (same gesture as R74's no-raw-history
      assertion); (b) journey: from `/`, `__ecrans.profil(t)` then `aller({to:"/"})` — walking
      back twice traverses exactly those two entries in reverse (count by observed states,
      not by `history.length`); (c) two `aller()` in the same task produce two entries.
- [ ] **Step 4: R76 mutation.** Remove `historique.flush()` from `aller` in the COPY's
      bundle — impractical to patch minified: mutate at SOURCE in a scratch worktree? NO —
      simpler and honest: the mutation is MANUAL by design (R74 precedent, recorded as such
      in `regions.json`): comment the flush out in `coquille.tsx`, rebuild into the copy via
      the ritual, run R76 → (c) falls (one merged entry), restore, rebuild. Record « mutation
      manuelle par conception » in the rule's entry.
- [ ] **Step 5: Register R75/R76 in `regions.json`** (`$adversarialReview` list) with
      their mutations and lessons. Full suite (now 47 scripts) green. Commit.

### Task 11: The Ajout pilot — the second screen, state in the URL

**Files:**

- Create: `frontend/maquette/design/src/ecrans/ajout.tsx`
- Modify: `frontend/maquette/design/src/coquille.tsx` (route `/ajout` with
  `validateSearch` for `{ q?: string; mode?: "suivi" | "identifier" }`, `__ecrans.ajout`)
- Modify: `frontend/maquette/design/refonte.html` (remove `openAddScreen` body; rewire
  call sites — `grep -n "openAddScreen" refonte.html`, includes the FAB, `data-search`,
  `data-manual` resolution path, and the post-add re-render sites which simply disappear:
  the component re-renders from the store)
- Modify: `frontend/maquette/harness/adresses_ecrans.py` (R75 extended to `/ajout`)

**Interfaces:**

- Consumes: everything above.
- Produces: `window.__ecrans.ajout(q?: string, mode?: string): void`; route `/ajout`
  whose `q`/`mode` are router-owned (the first router-owned search params — the
  ownership law's first flip); typing REPLACES the entry (`aller({ …, remplacer: true })`)
  so keystrokes never stack history.

- [ ] **Step 1: Transplant `openAddScreen`'s template** into `AjoutEcran` (same chains:
      `.screen > .port`, `.addbar`, `.reslist`, `.addfoot`…). The search input drives
      `aller({ to: "/ajout", search: { q }, remplacer: true })`; the component reads
      `useSearch` — the router owns this state end to end. Results/`added` come via hooks
      (`useMonde`/`useEtat` selections over `SEARCH`/`state.added` — whichever the engine
      exposes through the handshake; extend `adopterMonde`'s payload if a field is missing,
      never reach into the engine).
- [ ] **Step 2: Cross-world interplay stays free.** The result cards keep their
      `data-panel="add:N"` / `data-fiche` attributes VERBATIM: the legacy document-level
      delegation opens the panel and the fiche exactly as before — that is the strangler seam
      working. The panel's add act mutates state → store bumps → `AjoutEcran` re-renders (the
      legacy `openAddScreen()` re-render calls in the delegated handlers are deleted).
- [ ] **Step 3: Rewire entries.** FAB → `__ecrans.ajout(state.addQ, "suivi")`;
      `data-search` sites → `__ecrans.ajout(q)`; the resolution screen's manual-search path
      keeps its behavior (mode `identifier`, resolveTarget in engine state).
- [ ] **Step 4: Extend R75** to `/ajout`: deep `/ajout?q=lucky` lands with the field
      filled and results for « lucky »; typing rewrites the address in place (no history
      growth — assert by walking back ONCE from a 5-keystroke session and landing where one
      stood before the screen).
- [ ] **Step 5: Gate.** Rebuild + ritual + full suite green (R59/R69/R71 untouched —
      `ecrans.py`'s add-screen journeys now traverse the React screen). Live smoke. Commit:
      `feat(shell-mobile): Ajout — l'écran en route réelle, la recherche dans l'URL`

### Task 12: CI carries the maquette typecheck

**Files:**

- Modify: `.github/workflows/ci.yml` (the `frontend` job, after the existing
  `npx tsc -b --noEmit` step)

- [ ] **Step 1: Add the steps.**

```yaml
- run: npm ci
  working-directory: frontend/maquette/design
- run: npm run typecheck
  working-directory: frontend/maquette/design
```

- [ ] **Step 2: Commit** (`ci(shell-mobile): la coquille typée est gardée en CI`); the PR's
      CI run is the executable proof — check the job log shows the step running.

### Task 13: Wave gate — docs, suite, PR

**Files:**

- Modify: `IMPLEMENTATION.md` (SP4a state + ritual unchanged), `frontend/maquette/README.md`
  (route table, `aller()`, boot handshake — a short paragraph each),
  `personalscraper/__init__.py` (patch bump)

- [ ] **Step 1: `resynchro.py`** (live counters may have drifted during the wave), review, commit if it changed anything.
- [ ] **Step 2: Full suite** (47 scripts) — zero FAILED, output pasted. `make check` green. `make check-frontend` green.
- [ ] **Step 3: Docs + bump commit.**
- [ ] **Step 4: Push (verify remote SHA), PR** (title: `feat(shell-mobile): SP4a — la machinerie de la conversion et les deux premiers écrans en routes réelles`), CI green, adversarial review per the lane's discipline, squash-merge on the standing instruction, post-merge live check + `pm2 restart torrentmate-design` if `serve.py` changed.

---

## Self-review notes (executed)

- Spec coverage: waves table → SP4a scope ✔ (spikes T1-T2, store T3/T5, inversion T4,
  hooks T6, fallback+favicon+portal T7-T8, pilots T9/T11, R75/R76 T10, CI T12, gate T13).
  The spec's « profil page vs screen » ambiguity is resolved in T9 Step 4 by reading the
  code, decision recorded in the commit body.
- The `<base href="/">` element and the harness fallback server are plan-level additions
  the spec implies (deep paths must draw and be measured) — recorded here, and to be
  reflected in the spec by amendment at T7/T8 execution if the operator wants the spec to
  carry them explicitly.
- Type/name consistency: `magasin.ts` exports consumed as written in T4/T6/T9;
  `aller`/`__ecrans` signatures identical in T9/T10/T11.
