// The strangler shell. One owner for the URL and the history: this router.
// The legacy engine keeps its navigation LOGIC (what to push, when to
// unwind) and loses only its primitives — it speaks to `window.__pont`,
// implemented here on the router's history. `window.__go` keeps driving
// states without navigation, exactly as before.
import {
  createBrowserHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import React from "react";
import { flushSync } from "react-dom";
import ReactDOM from "react-dom/client";
import { Feuille } from "./composants/feuille";
import { refuserBloc, type Descripteur } from "./composants/panneau";
import { AjoutEcran } from "./ecrans/ajout";
import { ProfilEcran } from "./ecrans/profil";
import { creerMagasin, type Magasin } from "./magasin";

// R69's addressable state, validated — absent means "unchanged", as before.
type Recherche = {
  page?: string;
  tab?: string;
  lens?: string;
  mode?: string;
  cat?: string;
  rub?: string;
};

// The bridge's contract, stated once. The verbs are the legacy nav cluster's
// primitives, renamed; the state objects crossing them are the legacy ones.
type Pont = {
  noter: (etat: unknown, url: string) => void;
  remplacer: (etat: unknown, url?: string) => void;
  coucher: (couche: string) => void;
  retour: () => void;
  surRetour: (rappel: (etat: unknown) => void) => () => void;
};

// One entry per migrated screen: what a legacy call site invokes instead of
// its old `openX(...)` function. `titre` crosses the bridge as a plain
// string — normalisation and encoding are this file's job, not the caller's.
type Ecrans = {
  profil: (titre: string) => void;
  // `q`/`mode` cross the bridge as plain strings, the way a legacy call site
  // already holds them (`state.addQ`, a literal like `"identifier"`) — the
  // validated union lives in `/ajout`'s own `validateSearch`, not here.
  ajout: (q?: string, mode?: string) => void;
};

declare global {
  interface Window {
    __pont: Pont;
    __routeur: typeof routeur;
    // The engine's handshake: defined by refonte.html, called exactly once
    // below, once the store exists and the bridge is real. Optional because
    // a module that failed to evaluate is exactly the case this boot order
    // is built to leave visible — the startup screen, not a crash here.
    // `base` is the legacy engine's own address root (see its computation
    // below) — "/" in production, whatever else a static host answers the
    // document under otherwise (the rule harness's 8899 server names it
    // "/wrapped.html").
    __demarrerMoteur?: (deps: { magasin: Magasin; base: string }) => void;
    // The domain hooks and the probes read the engine's state through this.
    __magasin: Magasin;
    __ecrans: Ecrans;
    // The layer-unwind bookkeeping stays ENGINE-side (the named-entry check
    // and the one-in-flight latch live with the popstate handler that consumes
    // them); the fragment publishes it so the shell's own layer can announce
    // its close the same way every legacy layer does.
    __derouler?: (couche: string) => void;
    // The probe R56 calls to prove the panel REFUSES a block nobody declared.
    // Published here because the constructor it exercises is a component now.
    __panneauInconnu: () => void;
  }
}

// The history instance is created here rather than left to the router's
// default, so the single writer is a named object this file owns: the bridge
// below and the router share it, and no future default can silently split it
// in two.
//
// Creating it stamps the current entry with the library's own bookkeeping
// keys. Nothing is preserved across that stamp on purpose: the engine no
// longer writes the entry itself — its boot writes go straight onto this
// instance BELOW, once window.__demarrerMoteur is called, so the entry the
// shell mounts on is written once, by the single writer, in the right order.
const historique = createBrowserHistory();

// The root renders the matched route AND the bottom-sheet layer, which belongs
// to no route: it opens over whatever is on screen — a React route, a legacy
// `#screen`, a plain page — so it is mounted once, with the shell, and its
// visibility is a class, not a mount.
const racine = createRootRoute({
  component: () => (
    <>
      <Outlet />
      <Feuille fermer={fermerPanneau} />
    </>
  ),
});
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
  component: () => null, // the legacy DOM lives outside the React root until its surfaces migrate
});
// The quality-profile screen: a real route, rendering a final component
// INSIDE the React root — a surface reached directly rather than through the
// legacy fragment. `$titre` is percent-encoded and
// NFC-normalised by both ends of the bridge (`aller()` below on write,
// `ProfilEcran` on read) so a title carrying combining characters survives
// the round trip through the URL unchanged.
const profil = createRoute({
  getParentRoute: () => racine,
  path: "/profil/$titre",
  component: ProfilEcran,
});
// The second screen route, and the first whose OWN search params are
// router-owned rather than merely read: `q` (the typed query) and `mode`
// ("suivi" — follow a new title — or "identifier" — associate a stuck
// folder, reached from the resolution screen's manual search) live here for
// as long as the address reads `/ajout`, replacing `state.addQ`/
// `state.addMode` as the SOURCE of truth on this path (see `ajout.tsx`'s own
// doc comment for the transitional contract with the one legacy reader that
// remains). Absent means "suivi" / no query, the same "absent is unchanged"
// convention `attrape`'s `validateSearch` already uses above.
type RechercheAjout = { q?: string; mode?: "suivi" | "identifier" };
const ajout = createRoute({
  getParentRoute: () => racine,
  path: "/ajout",
  validateSearch: (brut: Record<string, unknown>): RechercheAjout => {
    const lu: RechercheAjout = {};
    if (typeof brut.q === "string" && brut.q) lu.q = brut.q;
    if (brut.mode === "identifier") lu.mode = "identifier";
    return lu;
  },
  component: AjoutEcran,
});
// A thrown component used to fail into a bare `null` — the exact failure
// shape this whole architecture exists to kill: a blank phone frame with
// nothing on screen saying why, and nothing in the console pointing at it
// either, since React only reports past an error boundary. This one is a
// VISIBLE failure instead, styled with the document's own tokens rather
// than an inline guess, so it reads as part of the interface it failed
// inside rather than as an unstyled crash page.
function EcranEnErreur({ error }: { error: unknown }) {
  console.error(error);
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        textAlign: "center",
        background: "var(--background)",
        color: "var(--danger)",
      }}
    >
      Cet écran a échoué à s'afficher. Détail dans la console.
    </div>
  );
}

