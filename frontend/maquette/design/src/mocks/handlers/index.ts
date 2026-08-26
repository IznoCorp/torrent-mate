// Every route the mock layer answers, assembled once.
//
// One module per SUBJECT, and the table is built rather than declared as a
// constant: a handler reads the mutable state, and a constant built at import
// would capture the state object that existed then instead of the one a reset
// has just replaced.
import { acquisitionRoutes } from "./acquisition";
import { authenticationRoutes } from "./authentication";
import { configurationRoutes } from "./configuration";
import { decisionRoutes } from "./decisions";
import { libraryRoutes } from "./library";
import { maintenanceRoutes } from "./maintenance";
import { mediaRoutes } from "./media";
import { stagingRoutes } from "./staging";
import { systemRoutes } from "./system";
import type { MockRoute } from "../router";

/** Every route, in a stable order. */
export function routes(): MockRoute[] {
  return [
    ...authenticationRoutes(),
    ...libraryRoutes(),
    ...mediaRoutes(),
    ...acquisitionRoutes(),
    ...stagingRoutes(),
    ...decisionRoutes(),
    ...systemRoutes(),
    ...maintenanceRoutes(),
    ...configurationRoutes(),
  ];
}
