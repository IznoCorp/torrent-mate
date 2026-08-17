// design/src/pages/host.tsx
// The PAGE host — the machinery a page needs and a screen never did.
//
// Every surface migrated before the pages is an overlay SCREEN: it has its own
// path, and it renders inside the React root `#coquille`, which sits beside
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
import { useUiState } from "../data";
import { ArrivalsPage } from "./arrivals";
import { LibraryPage } from "./library";
import { MaintenancePage } from "./maintenance";
import { SettingsPage } from "./settings";
import { SystemPage } from "./system";

type MigratedPage = {
  Body: () => ReactElement | null;
  // The single root the legacy view emitted, when there is one. A page that
  // emits SEVERAL roots (the Médiathèque draws four siblings) declares none and
  // draws them itself. Either way the markup is what the legacy returned: this
  // wrapper is rendered by React, not added by it.
  root?: string;
};

// The ONE place a later wave adds a page. An id absent from this table is a
// page the legacy still draws, and nothing here touches it.
const PAGES: Record<string, MigratedPage> = {
  sys: { Body: SystemPage, root: "body" },
  arr: { Body: ArrivalsPage, root: "body" },
  lib: { Body: LibraryPage },
  maint: { Body: MaintenancePage, root: "body" },
  cfg: { Body: SettingsPage, root: "body" },
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
    // Called by the fragment's `render()` immediately BEFORE it writes `#view`
    // for a page the shell does not own.
    __releasePage?: () => void;
  }
}

window.__releasePage = () => {
  flushSync(() => setReleased(true));
};

export function PageHost(): ReactElement | null {
  const page = useUiState().page as string | undefined;
  const migrated = page ? PAGES[page] : undefined;
  const isReleased = useSyncExternalStore(subscribeRelease, () => released);

  // Ownership resumes the moment a migrated page is current again. The fragment
  // has already emptied `#view` by then — it does that on the same transition,
  // for the same reason the shell used to do it itself.
  useLayoutEffect(() => {
    if (migrated && released) setReleased(false);
  });

  if (!migrated || isReleased) return null;
  const view = document.getElementById("view");
  if (!view) return null;
  const { Body, root } = migrated;
  return createPortal(
    root ? (
      <div className={root}>
        <Body />
      </div>
    ) : (
      <Body />
    ),
    view,
  );
}
