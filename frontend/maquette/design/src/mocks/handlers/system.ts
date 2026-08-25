// Whether the machine is well.
import DEPENDENCIES from "../seeds/dependencies.json";
import DISKS from "../seeds/disks.json";
import ERRORS from "../seeds/errors.json";
import INDEX_HEALTH from "../seeds/index-health.json";
import SCHEDULERS from "../seeds/schedulers.json";
import SERVICES from "../seeds/services.json";
import { GET, route } from "./shared";
import type { MockRoute } from "../router";

// What an answer carries when the maquette genuinely has nothing to put there.
const NOTHING_TO_REPORT = "";

/** Every route this subject answers. */
export function systemRoutes(): MockRoute[] {
  return [
    route("readServices", GET, "/api/system/services", () => SERVICES),
    route("readDependencies", GET, "/api/system/dependencies", () => DEPENDENCIES),
    route("readErrors", GET, "/api/system/errors", () => ERRORS),
    route("readSchedulers", GET, "/api/maintenance/schedulers", () => SCHEDULERS),
    route("readDisks", GET, "/api/maintenance/disks", () => DISKS),
    route("readIndexHealth", GET, "/api/maintenance/index-health", () => INDEX_HEALTH),
    // The maquette is not a server and has no version of its own. The shape is
    // answered so a surface can be wired to it; the value is EMPTY rather than
    // invented, because a plausible-looking version string is exactly the kind
    // of made-up datum this whole lot exists to keep out. The operation's
    // `x-unseeded` in the contract says so.
    route("readVersion", GET, "/api/version", () => ({
      version: NOTHING_TO_REPORT,
      commit: NOTHING_TO_REPORT,
    })),
  ];
}