const routeur = createRouter({
  routeTree: racine.addChildren([attrape, profil, ajout]),
  history: historique,
  // The document is also read under other paths than `/` — the rule harness
  // serves it as `wrapped.html`. The router's built-in not-found fallback
  // would print « Not Found » into the mount node; the fallback DOCUMENT
  // already serves any unknown path (see serve.py), so a second one here
  // would only duplicate it — silenced rather than left to a default. A
  // thrown error is a different failure and gets a different answer: see
  // `EcranEnErreur` above.
  defaultNotFoundComponent: () => null,
  defaultErrorComponent: EcranEnErreur,
});
// Registers `routeur` as THE router for every `useParams`/`useNavigate` call
// in the tree, so a screen component (in its own file, importing neither
// `routeur` nor `racine` — that would cycle back to this module) still gets
// fully typed params from a bare path literal like `/profil/$titre`.
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof routeur;
  }
}

// The bridge: the same verbs the legacy cluster used, one writer underneath.
// `couche` entries and the guard entry keep their exact state shapes — the
// legacy popstate logic still reads them.
//
// Two adaptations to the router's history, both to keep the NATIVE semantics
// the legacy engine was written against:
//   - writes are flushed immediately. The library batches pushes into a
//     microtask, which would merge two writes issued in the same task into a
//     single entry; native `pushState` creates one entry per call, and the
//     unwinding logic counts entries.
//   - a pop is reported as BACK / FORWARD / GO, never as a « POP » type: the
//     three together are what the `popstate` event used to signal.
//
// EVERY pop is forwarded to the engine callback, unfiltered. Ownership of an
// entry is not decided here by matching the address against a list of
// routes — it is already encoded in the entry's own SHAPE, and the engine
// callback reads that shape itself: a `layer` entry and a `tm: "nav"` entry
// keep their exact existing handling, and an entry written by the router
// carries neither key, so the callback's own checks fall through it
// harmlessly — the router has already re-rendered by the new URL before this
// runs, and the callback simply has nothing left to do. Filtering pops by
// pathname here was tried and withdrawn: a layer opened OVER a screen route
// (via `coucher`, still a `layer` entry) needs the SAME forwarding a layer
// opened anywhere else gets, or its own unwind guard never runs and closing
// it silently stops working.
window.__pont = {
  noter: (etat: unknown, url: string) => {
    historique.push(url, etat);
    historique.flush();
  },
  remplacer: (etat: unknown, url?: string) => {
    historique.replace(url ?? historique.location.href, etat);
    historique.flush();
  },
  coucher: (couche: string) => {
    historique.push(historique.location.href, { layer: couche });
    historique.flush();
  },
  retour: () => historique.back(),
  surRetour: (rappel: (etat: unknown) => void) =>
    historique.subscribe(({ action, location }) => {
      if (
        action.type === "BACK" ||
        action.type === "FORWARD" ||
        action.type === "GO"
      )
        rappel(location.state);
    }),
};
window.__routeur = routeur;

