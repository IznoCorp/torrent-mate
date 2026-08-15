# Maquette SP3 — Router by Strangler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** React + TanStack Router become the maquette's outer shell and the single owner of URL/history; the legacy engine runs unchanged in a catch-all; the harness measures the BUILD from the first commit.

**Architecture:** Phase A switches the measuring ritual to a copy of the build while build ≡ source still holds (risk-free under R72). Phase B adds the module entry (`design/src/coquille.tsx`), a `window.__pont` bridge that re-plugs the legacy nav cluster's 11 history-primitive sites + 1 popstate listener onto the router's history, rescopes R72, and adds R74. R59/R69/R71 are the bridge's acceptance gates — unchanged rule code, that is the point.

**Tech Stack:** React ^19.2.7 (aligned with `frontend/`), `@tanstack/react-router` latest v1, Vite 8 (in place). Harness: `command python3` + Playwright `channel="chrome"`.

**Spec:** `docs/superpowers/specs/2026-08-14-maquette-sp3-routeur-etrangleur-design.md`

## Global Constraints

- Branch `feat/maquette-sp3` (from `main` `a7e7396b`); spec committed (`ad2036e7`).
- Conventional Commits, scope `(shell-mobile)`, French messages, no AI attribution; comments English/timeless.
- Never `rg` unfiltered; `curl` with `--connect-timeout 10 --max-time 30`; scratch ports 8913/8917/8918 only; one measuring process; exit codes are the verdict.
- The pm2 host serves this tree (auto-rebuild is live since the bascule). `serve.py` changes require `pm2 restart torrentmate-design`.
- **The NEW measuring ritual** (Phase A onward — replaces the wrapped.html recipe everywhere):
  ```bash
  cd /Users/izno/dev/PersonalScraper/frontend/maquette/design
  /Users/izno/.nvm/versions/node/v22.13.1/bin/npm run build
  cp dist/index.html /tmp/tm-refonte/wrapped.html
  rm -rf /tmp/tm-refonte/vite && { [ -d dist/vite ] && cp -R dist/vite /tmp/tm-refonte/vite || true; }
  ```
  (assets symlink already in place; `dist/vite` exists only from Phase B on.)
- Legacy behavior invariants the bridge must keep byte-for-behavior: R59 (guard entry, exit-armed double-back), R69 (URL carries state, only diffs written), R71 (screen stack redraw). No bridge commit lands while any of the three is red.
- Version bump 0.97.4 in `personalscraper/__init__.py` at delivery.

---

### Task 1 (Phase A): the harness measures the build

**Files:**

- Modify: `frontend/maquette/README.md` (the run ritual), `IMPLEMENTATION.md` (same recipe, lines ~108-118)

**Interfaces:**

- Produces: the ritual above as the documented recipe; all 44 rules green measuring the build copy. Every later task measures through it.

- [ ] **Step 1:** Update both recipes to the Global Constraints ritual (replace the python-wrapper heredoc blocks; keep the surrounding prose about stale copies, adjusting "re-synced from refonte.html" to "rebuilt and copied from the build"). English.
- [ ] **Step 2:** Execute the ritual, then run the FULL 44-script suite (sequential, detached, log to `/tmp/tm-refonte/suite-sp3a.log`, `FAILED:` lines + `SUITE TERMINEE`). Expected: zero FAILED. A failure here means an envelope-sensitive probe — diagnose by mechanism; the only expected delta between old wrapper and build copy is the head (title/lang/PWA) which no subtree probe reads.
- [ ] **Step 3:** Commit:

```bash
git add frontend/maquette/README.md IMPLEMENTATION.md
git commit -m "docs(shell-mobile): le harnais mesure le build — le rituel copie dist, la source reste la source d'édition"
```

---

### Task 2 (Phase B): the shell — React + TanStack Router mounted, owning nothing yet

**Files:**

