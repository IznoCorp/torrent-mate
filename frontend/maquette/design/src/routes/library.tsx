// One address, one file.
//
// A route is THIN: it names its path and composes what renders there. A PAGE
// renders nothing here — its markup must land inside the legacy `#view`, where
// the stylesheet, the harness selectors and the document-level click delegation
// all expect it, so `app/page-host.tsx` portals into that container and this
// file's job is done once the address EXISTS. Declaring it is what makes
// `/media` a known address rather than one nobody serves.
//
// The parent is imported from `app/root-route`, never from the shell: the shell
// imports the assembled tree, so a route reaching back into it would close a
// cycle.

import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";

// This page's own dials, and only its own: D1 puts the STATE in the query, and
// a dial belongs to the surface it describes. Absent means « unchanged », the
// same convention every other route here already uses.
type SearchParams = { lens?: string; mode?: string; cat?: string };

export const libraryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/media",
  validateSearch: (raw: Record<string, unknown>): SearchParams => {
    const read: SearchParams = {};
    for (const name of ["lens", "mode", "cat"] as const)
      if (typeof raw[name] === "string" && raw[name]) read[name] = raw[name] as string;
    return read;
  },
  component: () => null,
});
