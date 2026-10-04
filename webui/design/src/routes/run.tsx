// One address, one file.
//
// A route is THIN: it names its path and composes what renders there. The
// passage's own screen is a feature's, and this file decides nothing about it.
import { createRoute } from "@tanstack/react-router";
import { rootRoute } from "../app/root-route";
import { RunScreen } from "../features/system/run-screen";

// One passage's screen, reached from a row of « Les passages ».
export const runRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/run/$runUid",
  component: RunScreen,
});
