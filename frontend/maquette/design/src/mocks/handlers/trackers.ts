// The ratio, tracker by tracker: the configured trackers as their own subject,
// the download client's entries one per tracker they run on, and the seeding
// obligations those entries owe.
import { GET, route } from "./shared";
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
  ];
}
