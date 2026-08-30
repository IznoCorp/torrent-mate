// THE POPOVER'S VERBS, and the seam the dying engine says them through.
//
// `{ anchor, content }` — the frame decides where, the feature decides what.
// The engine's `openPopEp(button)` built the node, placed it, wrote its
// sentence and armed its dismissal in one function; only the sentence is a
// producer's, and it moves to its feature at L19 with the rest of Part 12.
//
// NOT IN THE STORE, and for the reason `app/message-presence.ts` records: a
// store write re-renders every page, and a popover is opened BY a tap — a
// re-render in the gap between a press and the click that follows destroys the
// click (B-247). It has its own subscription with one subscriber.
import type { PopoverContent } from "../ui/popover";

type Layer = { anchor: HTMLElement | null; content: PopoverContent | null };

// The snapshot only changes when the layer does — `useSyncExternalStore`
// compares what it is handed, and a fresh object per call loops for ever.
let layer: Layer = { anchor: null, content: null };
const listeners = new Set<() => void>();
let dismiss: (() => void) | null = null;

function announce(next: Layer): void {
  layer = next;
  for (const listener of listeners) listener();
}

export function readPopover(): Layer {
  return layer;
}

export function subscribeToPopover(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/** Takes the popover off screen and disarms whatever was waiting to do it. */
export function closePopover(): void {
  if (dismiss) {
    document.removeEventListener("pointerdown", dismiss);
    dismiss = null;
  }
  if (layer.anchor === null && layer.content === null) return;
  announce({ anchor: null, content: null });
}

/**
 * Opens a popover against an anchor.
 *
 * Args:
 *     anchor: What was tapped.
 *     content: The facts to show.
 */
export function openPopover(anchor: HTMLElement, content: PopoverContent): void {
  closePopover();
  announce({ anchor, content });
  // THE NEXT TAP CLOSES IT, and the `setTimeout` is load-bearing: the very tap
  // that opened it is still travelling, and a listener armed in the same task
  // would receive it and close what had just opened. The engine armed it the
  // same way, for the same reason.
  window.setTimeout(() => {
    dismiss = () => closePopover();
    document.addEventListener("pointerdown", dismiss, { once: true });
  }, 0);
}

declare global {
  interface Window {
    /** The popover's verbs, as the engine's producers say them. */
    __popover?: {
      open: (anchor: HTMLElement, content: PopoverContent) => void;
      close: () => void;
    };
  }
}

export function installPopoverHost(): void {
  window.__popover = { open: openPopover, close: closePopover };
}
