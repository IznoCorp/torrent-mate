// THE LAYERS, AS REGISTRATIONS — a name, an `isOpen`, a `close(pop)`.
//
// THE LADDER'S HANDLER IS NOT HERE, and that is deliberate. `onEngineBack`
// walks the layers, `unwindLayer` announces a layer's own pop, `hideLayers`
// resets them for `__go` and `__closeLayers` says what a scrim tap closes —
// all four stay in the dying engine until L13, which is where the rest of the
// navigation logic goes. Reaching in to move them early would make this lot a
// subtraction wave as well as a conversion wave.
//
// WHAT THIS FILE DOES is let a converted layer be WALKED without the walker
// knowing its markup. The engine tested `#drawer.classList.contains("open")`;
// it asks the registration now, exactly as it already asks `window.__panel`
// whether the sheet is open. `MODEL.md` § 2 Part 4: « a layer registers itself
// — a name, an `isOpen`, a `close(pop)` — and the ladder walks registrations. »
//
// THE STATE IS THE REGISTRATION'S, NEVER THE DOM'S. A caller asks in the middle
// of its own task (« is a layer up before I open a screen? ») and the answer
// must be right at that instant, whatever React has painted — the same reason
// `panel.isOpen()` reads the store.

export type LayerRegistration = {
  /** Whether it is up right now. */
  isOpen: () => boolean;
  /**
   * Closes it.
   *
   * Args:
   *     pop: True when the entry is already being popped by the gesture that
   *         got here, so the layer must not unwind one of its own.
   */
  close: (pop?: boolean) => void;
};

const layers = new Map<string, LayerRegistration>();

/**
 * Registers a layer under a name the ladder walks.
 *
 * Args:
 *     name: The rung's name — `"drawer"`, `"dialog"`.
 *     registration: What the walker may ask and say.
 *
 * Returns:
 *     The way to take it off the ladder again.
 */
export function registerLayer(
  name: string,
  registration: LayerRegistration,
): () => void {
  layers.set(name, registration);
  return () => {
    if (layers.get(name) === registration) layers.delete(name);
  };
}

declare global {
  interface Window {
    /** The registrations, as the engine's ladder walks them. Dies with L13. */
    __layers?: {
      isOpen: (name: string) => boolean;
      close: (name: string, pop?: boolean) => void;
      names: () => string[];
    };
  }
}

export function installLayerRegistry(): void {
  window.__layers = {
    isOpen: (name) => layers.get(name)?.isOpen() === true,
    close: (name, pop) => layers.get(name)?.close(pop),
    // Published so a rule can ask what is ON the ladder rather than assume it:
    // a rung that stopped registering is invisible to every hold shaped like
    // « Back closed the thing that was open ».
    names: () => [...layers.keys()],
  };
}
