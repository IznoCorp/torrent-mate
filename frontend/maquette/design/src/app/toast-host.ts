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
//
// WHERE THE MESSAGE IS PLACED IS DECIDED HERE, from whether a layer is open
// (`app/layer-presence.ts`): at the top while one is, at the bottom otherwise.
// `ui/variants/frame.ts`'s ranked list says why. It follows the layers only
// while the message is SHOWN — a message up before a sheet opens moves off it —
// and a leaving message keeps its place until its exit has run.
import { setMessagePresent } from "./message-presence";
import { readLayerOpen, subscribeToLayerOpen } from "./layer-presence";
import type { Message, Edge } from "../ui/toast";

const MESSAGE_MS = 5000;
const MESSAGE_WITH_UNDO_MS = 6000;

// THE EXIT'S WHOLE LENGTH: `messageHost`'s 200 ms fade, and the visibility step
// it delays behind the fade. Until both have run the host is still the leaving
// message, and moving its box then would move a message the reader watches go.
// After it, the host at rest is back in the bottom box — the box the oracle
// measures on every state, none of which draws a message.
const MESSAGE_EXIT_MS = 400;

type Layer = { message: Message | null; shown: boolean; edge: Edge };

// THE SNAPSHOT IS AN OBJECT THAT ONLY CHANGES WHEN THE LAYER DOES, and that is
// a requirement rather than an economy: `useSyncExternalStore` compares the
// value it is handed, so a reader building a fresh object on every call
// reports a change on every render and loops for ever.
let layer: Layer = { message: null, shown: false, edge: "bottom" };
let timer = 0;
let exitTimer = 0;
const listeners = new Set<() => void>();

function edgeNow(): Edge {
  return readLayerOpen() ? "top" : "bottom";
}

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
  window.clearTimeout(exitTimer);
  timer = window.setTimeout(
    hideMessage,
    descriptor.undo ? MESSAGE_WITH_UNDO_MS : MESSAGE_MS,
  );
  announce({ message: descriptor, shown: true, edge: edgeNow() });
}

/** Takes the message off screen, keeping its text and its place for the exit. */
export function hideMessage(): void {
  if (!layer.shown) return;
  window.clearTimeout(timer);
  announce({ ...layer, shown: false });
  exitTimer = window.setTimeout(returnToRest, MESSAGE_EXIT_MS);
}

/** Puts the hidden host back in the bottom box once its exit has run. */
function returnToRest(): void {
  if (layer.shown || layer.edge === "bottom") return;
  announce({ ...layer, edge: "bottom" });
}

/** Moves a shown message when a layer opens where none was, or the last closes. */
function followTheLayers(): void {
  if (!layer.shown) return;
  const edge = edgeNow();
  if (edge !== layer.edge) announce({ ...layer, edge });
}

declare global {
  interface Window {
    /** The message's verbs, as the engine's producers say them. */
    __toast?: {
      show: (descriptor: Message) => void;
      hide: () => void;
      /** What is on screen, for a rule and for the boot hint's own dismissal. */
      read: () => { message: Message | null; shown: boolean; edge: Edge };
    };
  }
}

export function installToastHost(): void {
  window.__toast = {
    show: showMessage,
    hide: hideMessage,
    read: readMessage,
  };
  subscribeToLayerOpen(followTheLayers);
}
