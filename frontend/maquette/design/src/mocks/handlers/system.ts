// Whether the machine is well.
import DEPENDENCIES from "../seeds/DEPENDENCIES.json";
import DISKS from "../seeds/DISKS.json";
import ERRORS from "../seeds/ERRORS.json";
import INDEX from "../seeds/INDEX.json";
import SCHEDULERS from "../seeds/SCHEDULERS.json";
import SERVICES from "../seeds/SERVICES.json";
import { GET, route } from "./shared";
import type { MockRoute } from "../router";

/** Every route this subject answers. */
export function systemRoutes(): MockRoute[] {
  return [
    route("readServices", GET, "/api/system/services", () => SERVICES),
    route("readDependencies", GET, "/api/system/dependencies", () => DEPENDENCIES),
    route("readErrors", GET, "/api/system/errors", () => ERRORS),
    route("readSchedulers", GET, "/api/maintenance/schedulers", () => SCHEDULERS),
    route("readDisks", GET, "/api/maintenance/disks", () => DISKS),
    route("readIndexHealth", GET, "/api/maintenance/index-health", () => INDEX),
    // The maquette is not a server and has no version of its own. The shape is
    // answered so a surface can be wired to it; the values are EMPTY rather
    // than invented, because a plausible-looking version string is exactly the
    // kind of made-up datum this whole lot exists to keep out.
    route("readVersion", GET, "/api/version", () => ({ version: "", commit: "" })),
  ];
}
