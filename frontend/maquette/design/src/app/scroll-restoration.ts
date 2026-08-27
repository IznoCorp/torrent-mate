// Scroll follows the history entry.
//
// Its own file because it is its own subject: nothing else in the shell reads
// or writes a scroll offset, and nothing here knows what a route or a panel is.
import { history } from "./history-bridge";

/* ── SCROLL FOLLOWS THE HISTORY ENTRY ─────────────────────────────────────
   A screen opened OVER another one used to be the same LAYER replacing its
   own content, and the legacy layer restored the covered screen's scroll
   itself when it unwound (`closeScreen`). Router-owned screens replace each
   other by UNMOUNTING instead: the covered screen's DOM — and its scroll
   offset with it — is gone by the time one comes back to it, and the
   operator lands at the top of the list they had walked down.

   The memory is kept HERE, in the shell, and keyed per HISTORY ENTRY (the
   library stamps every entry with its own `key`), never per address: the
   same `/add?q=lucky` reached twice is two entries and two positions.
   Components stay unaware — nothing below is a prop, a hook or a context.

   Reading happens in the history subscription, which runs BEFORE React
   commits the new route: the outgoing screen is still in the DOM at that
   instant, which is the only moment its position can still be read.
   `.screen.open .port` resolves the React screen first (`#shell` precedes
   the legacy `#screen` in document order), which is exactly the one that is
   about to be unmounted; a legacy screen above it keeps its own restoration.

   Restoring mirrors the legacy re-apply: once as soon as the port exists,
   then once more when the late-loading posters have settled — the restored
   list is briefly too short and the browser clamps the offset back to 0. */
const scrollPositions = new Map<string, number>();
// A navigation that lands while a restoration is still waiting for its frames
// or its images invalidates it: the position belonged to the entry one has
// just left.
let restoreToken = 0;

function entryKey(state: unknown): string | null {
  const stamped = state as { key?: string; __TSR_key?: string } | undefined;
  return stamped?.key ?? stamped?.__TSR_key ?? null;
}

function activePort(): HTMLElement | null {
  return document.querySelector<HTMLElement>(".screen.open .port");
}

function restoreScroll(y: number, token: number): void {
  // The router commits its re-render on its own schedule, so the port of the
  // screen being restored does not exist yet at subscription time. A bounded
  // retry over a few frames is what waits for it without polling forever.
  // Enough frames for a query to land and its rows to be drawn.
  let framesLeft = 30;
  const attempt = () => {
    if (token !== restoreToken) return;
    const port = activePort();
    if (!port) {
      if (--framesLeft > 0) requestAnimationFrame(attempt);
      return;
    }
    port.scrollTop = y;
    // AND IF IT WAS CLAMPED, THE CONTENT IS NOT ALL THERE YET. A list whose
    // rows arrive from a query is short at this instant, and the browser
    // refuses an offset past the end — silently, by moving it. It used to be
    // whole before the first frame, because it came from a fixture; the same
    // bounded retry the port itself needs is what waits for it now. Measured:
    // a walk back landed at 177 px where it had left at 300.
    if (port.scrollTop < y && framesLeft > 0) {
      framesLeft -= 1;
      requestAnimationFrame(attempt);
      return;
    }
    const images = [...port.querySelectorAll("img")].filter(
      (image) => !image.complete,
    );
    let pending = images.length;
    images.forEach((image) =>
      image.addEventListener(
        "load",
        () => {
          if (--pending <= 0 && token === restoreToken) port.scrollTop = y;
        },
        { once: true },
      ),
    );
  };
  requestAnimationFrame(attempt);
}

/**
 * Starts remembering and restoring the scroll offset per history entry.
 *
 * Called once from the boot. It subscribes for the document's lifetime — there
 * is nothing to unsubscribe, and a returned disposer nobody calls would be a
 * promise this module does not keep.
 */
export function installScrollRestoration(): void {
let currentKey = entryKey(history.location.state);
history.subscribe(({ action, location }) => {
  const port = activePort();
  if (currentKey && port) scrollPositions.set(currentKey, port.scrollTop);
  currentKey = entryKey(location.state);
  restoreToken += 1;
  // Only a RETURN restores: arriving forward on an address one has seen
  // before is a new visit, and it starts where a new visit starts.
  if (
    action.type !== "BACK" &&
    action.type !== "FORWARD" &&
    action.type !== "GO"
  )
    return;
  const remembered = currentKey ? scrollPositions.get(currentKey) : undefined;
  if (remembered) restoreScroll(remembered, restoreToken);
});
}
