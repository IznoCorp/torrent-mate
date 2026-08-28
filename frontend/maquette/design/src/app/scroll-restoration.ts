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
   `[data-part="screen"][data-open]` resolves the React screen first (`#shell`
   precedes the legacy `#screen` in document order), which is exactly the one
   that is about to be unmounted; a legacy screen above it keeps its own
   restoration. With no screen open it is `#port`, the page's own viewport —
   see `activePort` for why that half was missing for a wave.

   WHAT THIS REPAIR DOES AND DOES NOT PAY OFF. `frontend-architecture.md` § 1
   lists three things that keep the semantic scroll index's door open, and one
   of them is « programmatic scrolling must have one path ». This function is
   now the one path for HISTORY-driven scrolling, which it was not — and that
   clause is still NOT paid: `app/focus.ts` writes `#port.scrollTop = 0` from
   the skip link, on the very element this function owns, and `ui/sheet.tsx`
   resets a panel's own offset. The claim first written here said the debt was
   settled, and a comment that says a debt is paid is worse than one that says
   nothing.

   IT ALSO CITED THE WRONG ENTRY. The three clauses belong to B-140; B-104 is
   about the generated contract types living under `mocks/`. The wrong number
   was inherited from `frontend-architecture.md` § 1, which makes the same
   mistake in the sentence that describes this very defect.

   Restoring mirrors the legacy re-apply: once as soon as the port exists,
   then once more when the late-loading posters have settled — the restored
   list is briefly too short and the browser clamps the offset back to 0. */
const scrollPositions = new Map<string, number>();
// A navigation that lands while a restoration is still waiting for its frames
// or its images invalidates it: the position belonged to the entry one has
// just left.
let restoreToken = 0;

/**
 * Says whether a history entry is a LAYER — a drawer, a panel, a sheet.
 *
 * A LAYER NEVER REPLACES THE PAGE'S CONTENT. It opens over it; `#port` keeps
 * its element, its height and its offset throughout, so there is nothing to
 * remember and nothing to put back. Saving across one stores the position the
 * page had when the layer OPENED, and restoring it on the way out overwrites
 * whatever the operator has scrolled to since.
 *
 * IT ONLY BECAME REACHABLE WITH B-140's REPAIR. While `activePort()` knew one
 * port out of two it returned null here and nothing was stored — and the stored
 * zero was skipped again by `if (remembered)`, which B-140's own entry called a
 * second, latent defect. Repairing both at once made the pair live: a page
 * scrolled to 300 with a drawer open came back to 0. Found by the wave gate,
 * which is what the wave gate is for.
 *
 * @param state The entry's state, as the history library stamps it.
 * @returns True when the entry is a layer rather than a page.
 */
function isLayer(state: unknown): boolean {
  return typeof (state as { layer?: unknown } | undefined)?.layer === "string";
}

function entryKey(state: unknown): string | null {
  const stamped = state as { key?: string; __TSR_key?: string } | undefined;
  return stamped?.key ?? stamped?.__TSR_key ?? null;
}

function activePort(): HTMLElement | null {
  // IT KNEW ONE PORT OUT OF TWO (B-140). It was `.screen.open .port` — the
  // viewport of an OVERLAY SCREEN — and the main pages do not scroll in one:
  // they scroll inside `#port`, which is never within a `.screen.open`. So on a
  // main page the save either stored nothing (the query returned null) or
  // stored the just-opened screen's offset under the departing page's key.
  // Either way the return found nothing to restore, and the operator landed at
  // the top of the list they had walked down.
  //
  // ANCHORED ON `data-*`, NEVER ON A STYLE CLASS (D4). `.port` is a class
  // Tailwind variants own and L07 has already moved once; `data-part` and
  // `data-open` are names chosen to be read, and `harness/scroll.py` reads the
  // same pair.
  //
  // THE OPEN SCREEN WINS, and the order is the whole of the function. A screen
  // is what is about to be unmounted at the instant the history subscription
  // runs, so its position is the one that can still be read — and while one is
  // open the page underneath is not what the operator is looking at.
  return document.querySelector<HTMLElement>(
    '[data-part="screen"][data-open] [data-part="viewport"]',
  ) ?? document.getElementById("port");
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
let currentIsLayer = isLayer(history.location.state);
history.subscribe(({ action, location }) => {
  const nextIsLayer = isLayer(location.state);
  // ACROSS A LAYER BOUNDARY, NEITHER HALF RUNS. Opening one must not store the
  // page's offset — the page is still on screen and still scrolling — and
  // closing one must not put an older offset back over it.
  const crossesALayer = currentIsLayer || nextIsLayer;
  const port = crossesALayer ? null : activePort();
  if (currentKey && port) scrollPositions.set(currentKey, port.scrollTop);
  currentKey = entryKey(location.state);
  currentIsLayer = nextIsLayer;
  restoreToken += 1;
  if (crossesALayer) return;
  // Only a RETURN restores: arriving forward on an address one has seen
  // before is a new visit, and it starts where a new visit starts.
  if (
    action.type !== "BACK" &&
    action.type !== "FORWARD" &&
    action.type !== "GO"
  )
    return;
  const remembered = currentKey ? scrollPositions.get(currentKey) : undefined;
  // A STORED ZERO IS A POSITION, not an absence. B-140's own register entry
  // named this as a second, latent defect in the same block, and the repair
  // closed the entry without touching it. It is latent because the top is where
  // a page starts anyway — until a surface's default position is not the top,
  // or the page host stops resetting `#port` on a draw.
  if (remembered !== undefined) restoreScroll(remembered, restoreToken);
});
}
