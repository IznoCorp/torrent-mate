// The panel's door — the verbs a producer and the frame open the single panel with.
import type { PanelDescriptor } from "./contract";

// The single panel, as a producer asks for it. `isOpen()` answers from the
// STORE, never from the DOM: a caller asks mid-task ("is a layer up
// before I open a screen?") and the store is already right at that instant,
// whatever React has committed. `pop` —
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
  // Opening a panel BY KIND — the seam a producer that has moved into its
  // feature arrives through. The delegation asks « the panel about this »; the
  // registry decides which feature answers. A kind nobody registered raises;
  // a producer answering `null` opens nothing, which is the honest reply for a
  // subject the cache does not hold yet.
  produce: (kind: string, subject?: string) => void;
  // RE-PRODUCING THE PANEL THAT IS ALREADY OPEN, from a cache that has moved
  // under it. A producer is a function from the cache to a descriptor and NOT
  // a component: nothing subscribes while the panel is open, so a verb that
  // refetched what the panel reads left the operator looking at the answer
  // from before his own act. It re-runs the same kind and subject with the
  // history write suppressed — the entry it would push is the one being stood
  // on — and does nothing at all when no panel is open.
  redraw: () => void;
  // Which kinds have a producer, read by the rule that holds the seam from
  // outside. A reading rather than an assertion — see `registeredProducers`.
  producers: () => string[];
  // Whether the feature that owns a kind HOLDS a subject — asked by the
  // addressed-panel table before it opens a panel from a typed address. A
  // producer answers for anything; this is the other question, and it is the
  // feature's to answer rather than the engine's fixture's.
  holds: (kind: string, subject: string) => boolean;
};

// The published half of the same door, declared beside the type it publishes.
declare global {
  interface Window {
    __panel: Panel;
  }
}
