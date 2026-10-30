// One address, one file.
//
// A route is THIN: it names its path and composes what renders there. A PAGE
// renders nothing here — its markup lands in the legacy `#view` through
// `app/page-host.tsx`, so this file's job is done once the address EXISTS.
// Declaring it is what makes `/trackers` a known address rather than one
// nobody serves.
//
// The parent is imported from `app/root-route`, never from the shell: the shell
// imports the assembled tree, so a route reaching back into it would close a
// cycle.

import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";

export const trackersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/trackers",
  component: () => null,
});
