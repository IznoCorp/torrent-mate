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
import { AddScreen } from "../features/acquisition/add-screen";

// The second screen route, and the first whose OWN search params are
// router-owned rather than merely read: `q` (the typed query) and `mode`
// ("follow" — follow a new title — or "identify" — associate a stuck
// folder, reached from the resolution screen's manual search) live here for
// as long as the address reads `/add`, replacing `state.addQ`/
// `state.addMode` as the SOURCE of truth on this path (see `add.tsx`'s own
// doc comment for the transitional contract with the one legacy reader that
// remains). Absent means "follow" / no query, the same "absent is unchanged"
// convention `catchAllRoute`'s `validateSearch` already uses above.
type AddSearchParams = { q?: string; mode?: "follow" | "identify" };
export const addRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/add",
  validateSearch: (raw: Record<string, unknown>): AddSearchParams => {
    const read: AddSearchParams = {};
    if (typeof raw.q === "string" && raw.q) read.q = raw.q;
    if (raw.mode === "identify") read.mode = "identify";
    return read;
  },
  component: AddScreen,
});
