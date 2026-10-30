// Whether the machine is well.
import DEPENDENCIES from "../seeds/dependencies.json";
import DISKS from "../seeds/disks.json";
import DISKS_BLOCKED from "../seeds/disks-blocked.json";
import ERRORS from "../seeds/errors.json";
import INDEX_HEALTH from "../seeds/index-health.json";
import SCHEDULERS from "../seeds/schedulers.json";
import SERVICES from "../seeds/services.json";
import { GET, route } from "./shared";
import { mockState } from "../state";
import { heldCauses, serviceDownSince } from "./posed-block";
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

// The contract's state of a dependency that does not answer.
const OFFLINE = "offline";

/**
 * A dependency as the layer answers it: down since when it was posed down.
 *
 * @param fact The seeded dependency.
 * @returns The fact, down with its `since` when a block posed it so.
 */
function downWhenPosed(fact: Schemas["Fact"]): Schemas["Fact"] {
  const since = serviceDownSince(fact.label);
  return since === undefined ? fact : { ...fact, state: OFFLINE, since, secondaryLine: undefined };
}

// A library with no disk to receive a medium (maquette-blocked § 1.2).
const LIBRARY_FULL = "library_full";
// The state of a disk with too little room.
const NEARLY_FULL = "nearly_full";

/**
 * The disks as a posed block leaves them — the door « Voir les disques » lands on
 * a section saying the cause the card said (maquette-blocked § 1.3), a fact
 * absent at rest:
 *
 * - the STAGING disk without room (`insufficient_space`), and the volume where
 *   qBittorrent downloaded unreadable (`content_missing`), each a row of its
 *   own, from `disks-blocked.json`;
 * - a library with no disk to receive the medium (`library_full`): every
 *   library disk short of room, none saying the free space a figure would
 *   contradict.
 *
 * A derivation, shown as one: the backend reads the disks' space (BK1, BK2).
 *
 * @param disks The disks as the layer answers them at rest.
 * @returns The disks, as the blocks posed now leave them.
 */
function disksUnderBlocks(disks: Schemas["Fact"][]): Schemas["Fact"][] {
  const causes = heldCauses();
  const library = causes.has(LIBRARY_FULL)
    ? disks.map((disk) => ({ ...disk, state: NEARLY_FULL as Schemas["Fact"]["state"], secondaryLine: undefined }))
    : disks;
  const named = DISKS_BLOCKED as Record<string, Schemas["Fact"]>;
  return [...Object.keys(named).filter((cause) => causes.has(cause)).map((cause) => named[cause]), ...library];
}

// What an answer carries when the maquette genuinely has nothing to put there.
const NOTHING_TO_REPORT = "";

/** Every route this subject answers. */
export function systemRoutes(): MockRoute[] {
  return [
    route("readServices", GET, "/system/services", () => SERVICES),
    route("readDependencies", GET, "/system/dependencies", () => (DEPENDENCIES as Schemas["Fact"][]).map(downWhenPosed)),
    route("readErrors", GET, "/system/errors", () => ERRORS),
    route("readSchedulers", GET, "/maintenance/schedulers", () => SCHEDULERS),
    route("readDisks", GET, "/maintenance/disks", () => disksUnderBlocks(asPosed(DISKS))),
    route("readIndexHealth", GET, "/maintenance/index-health", () => asPosed(INDEX_HEALTH)),
    // The maquette is not a server and has no version of its own. The shape is
    // answered so a surface can be wired to it; the value is EMPTY rather than
    // invented, because a plausible-looking version string is exactly the kind
    // of made-up datum this whole lot exists to keep out. The operation's
    // `x-unseeded` in the contract says so.
    route("readVersion", GET, "/version", () => ({
      version: NOTHING_TO_REPORT,
      commit: NOTHING_TO_REPORT,
    })),
  ];
}
