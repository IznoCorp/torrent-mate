// THE MESSAGE'S VERBS, and the seam the dying engine says them through.
//
// `app/panel-host.ts` is the precedent and the posture is the same: a
// DESCRIPTOR of facts crosses — what happened, and what undoes it — and the
// markup is the component's. The engine had thirty-four callers of `toast(…)`
// and `toastUndo(…)`; they keep saying exactly that, through one-line
// forwarders, because they are PRODUCERS and a producer moves to its feature
// with L19. The forwarders die with them.
//
// THE TWO DURATIONS ARE NOT ONE. Five seconds for a message, six for one that
// offers an undo, and the difference is the point: a reader who has to decide
// whether to undo needs longer than a reader who only has to notice. Folding
// them into one constant would be a behaviour change smuggled into a
// conversion.
//
// THE PRESENCE IS PUBLISHED, NEVER THE STATE. `app/message-presence.ts` is what
// the action button watches — it is anchored to the same corner and the message
// paints over it — and it is deliberately not the store: a store write between
// a finger's press and the click that follows destroys the click (B-247).
import { setMessagePresent } from "./message-presence";
import type { Message } from "../ui/toast";

const MESSAGE_MS = 5000;
const MESSAGE_WITH_UNDO_MS = 6000;

type Layer = { message: Message | null; shown: boolean };

// THE SNAPSHOT IS AN OBJECT THAT ONLY CHANGES WHEN THE LAYER DOES, and that is
// a requirement rather than an economy: `useSyncExternalStore` compares the
// value it is handed, so a reader building a fresh object on every call
// reports a change on every render and loops for ever.
let layer: Layer = { message: null, shown: false };
let timer = 0;
const listeners = new Set<() => void>();

function announce(next: Layer): void {
  layer = next;
  setMessagePresent(next.shown);
  for (const listener of listeners) listener();
}

/** What the message layer draws right now. */
export function readMessage(): Layer {
  return layer;
}

export function subscribeToMessage(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/**
 * Shows a message, replacing whatever was up.
 *
 * Args:
 *     descriptor: What happened, and optionally what undoes it.
 */
export function showMessage(descriptor: Message): void {
  window.clearTimeout(timer);
  timer = window.setTimeout(
    hideMessage,
    descriptor.undo ? MESSAGE_WITH_UNDO_MS : MESSAGE_MS,
  );
  announce({ message: descriptor, shown: true });
}

/** Takes the message off screen, keeping its text for the exit transition. */
export function hideMessage(): void {
  if (!layer.shown) return;
  window.clearTimeout(timer);
  announce({ message: layer.message, shown: false });
}

declare global {
  interface Window {
    /** The message's verbs, as the engine's producers say them. */
    __toast?: {
      show: (descriptor: Message) => void;
      hide: () => void;
      /** What is on screen, for a rule and for the boot hint's own dismissal. */
      read: () => { message: Message | null; shown: boolean };
    };
  }
}

export function installToastHost(): void {
  window.__toast = {
    show: showMessage,
    hide: hideMessage,
    read: readMessage,
  };
}
