// design/src/pages/host.tsx
// The PAGE host — the machinery a page needs and a screen never did.
//
// Every surface migrated before this one is an overlay SCREEN: it has its own
// path, and it renders inside the React root `#coquille`, which sits beside
// `.stage`. A PAGE has no address of its own. `/` stays the pages' route with
// its legacy query (`?page=&rub=`), the legacy parser keeps owning it, and a
// page's markup has to land inside `#view` — where the stylesheet, the harness
// selectors and the document-level click delegation all expect it.
//
// So the shell PORTALS into the legacy `#view`, and the fragment stops writing
// there for a page that has migrated (`shellOwned` on its `PAGES_OF` entry;
// `render()` skips the `innerHTML` write and does everything else, because the
// bar, the nav and the save bar are shared furniture).
//
// WHY A HOST ELEMENT RATHER THAN PORTALLING STRAIGHT INTO `#view`. Leaving a
// migrated page for a legacy one, the legacy's own `view.innerHTML = …` runs
// FIRST (synchronously, from `applyState`) and React unmounts the portal after,
// on its own schedule — so React would be removing children that are already
// detached. With a host element, React only ever adds and removes children of
// `host`, which it owns whether or not `host` is still in the document; the
// legacy write removes the whole host in one operation, and the cleanup below
// removes it again harmlessly.
//
// The host IS the page's root element, never a wrapper: all three migrated
// pages emit exactly one `<div class="body">`, so the host carries that class
// and the component renders its CHILDREN. A wrapper would be a markup change,
// and this conversion changes no markup.
import { useLayoutEffect, useRef } from "react";
import type { ReactElement } from "react";
import { createPortal } from "react-dom";
import { useUiState } from "../data";
import { ArrivalsPage } from "./arrivals";
import { MaintenancePage } from "./maintenance";
import { SettingsPage } from "./settings";
import { SystemPage } from "./system";

type MigratedPage = {
  // The root element the legacy view emitted, recreated verbatim.
  tag: string;
  className: string;
  Body: () => ReactElement | null;
};

// The ONE place a later wave adds a page. An id absent from this table is a
// page the legacy still draws, and nothing here touches it.
const PAGES: Record<string, MigratedPage> = {
  sys: { tag: "div", className: "body", Body: SystemPage },
  arr: { tag: "div", className: "body", Body: ArrivalsPage },
  maint: { tag: "div", className: "body", Body: MaintenancePage },
  cfg: { tag: "div", className: "body", Body: SettingsPage },
};

export function PageHost(): ReactElement | null {
  const page = useUiState().page as string | undefined;
  const migrated = page ? PAGES[page] : undefined;

  // One host per page id: switching between two migrated pages must not reuse
  // the previous page's element, or its root attributes would leak across.
  //
  // A REF, not `useMemo`: React documents a memo's cache as droppable, and a
  // drop here would silently re-create the page's whole DOM — a new host, a
  // fresh `replaceChildren`, and the scroll position gone, with no state change
  // to explain it. Assigning during render is the sanctioned lazy-init shape.
  const hostRef = useRef<{ page: string; element: HTMLElement } | null>(null);
  if (migrated && page && hostRef.current?.page !== page) {
    const element = document.createElement(migrated.tag);
    element.className = migrated.className;
    hostRef.current = { page, element };
  }
  const host = migrated && page ? (hostRef.current?.element ?? null) : null;

  useLayoutEffect(() => {
    if (!host) return undefined;
    const view = document.getElementById("view");
    if (!view) return undefined;
    // Taking ownership removes whatever the previous page left. It happens
    // HERE, once, on the transition — not on every render, and not in the
    // legacy, which cannot know when React is ready to draw.
    view.replaceChildren(host);
    return () => {
      host.remove();
    };
  }, [host]);

  if (!migrated || !host) return null;
  const { Body } = migrated;
  return createPortal(<Body />, host);
}
