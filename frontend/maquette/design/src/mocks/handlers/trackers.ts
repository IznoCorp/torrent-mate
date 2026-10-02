// The ratio, tracker by tracker: the configured trackers as their own subject,
// the download client's entries one per tracker they run on, and the seeding
// obligations those entries owe.
import { DELETE, GET, POST, field, route } from "./shared";
import { mockState } from "../state";
import { alertThresholdKey, enabledKey, trackersState } from "../trackers-state";
import { crossSeedOfEntry, crossSeedOrigin, crossSeedState, trackerCrossSeed } from "../cross-seed-state";
import { refused, type MockRoute } from "../router";
import { previewOf } from "./ranking";
import type { components } from "../../contract/types";

type Schemas = components["schemas"];

// Why « Vu » is refused: the tracker holds no broken obligation on that torrent.
const NO_BROKEN_OBLIGATION = "no broken obligation of that tracker is owed on that torrent";

// The milliseconds in a second: a removal is dated in Unix-epoch seconds.
const MILLISECONDS_PER_SECOND = 1000;

/**
 * The alert threshold the settings hold for one tracker.
 *
 * @param tracker The tracker's configured name.
 * @returns The threshold, or null when no setting names one.
 */
function alertThresholdOf(tracker: string): number | null {
  // READ WHERE THE SETTINGS WRITE PUTS IT, rather than from a second copy
  // that could disagree with what the settings page shows.
  const key = alertThresholdKey(tracker);
  const setting = mockState()
    .settings.flatMap((topic) => topic.settings)
    .find((candidate) => candidate.key === key);
  return typeof setting?.raw === "number" ? setting.raw : null;
}

/**
 * Whether the settings hold one tracker switched on.
 *
 * @param tracker The tracker's configured name.
 * @returns The setting's value, or true when no setting names the tracker.
 */
function enabledOf(tracker: string): boolean {
  // READ WHERE THE SETTINGS WRITE PUTS IT: the roster's switch and Réglages
  // write the same key, so the two cannot disagree.
  const key = enabledKey(tracker);
  const setting = mockState()
    .settings.flatMap((topic) => topic.settings)
    .find((candidate) => candidate.key === key);
  return typeof setting?.raw === "boolean" ? setting.raw : true;
}

/**
 * Why a tracker is off: its failure when one holds, the operator's choice otherwise.
 *
 * @param tracker The tracker as the layer holds it.
 * @param enabled Whether its setting is on.
 * @returns Null while it is on.
 */
function disabledOf(tracker: Omit<Schemas["Tracker"], "crossSeed">, enabled: boolean): Schemas["Tracker"]["disabled"] {
  if (enabled) return null;
  if (tracker.disabled?.by === "failure") return tracker.disabled;
  return { by: "operator", reason: null, message: null, since: null };
}

/**
 * The refusal a write switching trackers on earns: the first of them whose failure persists.
 *
 * @param values The write, keyed `<file>:<key>`.
 * @returns The engine's words, or null when the write may land.
 */
export function activationRefusal(values: Record<string, unknown>): string | null {
  for (const tracker of trackersState().trackers) {
    const asked = values[`tracker:${enabledKey(tracker.name)}`];
    if (asked === true && tracker.disabled?.by === "failure") return tracker.disabled.message ?? "";
  }
  return null;
}

/** Every route this subject answers. */
export function trackerRoutes(): MockRoute[] {
  return [
    route("readTrackers", GET, "/api/trackers", (): Schemas["Tracker"][] =>
      trackersState().trackers.map((tracker) => {
        const enabled = enabledOf(tracker.name);
        return {
          ...tracker, alertThreshold: alertThresholdOf(tracker.name), enabled, disabled: disabledOf(tracker, enabled),
          // THE CROSS-SEED'S COUNTS DERIVED FROM THE SAME PAIRS the downloads read answers, its torrents still in the client.
          crossSeed: trackerCrossSeed(tracker.name, trackersState().downloads),
        };
      }),
    ),
    route("markBrokenObligationSeen", POST, "/api/trackers/{tracker}/broken-obligations/{infoHash}/seen", (request) => {
      // SEEN IS NOT GONE: the row stays on its tracker, and leaves the alert's count.
      const tracker = trackersState().trackers.find((one) => one.name === request.parameters.tracker);
      const broken = tracker?.brokenObligations.find((row) => row.infoHash === request.parameters.infoHash);
      if (broken === undefined) return refused(404, NO_BROKEN_OBLIGATION);
      broken.seen = true;
      return broken;
    }),
    // THE RANKING EDITOR'S LIVE PREVIEW: read-only and pure, the fixed sample set
    // scored under the ranking the request carries.
    route("previewRanking", POST, "/api/acquisition/ranking/preview",
          (request) => previewOf(request.body as Schemas["RankingConfig"])),
    route("readDownloads", GET, "/api/acquisition/downloads", (): Schemas["Downloads"] => ({
      clientAvailable: true,
      // THE MARK'S PAIRS FOLDED INTO THE SAME ANSWER (R-L17-k): no second read for them.
      downloads: trackersState().downloads.map((entry) => ({ ...entry, crossSeed: crossSeedOfEntry(entry) })),
      crossSeedQuota: crossSeedState().quota,
    })),
    route("readObligations", GET, "/api/acquisition/obligations", (): Schemas["Obligations"] => ({
      // AN OBLIGATION A CROSS-SEED CREATED says whose copy it is (§ 19 point 2).
      items: trackersState().obligations.map((obligation) => ({
        ...obligation, crossSeedOf: crossSeedOrigin(obligation, trackersState().downloads),
      })),
    })),
    route("removeDownload", DELETE, "/api/acquisition/downloads/{infoHash}", (request) => {
      // THE ENTRY LEAVES THE CLIENT, and a running obligation it owed is CLOSED
      // at that moment — released, never left reading in breach.
      const held = trackersState();
      const entryHash = request.parameters.infoHash;
      held.removals.push({ infoHash: entryHash, deleteFiles: field(request.body, "deleteFiles") === true });
      // EVERY ENTRY SHARING ITS FILES LEAVES WITH IT, in the same answer — a
      // cross-seed of the same content is the same files under another entry.
      const files = new Set(held.downloads.filter((entry) => entry.infoHash === entryHash).map((entry) => entry.name));
      const leaving = new Set(held.downloads.filter((entry) => files.has(entry.name)).map((entry) => entry.infoHash));
      const removed = [...leaving];
      held.downloads = held.downloads.filter((entry) => !leaving.has(entry.infoHash));
      const now = Math.floor(Date.now() / MILLISECONDS_PER_SECOND);
      for (const obligation of held.obligations) {
        // RELEASED HERE: the in-app message says the torrent left by this gesture.
        if (leaving.has(obligation.infoHash) && obligation.releasedAt === null) {
          Object.assign(obligation, { releasedAt: now, releasedBy: "removedHere" });
        }
      }
      return { removed };
    }),
  ];
}
