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
//
// A MESSAGE THE READER HAS SEEN NEVER JUMPS. Moved at once, a message up on a
// screen that closed crossed the frame from its top to its bottom in one frame
// at full opacity, while it was being read. So a message already drawn that must
// change edge LEAVES — its own fade — and comes back at the other edge. One not
// yet drawn, said in the same task as the layer change, simply takes its place:
// there is nothing to watch move, and making it wait would only delay it.
//
// A CROSSING TAKES NOTHING FROM THE MESSAGE'S LIFE. Its clock stops when it
// starts to leave and runs again once it is whole at the other edge, so the
// reader gets back every moment it was away. One owed less than its own exit
// when it starts to leave does not come back: returning for less than that is
// a flash, at one edge, of a sentence the reader has just watched go at the
// other.
import { setMessagePresent } from "./message-presence";
import { readLayerOpen, subscribeToLayerOpen } from "./layer-presence";
import type { Message, Edge } from "../ui/toast";

const MESSAGE_MS = 5000;
const MESSAGE_WITH_UNDO_MS = 6000;

// THE ENTRANCE: `messageHost`'s 200 ms fade in. A message shown again at the
// other edge is not whole until it has run, so the life it is given back
// carries it.
const MESSAGE_ENTRY_MS = 200;

// THE EXIT'S WHOLE LENGTH: `messageHost`'s 200 ms fade, and the visibility step
// it delays behind the fade. Until both have run the host is still the leaving
// message, and moving its box then would move a message the reader watches go.
// After it, the host at rest is back in the bottom box — the box the oracle
// measures on every state, none of which draws a message. A message changing
// edge is away for the same length: moving its box before both have run would
// move a message the reader still sees.
const MESSAGE_EXIT_MS = 400;

type Layer = { message: Message | null; shown: boolean; edge: Edge };

// THE SNAPSHOT IS AN OBJECT THAT ONLY CHANGES WHEN THE LAYER DOES, and that is
// a requirement rather than an economy: `useSyncExternalStore` compares the
// value it is handed, so a reader building a fresh object on every call
// reports a change on every render and loops for ever.
let layer: Layer = { message: null, shown: false, edge: "bottom" };
let timer = 0;
// WHEN THE LIFE RUNS OUT, on the page's monotonic clock — and, while the
// message is away between two edges, what it is still owed. The clock does not
// run while it is away.
let deadline = 0;
let owed = 0;
let exitTimer = 0;
let moveTimer = 0;
// WHETHER THE MESSAGE IS AWAY BETWEEN TWO EDGES. It is still UP for the frame —
// its presence stays published, so the action button does not drop and rise —
// but it is not shown, so nothing a finger or a reader meets is at either edge.
let moving = false;
// WHETHER THE MESSAGE HAS BEEN DRAWN WHERE IT IS. Set on the animation frame
// after it was placed; the token keeps a frame scheduled for an earlier place
// from speaking for a later one.
let drawn = false;
let placeGeneration = 0;
const listeners = new Set<() => void>();

function edgeNow(): Edge {
  return readLayerOpen() ? "top" : "bottom";
}

function announce(next: Layer): void {
  layer = next;
  setMessagePresent(next.shown || moving);
  for (const listener of listeners) listener();
}

/** Announces a shown message at its place, and learns when it has been drawn there. */
function place(next: Layer): void {
  const token = ++placeGeneration;
  drawn = false;
  announce(next);
  window.requestAnimationFrame(() => {
    if (token === placeGeneration) drawn = true;
  });
}

/** Starts the message's life clock: it is taken off screen once `duration` has run. */
function startTheClock(duration: number): void {
  window.clearTimeout(timer);
  deadline = window.performance.now() + duration;
  timer = window.setTimeout(hideMessage, duration);
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
  window.clearTimeout(exitTimer);
  window.clearTimeout(moveTimer);
  moving = false;
  startTheClock(descriptor.undo ? MESSAGE_WITH_UNDO_MS : MESSAGE_MS);
  place({ message: descriptor, shown: true, edge: edgeNow() });
}

/** Takes the message off screen, keeping its text and its place for the exit. */
export function hideMessage(): void {
  // TAKEN OFF WHILE IT WAS AWAY between two edges — by its close, its undo or
  // a caller, since its own clock does not run meanwhile: it does not come back.
  if (moving) {
    window.clearTimeout(moveTimer);
    moving = false;
    announce({ ...layer, shown: false });
    exitTimer = window.setTimeout(returnToRest, MESSAGE_EXIT_MS);
    return;
  }
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
  if (edge === layer.edge) return;
  if (!drawn) {
    place({ ...layer, edge });
    return;
  }
  // WHAT IT IS OWED is read as it starts to leave, and its clock stops there.
  // Owed less than its own exit, it ends by leaving: coming back for less than
  // that is a flash.
  const remaining = deadline - window.performance.now();
  if (remaining < MESSAGE_EXIT_MS) {
    hideMessage();
    return;
  }
  window.clearTimeout(timer);
  owed = remaining;
  moving = true;
  announce({ ...layer, shown: false });
  moveTimer = window.setTimeout(showAgain, MESSAGE_EXIT_MS);
}

/** Shows a message that left one edge at the edge the layers now call for, owed what it had left. */
function showAgain(): void {
  moving = false;
  place({ ...layer, shown: true, edge: edgeNow() });
  startTheClock(owed + MESSAGE_ENTRY_MS);
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
