// The ratio, tracker by tracker: the configured trackers as their own subject,
// the download client's entries one per tracker they run on, and the seeding
// obligations those entries owe.
import { DELETE, GET, field, route } from "./shared";
import { mockState } from "../state";
import { trackersState } from "../trackers-state";
import type { MockRoute } from "../router";
import type { components } from "../../contract/types";

type Schemas = components["schemas"];

// WHERE A TRACKER'S ALERT THRESHOLD IS SET: its own key in the tracker's
// economy block, beside the floor and the target, written through the same
// settings write as they are. The summary READS it there rather than carrying
// a second copy that could disagree with what the settings page shows.
const SETTING_PREFIX = "tracker.providers.";
const ALERT_THRESHOLD_SUFFIX = ".economy.alert_threshold";

// The milliseconds in a second: a removal is dated in Unix-epoch seconds.
const MILLISECONDS_PER_SECOND = 1000;

/**
 * The alert threshold the settings hold for one tracker.
 *
 * @param tracker The tracker's configured name.
 * @returns The threshold, or null when no setting names one.
 */
function alertThresholdOf(tracker: string): number | null {
  const key = SETTING_PREFIX + tracker + ALERT_THRESHOLD_SUFFIX;
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
      const removed = held.downloads.filter((entry) => entry.infoHash === entryHash).map((entry) => entry.infoHash);
      held.downloads = held.downloads.filter((entry) => entry.infoHash !== entryHash);
      const now = Math.floor(Date.now() / MILLISECONDS_PER_SECOND);
      for (const obligation of held.obligations) {
        if (obligation.infoHash === entryHash && obligation.releasedAt === null) obligation.releasedAt = now;
      }
      return { removed };
    }),
  ];
}