// The ONLY programmatic navigator in `src/`: R76 forbids a bare
// `routeur.navigate()` anywhere else, because the library batches its
// commits into a microtask — two writes issued in the same task would merge
// into a single history entry, and the legacy unwinding logic COUNTS
// entries. The immediate `flush()` is what keeps native `pushState`
// semantics (one call, one entry) across the boundary.
export function aller(vers: {
  to: string;
  params?: Record<string, string>;
  search?: Record<string, unknown>;
  remplacer?: boolean;
}): void {
  void routeur.navigate({
    to: vers.to,
    params: vers.params,
    search: vers.search,
    replace: vers.remplacer ?? false,
  });
  historique.flush();
}
// What a migrated legacy call site invokes instead of its old `openX(...)`.
// NFC-normalised here, once, on write — `ProfilEcran` normalises again on
// read so an entry arriving by direct URL (not through this bridge) is
// covered too.
window.__ecrans = {
  profil: (titre: string) =>
    aller({ to: "/profil/$titre", params: { titre: titre.normalize("NFC") } }),
  // Kept in sync in `magasin.ecrire` BEFORE navigating: `state.addMode` is
  // still read by the untouched cross-world "add:N" panel act (it decides
  // ASSOCIATE vs regular add — see refonte.html) and by `addVerb`, and
  // `state.addQ` still seeds the FAB's next open. Neither is written again
  // after this call — typing on `/ajout` updates the ROUTER's search params
  // only, through `aller()` directly, not through this bridge — so a value
  // read off `state.addQ`/`state.addMode` after the operator has typed
  // reflects the screen's ENTRY query, not its live one. That staleness is
  // the accepted cost of the ownership flip: the router is the only thing
  // that stays current for as long as the address reads `/ajout`.
  ajout: (q?: string, mode?: string) => {
    const modeValide = mode === "identifier" ? "identifier" : "suivi";
    // This file is SHELL code, not a component — it is the seam itself, so
    // it writes the store directly rather than through donnees.ts's
    // `ecrireEtat` write door (components must use that one; see its own
    // doc comment).
    window.__magasin.ecrire({ addQ: q ?? "", addMode: modeValide });
    aller({
      to: "/ajout",
      search: {
        q: q || undefined,
        mode: modeValide === "identifier" ? "identifier" : undefined,
      },
    });
  },
};

/* The bottom panel, as the shell's verbs — what every legacy producer calls
   instead of the dead `openSheet(html)`. The descriptor of FACTS crosses
   untouched; the markup is `PanneauContenu`'s business.

   The store write is flushed SYNCHRONOUSLY, and that is the whole subtlety of
   moving this layer. React commits a frame later by default, while the legacy
   layer's callers were written against a DOM that was already updated when
   `openSheet`/`closeSheet` returned: `data-del` closes the sheet and opens a
   dialog on the next line, and the dialog raises the SAME shared `#scrim` — a
   commit landing after that line would clear the scrim out from under the
   dialog. Flushing keeps the ordering every caller already relies on, and the
   panel's own content changes in the same task as the class that reveals it,
   so the sheet never slides in showing the previous panel for a frame. */
function ouvrirPanneau(descripteur: Descripteur): void {
  // Same order as the legacy `openSheet`: the layer first, the history entry
  // second. This file is SHELL code — the seam itself — so it writes the store
  // directly rather than through donnees.ts's `ecrireEtat` component door.
  flushSync(() =>
    magasin.ecrire({ panneauDescripteur: descripteur, panneauOuvert: true }),
  );
  try {
    window.__pont.coucher("sheet");
  } catch (erreur) {
    // A bridge that is not there yet is not a reason to refuse a panel — the
    // same swallow the legacy `openSheet` did around this exact call.
  }
}

