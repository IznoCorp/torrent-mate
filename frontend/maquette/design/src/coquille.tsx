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
  }
}

// The history instance is created here rather than left to the router's
// default, so the single writer is a named object this file owns: the bridge
// below and the router share it, and no future default can silently split it
// in two.
//
// Creating it stamps the current entry with the library's own bookkeeping
// keys, and that stamp REPLACES whatever state the entry already carried.
// The engine writes its arrival state before this module runs (a module tag
// is deferred), so the state is read first and written back: a shell that
// erased the entry it mounted on would break the walk back to it, silently.
const etatALArrivee = window.history.state;
const historique = createBrowserHistory();
if (etatALArrivee) {
  historique.replace(historique.location.href, etatALArrivee);
  historique.flush();
}

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

ReactDOM.createRoot(document.getElementById("coquille")!).render(
  <React.StrictMode>
    <RouterProvider router={routeur} />
  </React.StrictMode>,
);
