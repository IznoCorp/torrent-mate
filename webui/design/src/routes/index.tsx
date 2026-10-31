// One address, one file — and this one is the root.
//
// `/` is where a bare link, a bookmark and an installed application's scope all
// land. It is not a page: the boot settles it onto the home page's own address
// (`/acquisition`) with a REPLACE, so nothing is inserted into the history and
// the first Back still reaches the guard entry rather than a bounce.
//
// The settling is done by the engine's boot through `window.__address`, not by
// a router redirect thrown from `beforeLoad`. A redirect would be a SECOND
// mechanism writing the address, beside the single writer this shell is built
// around — and the boot is the one place in this application where a second
// writer has already cost two defects (R69's own record: the boot's
// `replaceState` corrected first, then the guard entry pushed straight after
// putting the wrong address back).
//
// So this route exists to make `/` a KNOWN address rather than one nobody
// serves — which is what keeps it out of the not-found surface for the instant
// between the document loading and the boot settling it.
//
// The parent is imported from `app/root-route`, never from the shell: the shell
// imports the assembled tree, so a route reaching back into it would close a
// cycle.

import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";

export const rootAddressRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => null, // the pages draw into the legacy `#view`, through the page host
});
