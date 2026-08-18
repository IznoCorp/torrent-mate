// What the engine calls, declared instead of looked up.
//
// The engine used to reach the shell through `window.__pont`, `window.__ecrans`
// and `window.__panneau` — three globals, because a classic script inside the
// fragment had no other way to speak to a module. It is a module itself now, so
// it says what it depends on: these three names, imported.
//
// THEY ARE `let`, AND THAT IS THE WHOLE MECHANISM. The implementations need the
// store, and the store is created in the shell's BODY — which runs after its
// imports, and the engine is one of them. So nothing can be assigned at this
// module's evaluation. An ES export is a LIVE BINDING: the engine imports the
// name, the shell fills it at boot, and the engine reads the filled value at
// call time, which is the only time it calls. A value copied at import would
// have been `undefined` forever.
//
// WHAT THIS BUYS, stated plainly because it is narrower than it sounds. The
// engine is JavaScript that `tsc` does not check, so this is not type safety
// at the call sites. What it is: a declared dependency — the import list now
// says what the engine needs — and a name the BUNDLER resolves, so a typo is a
// failed build instead of `undefined is not a function` on a click nobody
// tested. The `window` surface does not shrink: the harness drives through
// `__ecrans`, `__panneau` and `__pont` itself, so those stay published for it,
// and R74 describes them as what they now are — a driving surface, not a
// bridge between two worlds.
import type { PanelDescriptor } from "./components/panel";

// The nav cluster's primitives. Named as the fragment spells them, because the
// fragment is the caller.
export type Bridge = {
  noter: (state: unknown, url: string) => void;
  remplacer: (state: unknown, url?: string) => void;
  coucher: (layer: string) => void;
  retour: () => void;
  reculer: (n: number) => void;
  surRetour: (callback: (state: unknown) => void) => () => void;
};

// One entry per migrated screen: what a legacy call site invokes instead of
// its old `openX(...)`.
export type Screens = {
  profil: (titre: string) => void;
  fiche: (titre: string) => void;
  releases: (titre: string) => void;
  resolution: (dossier?: string, replace?: boolean) => void;
  ajout: (q?: string, mode?: string) => void;
};

// The single panel, as a producer asks for it.
export type Panel = {
  ouvrir: (descriptor: PanelDescriptor) => void;
  fermer: (pop?: boolean) => void;
  ouverte: () => boolean;
};

// Read by the engine at CALL time, never at import time.
//
// The three names are the FRAGMENT's, and they stay as it spells them: they are
// the seam itself, and the same objects are published as `window.__pont`,
// `window.__ecrans` and `window.__panneau`, which is how the rule harness
// drives them. Renaming one half would be inventing a second vocabulary for
// one thing.
export let pont: Bridge; // french-ok: the seam's own name, as the fragment spells it
export let ecrans: Screens; // french-ok: the seam's own name, as the fragment spells it
export let panneau: Panel; // french-ok: the seam's own name, as the fragment spells it

/**
 * Fills the seams, once, from the shell's boot.
 *
 * Called before `window.__demarrerMoteur`, so every name is real by the time
 * the engine can reach one. Calling it twice would silently re-point the
 * engine's collaborators mid-run, so it refuses.
 *
 * @throws When called a second time.
 */
export function installSeams(seams: {
  pont: Bridge;
  ecrans: Screens;
  panneau: Panel;
}): void {
  if (pont) throw new Error("installSeams: already installed");
  ({ pont, ecrans, panneau } = seams);
}