function fermerPanneau(pop?: boolean): void {
  // Guarded per LAYER, exactly as `closeSheet` was: closing an already-closed
  // sheet would consume a history entry that belongs to someone else.
  if (!panneauEstOuvert()) return;
  flushSync(() => magasin.ecrire({ panneauOuvert: false }));
  // `pop` means the entry is already being popped by the gesture that got us
  // here; otherwise the layer unwinds its own, through the engine's latch.
  if (!pop) window.__derouler?.("sheet");
}

// The STORE answers, never the DOM: a legacy caller asks in the middle of its
// own task ("is a layer up before I open a screen?"), and the store is right
// at that instant whatever React has painted.
function panneauEstOuvert(): boolean {
  return magasin.lire().etat.panneauOuvert === true;
}

window.__panneau = {
  ouvrir: ouvrirPanneau,
  fermer: fermerPanneau,
  ouverte: panneauEstOuvert,
};

/* Lets the contract check prove the refusal rather than trust the comment on
   it: a block type nobody declared must raise, not draw nothing. Called as a
   plain function, not rendered — the dispatcher refuses before it reads
   anything else, which is what makes the refusal provable from outside. */
window.__panneauInconnu = () => refuserBloc({ type: "ceci-n-existe-pas" });

// The store is created here, and the engine starts only once it — and the
// bridge above — are real. No queue, no replay: the engine's own boot writes
// (the arrival state, the guard entry, the back listener) now run straight
// onto the single writer, in the engine's own order, before the first
// render. A module that never evaluates simply never calls this, and the
// startup screen — already first in the frame — stays up: a visible,
// truthful failure instead of an app with mute verbs.
const magasin = creerMagasin();
window.__magasin = magasin;
// The legacy engine's own address BASE, decided by the ROUTER's OWN
// matching rather than by a second, independently-maintained list of the
// two screen paths: `getMatchedRoutes` is the cleanest fit here — a pure,
// synchronous lookup keyed on a bare pathname, unlike `router.state.matches`
// (needs a load this router has not run yet, since RouterProvider has not
// mounted) or `router.navigate` (this is a read, not a navigation). A
// pathname that resolves to a registered route (`/`, `/profil/$titre`,
// `/ajout` — any of the three) is router territory, and the shared
// production root for all of them is "/"; a pathname the router does not
// recognise at all (the harness's own "/wrapped.html") is the legacy
// engine's ground exactly as it is.
const [, , routeTrouvee] = routeur.getMatchedRoutes(location.pathname);
const base = routeTrouvee ? "/" : location.pathname;
const demarrer = window.__demarrerMoteur;
if (typeof demarrer === "function") demarrer({ magasin, base });

// `#coquille` starts, in the markup, as a static sibling of `.stage` —
// index.html knows nothing about the phone frame the fragment draws. A
// migrated screen's `.screen{position:absolute;inset:0}` resolves against
// its nearest POSITIONED ancestor, which for the legacy `#screen` is
// `.device` (`position:relative`) — so at that sibling position a React
// screen has no positioned ancestor at all and sizes to the viewport
// instead of the phone frame, escaping it at any width past the 520px
// breakpoint where `.device` stops filling the viewport.
//
// Moved here, once, before the first render: into `.device`, immediately
// before the legacy `#screen`. Two things this placement is chosen to keep:
//   - containment — `.device` becomes the mount node's positioned ancestor
//     too, so a React `.screen.open` resolves its `inset: 0` the same way
//     the legacy one already does, at every viewport width.
//   - paint order — `insertBefore` keeps the mount node exactly where it
//     already was relative to `#screen` (earlier in document order, simply
//     re-parented), so a React screen still sits BEHIND the legacy one in
//     the stacking order the harness (ecrans.py, pont.py) already relies on:
//     when both carry `.open` at once (a legacy fiche opened over a migrated
//     results screen), `#screen` — later in the DOM — paints on top, and
//     `document.querySelector('.screen.open')` still resolves the React
//     screen first.
// A missing `#device`/`#screen` (a document without the fragment injected)
// leaves the node where the markup put it rather than throwing — the same
// fail-soft posture as the rest of this boot sequence.
const coquilleEl = document.getElementById("coquille")!;
const device = document.getElementById("device");
const ecranLegacy = document.getElementById("screen");
if (device && ecranLegacy) device.insertBefore(coquilleEl, ecranLegacy);

ReactDOM.createRoot(coquilleEl).render(
  <React.StrictMode>
    <RouterProvider router={routeur} />
  </React.StrictMode>,
);
