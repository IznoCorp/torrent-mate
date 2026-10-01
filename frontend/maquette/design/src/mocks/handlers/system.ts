// Whether the machine is well.
import DEPENDENCIES from "../seeds/dependencies.json";
import DISKS from "../seeds/disks.json";
import ERRORS from "../seeds/errors.json";
import INDEX_HEALTH from "../seeds/index-health.json";
import SCHEDULERS from "../seeds/schedulers.json";
import SERVICES from "../seeds/services.json";
import { GET, route } from "./shared";
import { mockState } from "../state";
import type { Schemas } from "../../lib/contract-schemas";
import type { MockRoute } from "../router";

// A POSED HEALTHY MACHINE answers the same facts, each state that asks for
// care turned to its healthy twin: a disk nearly full has room, the index's
// anomalies are none. The contract's own state codes.
const HEALTHY_TWIN: Record<string, string> = { nearly_full: "room", to_clean: "none" };

/**
 * Facts as the layer answers them: the seed, or its posed healthy twin.
 *
 * @param facts The seeded facts.
 * @returns What the read answers.
 */
function asPosed(facts: unknown): Schemas["Fact"][] {
  const seeded = facts as Schemas["Fact"][];
  if (!mockState().machineHealthy) return seeded;
  return seeded.map((fact) =>
    fact.state && HEALTHY_TWIN[fact.state]
      ? { ...fact, state: HEALTHY_TWIN[fact.state] as NonNullable<Schemas["Fact"]["state"]> }
      : fact);
}

// What an answer carries when the maquette genuinely has nothing to put there.
const NOTHING_TO_REPORT = "";

/** Every route this subject answers. */
export function systemRoutes(): MockRoute[] {
  return [
    route("readServices", GET, "/api/system/services", () => SERVICES),
    route("readDependencies", GET, "/api/system/dependencies", () => DEPENDENCIES),
    route("readErrors", GET, "/api/system/errors", () => ERRORS),
    route("readSchedulers", GET, "/api/maintenance/schedulers", () => SCHEDULERS),
    route("readDisks", GET, "/api/maintenance/disks", () => asPosed(DISKS)),
    route("readIndexHealth", GET, "/api/maintenance/index-health", () => asPosed(INDEX_HEALTH)),
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
