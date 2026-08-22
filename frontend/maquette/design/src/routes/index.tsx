// One address, one file.
//
// A route is THIN: it names its path and composes what renders there. Anything
// it would otherwise decide belongs to the feature it renders. The six of them
// lived inside the shell, which is how a file that boots the application also
// came to hold the address table.
//
// The parent is imported from `app/root-route`, never from the shell: the
// shell imports the assembled tree, so a route reaching back into it would
// close a cycle.

import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";

// R69's addressable state, validated — absent means "unchanged", as before.
type SearchParams = {
  page?: string;
  tab?: string;
  lens?: string;
  mode?: string;
  cat?: string;
  rub?: string;
};

export const catchAllRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  validateSearch: (raw: Record<string, unknown>): SearchParams => {
    const read: SearchParams = {};
    for (const name of ["page", "tab", "lens", "mode", "cat", "rub"] as const)
      if (typeof raw[name] === "string" && raw[name])
        read[name] = raw[name] as string;
    return read;
  },
  component: () => null, // the legacy DOM lives outside the React root until its surfaces migrate
});
