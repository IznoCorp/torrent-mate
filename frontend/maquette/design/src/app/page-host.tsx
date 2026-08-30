// design/src/pages/host.tsx
// The PAGE host — the machinery a page needs and a screen never did.
//
// Every surface migrated before the pages is an overlay SCREEN: it has its own
// path, and it renders inside the React root `#shell`, which sits beside
// `.stage`. A PAGE has no address of its own. `/` stays the pages' route with
// its legacy query (`?page=&rub=`), the legacy parser keeps owning it, and a
// page's markup has to land inside `#view` — where the stylesheet, the harness
// selectors and the document-level click delegation all expect it.
//
// So the shell PORTALS into the legacy `#view`, and the fragment writes there
// for no page at all: every page in `app/navigation.ts` carries a component and
// none carries a renderer. Everything else `render()` does still runs, because
// the bar, the nav and the save bar are shared furniture.
//
// THE HANDOVER IS ANNOUNCED, and that is the whole of the difficulty. Leaving a
// migrated page for a legacy one, the legacy's own `view.innerHTML = …` runs
// FIRST, synchronously, from `render()` — and React would unmount the portal
// after, on its own schedule, removing children that are already detached. That
// throws `NotFoundError` and tears the root down, which this conversion has
// measured once already, on a save bar.
//
// An earlier arrangement dodged it with a HOST ELEMENT: React portalled into a
// `<div class="body">` of its own, the legacy's write removed that one node
// whole, and React only ever touched children of a node it owned. It worked for
// three pages that each emit exactly one root — and it cannot describe a page
// that emits FOUR (the Médiathèque draws `.viewtabs`, `.filters`, `.countline`
// and `.body` as siblings). Wrapping those four would be a markup change, which
// this conversion does not make.
//
// So the fragment ANNOUNCES the handover instead, and EMPTIES the container when
// it hands ownership over — both inside `render()`, the one place that already
// knows which world owns the page:
//
//   · taking:    `view.innerHTML = ""`, once, on the transition; React draws
//     into the empty container on its own schedule;
//   · releasing: `window.__releasePage()` — synchronous, so React has let go of
//     every node before the next statement writes the container.
//
// What was implicit and fragile is now explicit, and both halves are measured.
import { useLayoutEffect, useSyncExternalStore } from "react";
import type { ReactElement } from "react";
import { createPortal, flushSync } from "react-dom";
import { useTranslation } from "react-i18next";
import { useUiState } from "../lib/store-access";
import { NAVIGATION, rowFor } from "./navigation";
import { body } from "../ui/variants";

// THE TABLE IS `app/navigation.ts`'s, and this file no longer keeps one.
// `PAGES` lived here — id → component, root and oracle region — beside three
// other copies of the same fact. What the host needs from a row is exactly
// what the row already carries.

// The release, as a value React can subscribe to. It lives outside React
// because the FRAGMENT is what asks for it, and `useSyncExternalStore` is the
// same door every other out-of-React value comes through here.
let released = false;
const listeners = new Set<() => void>();

function subscribeRelease(callback: () => void): () => void {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
}

function setReleased(next: boolean): void {
  if (released === next) return;
  released = next;
  for (const listener of listeners) listener();
}

declare global {
  interface Window {
    // Called by the fragment's `render()` immediately BEFORE it writes `#view`
    // for a page the shell does not own.
    __releasePage?: () => void;
    // The pages this side claims. It USED to be published so the two page
    // tables could be compared — this file's and the engine's — because they
    // were independent lists kept identical by hand, and a disagreement in one
    // direction drew a page in both worlds at once, consistently, which no
    // drawing-shaped hold can see. There is one table now, so what a rule
    // compares is no longer two lists: it is this seam against the addresses
    // and against what the interface can actually render.
    __shellPages?: string[];
  }
}

window.__releasePage = () => {
  flushSync(() => setReleased(true));
};

window.__shellPages = NAVIGATION.map((row) => row.id);

/**
 * The page's name, as a heading no one sees and every screen reader reads.
 *
 * WHY IT EXISTS. axe reported `page-has-heading-one` on 49 of the 83 named
 * states: the prototype has 26 `<h2>` and a single `<h1>`, on the login screen.
 * A page whose sections are all level two has an outline that starts in the
 * middle, and a screen reader navigating by heading finds no top.
 *
 * WHY IT IS HIDDEN. The interface deliberately shows no page title — the tab
 * bar says where you are, and that is a design decision this lot does not get
 * to overturn. `.visually-hidden` keeps the element out of the layout and IN
 * the accessibility tree, and being out of flow it moves no rectangle the
 * oracle measures.
 *
 * WHERE THE TEXT COMES FROM, and it moved in one step. It used to be read off
 * the engine's own page table, because copying it into `fr.json` while the tab
 * bar was still drawn from that table would have created a second source that
 * drifts silently until someone renames a tab. The table left the engine and
 * the string went with it: the row carries a KEY, `fr.json` carries the word,
 * and the tab bar reads the same key. D5's « dies by subtraction », applied to
 * a string.
 */
function PageHeading({ page }: { page: string }): ReactElement | null {
  const { t } = useTranslation();
  const row = rowFor(page);
  if (!row) return null;
  return <h1 className="visually-hidden" data-part="page/heading">{t(row.labelKey)}</h1>;
}

export function PageHost(): ReactElement | null {
  const page = useUiState().page as string | undefined;
  const phase = useUiState().phase as string | undefined;
  const migrated = rowFor(page);
  const isReleased = useSyncExternalStore(subscribeRelease, () => released);

  // Ownership resumes the moment a migrated page is current again. The fragment
  // has already emptied `#view` by then — it does that on the same transition,
  // for the same reason the shell used to do it itself.
  useLayoutEffect(() => {
    if (migrated && released) setReleased(false);
  });

  // `aria-busy` ON THE MAIN REGION, from the ONE place that knows every page's
  // phase. Marked on each page instead, it would be eight call sites and the
  // eighth would be forgotten — this repository has paid for that shape more
  // than once. A screen reader that is told a region is busy stops reading its
  // half-built contents and waits.
  useLayoutEffect(() => {
    const main = document.getElementById("port");
    if (!main) return;
    if (migrated && phase === "loading") main.setAttribute("aria-busy", "true");
    else main.removeAttribute("aria-busy");
  }, [migrated, phase]);

  if (!migrated || isReleased) return null;
  const view = document.getElementById("view");
  if (!view) return null;
  const { Body, root, region } = migrated;
  return createPortal(
    <>
      <PageHeading page={page as string} />
      {root ? (
        <div
          // THE ROOT IS A NAME, AND THE VARIANT IS ITS STYLE. Six pages declare
          // `root: "body"` in the table above, so this one element carries the
          // page column for most of the application — and it was the site the
          // first pass of phase 6 missed, because the class arrives as a VALUE
          // from a table rather than as a literal in the markup.
          className={root === "body" ? body() : root}
          data-region={region}
        >
          <Body />
        </div>
      ) : (
        <Body />
      )}
    </>,
    view,
  );
}
