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
// So the shell PORTALS into the legacy `#view`, and the fragment stops writing
// there for a page that has migrated (`shellOwned` on its `PAGES_OF` entry;
// everything else `render()` does still runs, because the bar, the nav and the
// save bar are shared furniture).
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
import { useUiState } from "../lib/store-access";
import { AccountPage } from "../features/account/page";
import { AcquisitionPage } from "../features/acquisition/page";
import { ArrivalsPage } from "../features/arrivals/page";
import { LibraryPage } from "../features/library/page";
import { MaintenancePage } from "../features/maintenance/page";
import { NotFoundPage } from "../app/not-found";
import { SettingsPage } from "../features/settings/page";
import { SystemPage } from "../features/system/page";
import { body } from "../ui/variants";

type MigratedPage = {
  Body: () => ReactElement | null;
  // The single root the legacy view emitted, when there is one. A page that
  // emits SEVERAL roots (the Médiathèque draws four siblings) declares none and
  // draws them itself. Either way the markup is what the legacy returned: this
  // wrapper is rendered by React, not added by it.
  root?: string;
  // The recorded oracle's anchor for this page's body — `frontend/maquette/
  // oracle.py`, whose region table is `regions.json`. A NAME, chosen here and
  // written in English, rather than derived from the page id: an id like `cfg`
  // or `404` is the value of `state.page` and an address, which is data. A page
  // drawing its own roots carries its own anchors and declares none here.
  region?: string;
};

// The ONE place a later wave adds a page. An id absent from this table is a
// page the legacy still draws, and nothing here touches it.
const PAGES: Record<string, MigratedPage> = {
  acq: { Body: AcquisitionPage },
  sys: { Body: SystemPage, root: "body", region: "system/body" },
  arr: { Body: ArrivalsPage, root: "body", region: "arrivals/body" },
  lib: { Body: LibraryPage },
  maint: { Body: MaintenancePage, root: "body", region: "maintenance/body" },
  cfg: { Body: SettingsPage, root: "body", region: "settings/body" },
  // french-ok: this key IS the page ID — the value of `state.page` and the
  // `?page=` address. It is data, not a property name: renaming it left
  // the shell unable to find the page at all, and the account surface
  // drew nothing.
  profile: { Body: AccountPage, root: "body", region: "account/body" },
  "404": { Body: NotFoundPage, root: "body", region: "not-found/body" },
};

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
    // The page table the fragment draws the tab bar from. Read here for ONE
    // value — the page's name — and see `PageHeading` for why it is read
    // rather than restated.
    PAGES_OF?: () => { id: string; l: string }[];
    // Called by the fragment's `render()` immediately BEFORE it writes `#view`
    // for a page the shell does not own.
    __releasePage?: () => void;
    // The pages this side claims, published so the two tables can be COMPARED.
    // They are independent lists that must agree — an id here without
    // `shellOwned` in `PAGES_OF()` draws in both worlds at once, consistently,
    // which no drawing-shaped hold can see.
    __shellPages?: string[];
  }
}

window.__releasePage = () => {
  flushSync(() => setReleased(true));
};

window.__shellPages = Object.keys(PAGES);

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
 * WHY THE TEXT IS READ AND NOT RESTATED. The name already exists, once, in the
 * fragment's page table — the same string the tab bar prints. Copying it into
 * `fr.json` today would create a second source that drifts silently until
 * someone renames a tab. It moves there in ONE step when the tab bar migrates
 * and the fragment's table goes with it, which is D5's « dies by subtraction »
 * applied to a string.
 */
function PageHeading({ page }: { page: string }): ReactElement | null {
  const entry = window.PAGES_OF?.().find((candidate) => candidate.id === page);
  if (!entry?.l) return null;
  return <h1 className="visually-hidden" data-part="page/heading">{entry.l}</h1>;
}

export function PageHost(): ReactElement | null {
  const page = useUiState().page as string | undefined;
  const phase = useUiState().phase as string | undefined;
  const migrated = page ? PAGES[page] : undefined;
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