- Modify: `frontend/maquette/design/package.json` (+ react, react-dom, @tanstack/react-router; lockfile)
- Create: `frontend/maquette/design/src/coquille.tsx`
- Modify: `frontend/maquette/design/index.html` (module tag + shell mount node, INSIDE the envelope, before the maquette placeholder)
- Modify: `frontend/maquette/serve.py` (session-gated `/vite/` route)

**Interfaces:**

- Produces: `window.__pont` (the bridge object, verbs below — Task 3 re-plugs legacy onto it) and `window.__routeur` (the router instance, for rules). The module entry emits under `dist/vite/`.

- [ ] **Step 1:** `npm install react@^19.2.7 react-dom@^19.2.7 @tanstack/react-router` in `design/` (lockfile updates).
- [ ] **Step 2:** `index.html`: inside `<body>`, BEFORE `<!-- maquette -->`, add:

```html
<!-- The strangler shell: the router owns the URL and the history; the
         legacy engine below keeps every surface until SP4 empties it. The
         mount node is size-zero — in SP3 the shell renders nothing visual. -->
<div id="coquille"></div>
<script type="module" src="/src/coquille.tsx"></script>
```

- [ ] **Step 3:** `src/coquille.tsx` — the shell. Requirements (transcribe this structure; exact TanStack API calls verified against the installed version's types):

```tsx
// The strangler shell. One owner for the URL and the history: this router.
// The legacy engine keeps its navigation LOGIC (what to push, when to
// unwind) and loses only its primitives — it speaks to `window.__pont`,
// implemented here on the router's history. `window.__go` keeps driving
// states without navigation, exactly as before.
import {
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import React from "react";
import ReactDOM from "react-dom/client";

// R69's addressable state, validated — absent means "unchanged", as before.
type Recherche = {
  page?: string;
  tab?: string;
  lens?: string;
  mode?: string;
  cat?: string;
  rub?: string;
};

const racine = createRootRoute();
const attrape = createRoute({
  getParentRoute: () => racine,
  path: "/",
  validateSearch: (brut: Record<string, unknown>): Recherche => {
    const lu: Recherche = {};
    for (const nom of ["page", "tab", "lens", "mode", "cat", "rub"] as const)
      if (typeof brut[nom] === "string" && brut[nom])
        lu[nom] = brut[nom] as string;
    return lu;
  },
  component: () => null, // the legacy DOM lives outside the React root until SP4
});
const routeur = createRouter({ routeTree: racine.addChildren([attrape]) });

// The bridge: the same verbs the legacy cluster used, one writer underneath.
// `couche` entries and the guard entry keep their exact state shapes — the
// legacy popstate logic still reads them.
window.__pont = {
  noter: (etat: unknown, url: string) =>
    routeur.history.push(url, etat as never),
  remplacer: (etat: unknown, url?: string) =>
    routeur.history.replace(
      url ?? routeur.history.location.href,
      etat as never,
    ),
  coucher: (couche: string) =>
    routeur.history.push(routeur.history.location.href, {
      layer: couche,
    } as never),
  retour: () => routeur.history.back(),
  surRetour: (rappel: (etat: unknown) => void) =>
    routeur.history.subscribe(({ action }) => {
      if (action.type === "POP") rappel(routeur.history.location.state);
    }),
};
window.__routeur = routeur;

ReactDOM.createRoot(document.getElementById("coquille")!).render(
  <React.StrictMode>
    <RouterProvider router={routeur} />
  </React.StrictMode>,
);
```

The implementer MUST check the installed `@tanstack/react-router` history API (`routeur.history` shape, subscribe signature, state passing) against its `.d.ts` and adapt names — the CONTRACT (verbs, semantics) is binding, the call syntax follows the library. If state-carrying pushes are not supported verbatim, wrap `@tanstack/history`'s `createBrowserHistory` explicitly and hand it to `createRouter({ history })`.

- [ ] **Step 4:** `serve.py`: add a `/vite/` route mirroring the `/assets/` one (session-gated, containment under `RACINE_DESIGN / "dist" / "vite"`, suffix allowlist `.js`/`.css`/`.map` → correct MIME, `private, max-age=31536000, immutable` — hash-named). Same structure, English comment stating why (the module entry the envelope names).
- [ ] **Step 5:** Build + prove: `npm run build` → `dist/index.html` contains ONE `<script type="module" src="/vite/...js">` (Vite rewrote the entry) AND the verbatim fragment; `dist/vite/` non-empty. Scratch-boot serve.py (8913, env hash) → authenticated `/vite/<bundle>.js` → 200, unauthenticated → 401. `pm2 restart torrentmate-design`, gate 401.
- [ ] **Step 6:** Ritual + targeted rules: `coquille.py` (R72 will FAIL its byte-exact hold — expected, Task 4 rescopes it; run it to CONFIRM it fails for exactly that reason and no other) and `bascule.py` (must stay green). Then commit:

```bash
git add frontend/maquette/design/package.json frontend/maquette/design/package-lock.json \
        frontend/maquette/design/index.html frontend/maquette/design/src/coquille.tsx frontend/maquette/serve.py
git commit -m "feat(shell-mobile): la coquille React + TanStack Router — montée, pont exposé, rien possédé encore"
```

(Note: R72 red between Tasks 2 and 4 is a DECLARED transition state — record it in the ledger; Task 4 closes it. Do not run the full suite in between.)

---

### Task 3 (Phase B): the bridge — the router becomes the single writer

**Files:**

- Modify: `frontend/maquette/design/refonte.html` (ONLY the nav cluster's primitive calls; zero rendering logic)

**The complete inventory to re-plug (verified at `a7e7396b`; line numbers drift with the formatter — anchor by content):**

| Site                          | Today                                                           | Becomes                                                                                                                               |
| ----------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| sheet layer push (~16252)     | `history.pushState({ layer: "sheet" }, "")`                     | `__pont.coucher("sheet")`                                                                                                             |
| `deroulerCouche` (~16286-291) | `history.back()` + `deroulementEnCours` consumption             | `__pont.retour()` (consumption logic unchanged)                                                                                       |
| screen stack push (~16349)    | `history.pushState({ layer: "screen" }, "")`                    | `__pont.coucher("screen")`                                                                                                            |
| screen open push (~16402)     | same                                                            | `__pont.coucher("screen")`                                                                                                            |
| `noterLeChemin` (~16540-543)  | `history.pushState(etatDeNavigation(), "", urlDeLEtat())`       | `__pont.noter(etatDeNavigation(), urlDeLEtat())`                                                                                      |
| popstate listener (~16547)    | `window.addEventListener("popstate", handler)`                  | `__pont.surRetour(handler)` — handler body unchanged, reading the popped entry's state from its argument instead of `evenement.state` |
| guard exit (~16583)           | `history.back()`                                                | `__pont.retour()`                                                                                                                     |
| drawer push (~17615)          | `history.pushState({ layer: "drawer" }, "")`                    | `__pont.coucher("drawer")`                                                                                                            |
| drawer arrival (~18072)       | `history.replaceState(etatDeNavigation(), "", urlDeLEtat())`    | `__pont.remplacer(etatDeNavigation(), urlDeLEtat())`                                                                                  |
| boot arrival replace (~40932) | `history.replaceState(etatDeNavigation(), "", adresseDArrivee)` | `__pont.remplacer(etatDeNavigation(), adresseDArrivee)`                                                                               |
| boot guard (~40943)           | `history.replaceState({ tm: "garde" }, "")`                     | `__pont.remplacer({ tm: "garde" })`                                                                                                   |
| boot arrival push (~40951)    | `history.pushState(etatDeNavigation(), "", adresseDArrivee)`    | `__pont.noter(etatDeNavigation(), adresseDArrivee)`                                                                                   |

Plus: a boot-order guard — the legacy script runs before the module loads (`type="module"` defers). The legacy boot sites must WAIT for the bridge: wrap the boot-time history calls in a `window.__pontPret` promise/callback the shell resolves on mount, with an English comment naming the ordering. If the legacy engine cannot defer its boot without behavior change, the alternative (implementer's judgment, reviewed): a tiny inline pre-bridge in the ENVELOPE that queues verb calls until the real bridge replaces it — queue-and-replay, no behavior change.

**Gates (each MUST be run after the re-plug, exit codes pasted):** `retour.py` (R59), `adresse.py` + `adresse_url.py` (R69), `ecrans.py` (R71), `demarrage.py` (R53 — boots serve.py, exercises boot order), `deconnexion.py`. All green with UNCHANGED rule code. Then the ritual + the full 44-suite in background. Zero FAILED.

- [ ] Implement, verify, commit:

```bash
git add frontend/maquette/design/refonte.html
git commit -m "feat(shell-mobile): le pont — le routeur seul écrit l'historique, la logique legacy ne change pas"
```

---

### Task 4 (Phase B): R72 rescoped, R74 born

**Files:**

- Modify: `frontend/maquette/harness/coquille.py`
- Create: `frontend/maquette/harness/pont.py` (R74)
- Modify: `frontend/maquette/regions.json`, `frontend/maquette/README.md`

- [ ] **Step 1 — R72 rescope** (`coquille.py`): byte-exact hold becomes `fragment in emis` PLUS `emis.count(fragment) == 1` (verbatim substring, once); the source-vs-build DOM/geometry comparison and its scratch source server RETIRE (delete the comparison loop; keep the build gate, the fragment hold, and add: exactly one `<script type="module" src="/vite/`… in `emis`, and the named bundle exists under `dist/vite/`). Docstring rewritten: the rule's remaining job. Rule count shrinks — the printed journal reflects reality.
- [ ] **Step 2 — retirement recorded**: `regions.json` R72 entry rewritten — what retired (the source-vs-build rendering comparison; its mechanism disappeared when the build began to contain the router by design), what remains (fragment verbatim ×1, module entry, bundle exists), and where the rendered-truth duty now lives (the full suite measures the build).
- [ ] **Step 3 — R74** (`pont.py`, Playwright on the measured build copy): four holds — (a) source assertion: zero direct `history.pushState`/`history.back(` calls remain in refonte.html's nav cluster (read the SOURCE, count occurrences; the only allowed writer is coquille.tsx); (b) the R71 journey (results → fiche → back redraws) re-run through the bridge on the BUILD; (c) direct URL entry `wrapped.html?page=lib&mode=list` lands on the promised state; (d) `window.__go` drives a state without changing `history.length`. Mutation: sever ONE bridge verb in the measured COPY (sed `__pont.retour()` → `void 0` in `/tmp/tm-refonte/wrapped.html`) → (b) falls naming the mechanism; restore via ritual.
- [ ] **Step 4:** regions.json R74 entry + README rows (pont.py; coquille.py row updated to its rescoped claim). Run both rules green + mutation evidence. Commit:

```bash
git add frontend/maquette/harness/coquille.py frontend/maquette/harness/pont.py \
        frontend/maquette/regions.json frontend/maquette/README.md
git commit -m "test(shell-mobile): R72 dit son nouveau périmètre, R74 tient le pont — mutation à l'appui"
```

---

### Task 5: suite, docs, bump, delivery

- [ ] Full suite (45 scripts) via the ritual, detached, zero FAILED.
- [ ] README (shell paragraph: the router owns the URL; the bridge; SP4 empties the catch-all) + IMPLEMENTATION.md SP3 entry + `0.97.4`.
- [ ] `make check` exit 0. Push (verify SHA). PR `feat(shell-mobile): SP3 — React et TanStack Router par étrangleur, le pont tenu par les règles`; body: the arbitrations (strangler confirmed after the confidence question; build measured first), Phase A/B, the bridge inventory, R72's recorded retirement, R74, gates. CI, squash merge (standing instruction), `pm2 restart torrentmate-design` (serve.py changed), post-merge: ritual + `pont.py` + live gate check.
