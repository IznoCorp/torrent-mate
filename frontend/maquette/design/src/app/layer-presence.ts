// WHETHER A LAYER IS OPEN — one fact, published for the one part of the frame
// that is placed by it.
//
// `app/focus.ts` already decides it: each time the markup says which layer is
// on top, it marks the rest of the frame `inert`. The message reads THAT
// decision rather than a second reading of the same attributes, so the two can
// never disagree about whether a layer is open.
//
// NOT IN THE STORE, for `app/message-presence.ts`'s measured reason: a store
// write re-renders every page, and a node replaced between a finger's press and
// its click loses the click (B-247). Its one subscriber is the message's host.
//
// AND HOW FAR DOWN THE FRAME A SCREEN'S OWN BAR REACHES. A screen keeps its way
// out — « Retour » — in a bar along its top, so a message placed at the top of
// the frame lay over it, and the tap did nothing for the message's five seconds.
// The offset is a MEASUREMENT, published the way `app/bar-height.ts` publishes
// the tab bar's height, and the message's `edge` reads it; it is zero whenever
// the layer on top is not a screen.

let open = false;
let observer: ResizeObserver | null = null;
const listeners = new Set<() => void>();

/**
 * Publishes how far down the frame the open screen's bar reaches, and keeps it
 * current while that screen is on top.
 *
 * Measured from the top of the box the message is positioned in — its offset
 * parent — because that is what the message's `top` counts from. Measured from
 * the shell instead, it read -798 px: the shell is not that box, and the message
 * stayed over the bar. Written only when it changes, for `app/bar-height.ts`'s
 * reason.
 *
 * Args:
 *     layer: The layer on top, or null when none is open.
 */
function publishScreenBarBottom(layer: Element | null): void {
  observer?.disconnect();
  observer = null;
  const bar = layer?.matches('[data-part="screen"]')
    ? layer.querySelector<HTMLElement>('[data-part="screen/bar"]')
    : null;
  const publish = () => {
    const frame = document.getElementById("toast")?.offsetParent;
    const offset = bar && frame
      ? Math.ceil(bar.getBoundingClientRect().bottom - frame.getBoundingClientRect().top)
      : 0;
    const current =
      document.documentElement.style.getPropertyValue("--tm-screen-bar-bottom");
    if (current !== offset + "px")
      document.documentElement.style.setProperty("--tm-screen-bar-bottom", offset + "px");
  };
  publish();
  if (bar && typeof ResizeObserver !== "undefined") {
    observer = new ResizeObserver(publish);
    observer.observe(bar);
  }
}

/**
 * Records which layer is on top, and tells whoever is watching when one opens
 * where none was or the last one closes.
 *
 * Args:
 *     layer: The drawer, a screen, the sheet or a confirmation — the one on
 *         top — or null when none is open.
 */
export function setLayerOpen(layer: Element | null): void {
  publishScreenBarBottom(layer);
  const on = layer !== null;
  if (open === on) return;
  open = on;
  for (const listener of listeners) listener();
}

/** Whether a layer is open right now. */
export function readLayerOpen(): boolean {
  return open;
}

/**
 * Subscribes to the fact.
 *
 * Args:
 *     onChange: Called when a layer opens where none was, and when the last one
 *         closes.
 *
 * Returns:
 *     The unsubscription.
 */
export function subscribeToLayerOpen(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}
