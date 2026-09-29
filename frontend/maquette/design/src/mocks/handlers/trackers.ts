// The ratio, tracker by tracker: the configured trackers as their own subject,
// the download client's entries one per tracker they run on, and the seeding
// obligations those entries owe.
import { DELETE, GET, field, route } from "./shared";
import { mockState } from "../state";
import { alertThresholdKey, trackersState } from "../trackers-state";
import type { MockRoute } from "../router";
import type { components } from "../../contract/types";

type Schemas = components["schemas"];

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

/** Every route this subject answers. */
export function trackerRoutes(): MockRoute[] {
  return [
    route("readTrackers", GET, "/api/trackers", (): Schemas["Tracker"][] =>
      trackersState().trackers.map((tracker) => ({
        ...tracker,
        alertThreshold: alertThresholdOf(tracker.name),
      })),
    ),
    route("readDownloads", GET, "/api/acquisition/downloads", (): Schemas["Downloads"] => ({
      clientAvailable: true,
      downloads: trackersState().downloads,
    })),
    route("readObligations", GET, "/api/acquisition/obligations", (): Schemas["Obligations"] => ({
      items: trackersState().obligations,
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
        if (leaving.has(obligation.infoHash) && obligation.releasedAt === null) obligation.releasedAt = now;
      }
      return { removed };
    }),
  ];
}
