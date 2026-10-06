// One address, one file.
//
// A route is THIN: it names its path and composes what renders there. The
// lots progress is a feature's screen, and this file decides nothing about it
// beyond WHERE the address exists.
//
// IT EXISTS ONLY IN THE BUILDS THAT CARRY THE DEVELOPMENT PAGES (`lib/dev-pages.ts`):
// the router registers it there and nowhere else.
import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";
import { DevLotsScreen } from "../features/dev-lots/screen";

// The lots progress, read from what the host generated.
export const devLotsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dev/lots",
  component: DevLotsScreen,
});
