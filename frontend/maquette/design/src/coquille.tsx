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
  RouterProvider,
} from "@tanstack/react-router";
import React from "react";
import ReactDOM from "react-dom/client";
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

declare global {
  interface Window {
    __pont: Pont;
    __routeur: typeof routeur;
    // The engine's handshake: defined by refonte.html, called exactly once
    // below, once the store exists and the bridge is real. Optional because
    // a module that failed to evaluate is exactly the case this boot order
    // is built to leave visible — the startup screen, not a crash here.
    __demarrerMoteur?: (deps: { magasin: Magasin }) => void;
    // The domain hooks and the probes read the engine's state through this.
    __magasin: Magasin;
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
const routeur = createRouter({
  routeTree: racine.addChildren([attrape]),
  history: historique,
  // The document is also read under other paths than `/` — the rule harness
  // serves it as `wrapped.html`. The router's built-in fallback would print
  // « Not Found » into the mount node; the shell renders nothing visual in
  // SP3, so both fallbacks are silenced rather than left to a default.
  defaultNotFoundComponent: () => null,
  defaultErrorComponent: () => null,
});

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

// The store is created here, and the engine starts only once it — and the
// bridge above — are real. No queue, no replay: the engine's own boot writes
// (the arrival state, the guard entry, the back listener) now run straight
// onto the single writer, in the engine's own order, before the first
// render. A module that never evaluates simply never calls this, and the
// startup screen — already first in the frame — stays up: a visible,
// truthful failure instead of an app with mute verbs.
const magasin = creerMagasin();
window.__magasin = magasin;
const demarrer = window.__demarrerMoteur;
if (typeof demarrer === "function") demarrer({ magasin });

ReactDOM.createRoot(document.getElementById("coquille")!).render(
  <React.StrictMode>
    <RouterProvider router={routeur} />
  </React.StrictMode>,
);
