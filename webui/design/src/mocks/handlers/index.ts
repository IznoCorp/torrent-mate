// Every route the mock layer answers, assembled once.
//
// One module per SUBJECT, and the table is built rather than declared as a
// constant: a handler reads the mutable state, and a constant built at import
// would capture the state object that existed then instead of the one a reset
// has just replaced.
import { accountRoutes } from "./accounts";
import { acquisitionRoutes } from "./acquisition";
import { acquisitionVerbRoutes } from "./acquisition-verbs";
import { authenticationRoutes } from "./authentication";
import { closureRoutes } from "./posed-closure";
import { completenessRoutes } from "./completeness";
import { configurationRoutes } from "./configuration";
import { crossSeedRoutes } from "./cross-seed";
import { decisionRoutes } from "./decisions";
import { libraryRoutes } from "./library";
import { maintenanceRoutes } from "./maintenance";
import { membershipRoutes } from "./membership";
import { notificationRoutes } from "./notifications";
import { mediaRoutes } from "./media";
import { pipelineRoutes } from "./pipeline";
import { requesterRoutes } from "./requesters";
import { stagingRoutes } from "./staging";
import { systemRoutes } from "./system";
import { trackerRoutes } from "./trackers";
import type { MockRoute } from "../router";

/** Every route, in a stable order. */
export function routes(): MockRoute[] {
  return [
    ...authenticationRoutes(),
    ...accountRoutes(),
    ...notificationRoutes(),
    ...libraryRoutes(),
    ...membershipRoutes(),
    ...mediaRoutes(),
    ...acquisitionRoutes(),
    ...acquisitionVerbRoutes(),
    ...closureRoutes(),
    ...requesterRoutes(),
    ...completenessRoutes(),
    ...stagingRoutes(),
    ...pipelineRoutes(),
    ...decisionRoutes(),
    ...systemRoutes(),
    ...maintenanceRoutes(),
    ...configurationRoutes(),
    ...trackerRoutes(),
    ...crossSeedRoutes(),
  ];
}
