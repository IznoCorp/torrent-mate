// What the engine calls, declared instead of looked up.
//
// The engine used to reach the shell through `window.__bridge`, `window.__screens`
// and `window.__panel` — three globals, because a classic script inside the
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
// `__screens`, `__panel` and `__bridge` itself, so those stay published for it,
// and R74 describes them as what they now are — a driving surface, not a
// bridge between two worlds.
import type { PanelDescriptor } from "../ui/panel/contract";

// The nav cluster's primitives. Named as the fragment spells them, because the
// fragment is the caller.
export type Bridge = {
  record: (state: unknown, url: string) => void;
  replace: (state: unknown, url?: string) => void;
  pushLayer: (layer: string) => void;
  back: () => void;
  rewind: (n: number) => void;
  // The callback is handed the entry's state AND the direction the
  // traversal came from: the same entry means opposite things stepped onto
  // forwards and stepped back onto, and only the caller of `subscribe` can
  // tell them apart.
  onBack: (
    callback: (state: unknown, direction: "BACK" | "FORWARD" | "GO") => void,
  ) => () => void;
};

// One entry per migrated screen: what a legacy call site invokes instead of
// its old `openX(...)`.
export type Screens = {
  profile: (title: string) => void;
  mediaSheet: (title: string) => void;
  releases: (title: string) => void;
  resolution: (folder?: string, replace?: boolean) => void;
  add: (q?: string, mode?: string) => void;
};

// The single panel, as a producer asks for it. `isOpen()` answers from the
// STORE, never from the DOM: a legacy caller asks mid-task ("is a layer up
// before I open a screen?") and the store is already right at that instant,
// whatever React has committed. `pop` mirrors the legacy `closeSheet(pop)` —
// truthy means the history entry is ALREADY being popped, so the layer must
// not unwind one of its own.
export type Panel = {
  open: (descriptor: PanelDescriptor) => void;
  close: (pop?: boolean) => void;
  isOpen: () => boolean;
  // Opening onto the entry that already records the panel — a Forward back
  // onto a layer entry. The producer is run through this door, with the
  // history write suppressed, because the entry it would push is the one
  // being stood on.
  openOnCurrentEntry: (open: () => void) => void;
};

// The published half of the same seam. It is declared HERE, beside the type it
// publishes, and not in the module that holds the domain hooks: declaring it
// there made that module import the panel component for one type, while the
// panel component imported it back for its own — a cycle whose two halves were
// a duplicate of THIS declaration.
declare global {
  interface Window {
    __panel: Panel;
  }
}

// Read by the engine at CALL time, never at import time.
//
// The three names are the FRAGMENT's, and they stay as it spells them: they are
// the seam itself, and the same objects are published as `window.__bridge`,
// `window.__screens` and `window.__panel`, which is how the rule harness
// drives them. Renaming one half would be inventing a second vocabulary for
// one thing.
export let bridge: Bridge; // french-ok: the seam's own name, as the fragment spells it
export let screens: Screens; // french-ok: the seam's own name, as the fragment spells it
export let panel: Panel; // french-ok: the seam's own name, as the fragment spells it

/**
 * Fills the seams, once, from the shell's boot.
 *
 * Called before `window.__startEngine`, so every name is real by the time
 * the engine can reach one. Calling it twice would silently re-point the
 * engine's collaborators mid-run, so it refuses.
 *
 * @throws When called a second time.
 */
export function installSeams(seams: {
  bridge: Bridge;
  screens: Screens;
  panel: Panel;
}): void {
  if (bridge) throw new Error("installSeams: already installed");
  ({ bridge, screens, panel } = seams);
}
