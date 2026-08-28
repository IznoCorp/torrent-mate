// What a server event refreshes on the system page.
//
// SEVEN READS, ONE SURFACE, and the map keeps them apart for the reason the
// page keeps them apart: one « everything about the system » invalidation would
// make every event refetch seven resources, which is a reload under another
// name.
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

/** The services, and what each is doing. */
const SERVICES_KEY = ["/api/system/services"];
/** The schedulers, and when each next runs. */
const SCHEDULERS_KEY = ["/api/maintenance/schedulers"];
/** The disks, and what is left on them. */
const DISKS_KEY = ["/api/maintenance/disks"];
/** The index's health. */
const INDEX_HEALTH_KEY = ["/api/maintenance/index-health"];
/** What the code has been complaining about. */
const ERRORS_KEY = ["/api/system/errors"];
/** The runs, and how each ended. */
const HISTORY_KEY = ["/api/pipeline/history"];

/** What a server event refreshes on the system page. */
export const systemLiveRules: readonly LiveRule[] = [
  {
    types: ["DiskFullWarning", "ItemDispatched"],
    keys: [DISKS_KEY],
    because:
      "a warning is the disks read arriving as news, and a dispatched item is "
      + "the one routine act that consumes the space it reports",
  },
  {
    types: ["WatcherRunTriggered", "PipelineStarted", "PipelineEnded"],
    keys: [SCHEDULERS_KEY, HISTORY_KEY],
    because:
      "a run beginning or ending moves the next scheduled time AND appends to "
      + "the history — the two reads that are about runs rather than about "
      + "state",
  },
  {
    types: ["StepErrored", "TrackerAuthFailed"],
    keys: [ERRORS_KEY],
    because:
      "an error is exactly what this read answers, and a screen that has to be "
      + "reloaded to show one is §8's own example of a lie by omission",
  },
  {
    types: ["LibraryScanCompleted", "BackfillCompleted"],
    keys: [INDEX_HEALTH_KEY],
    because:
      "the index's health is what a scan and a backfill exist to change",
  },
];

/** The events that reach the system page and deliberately refresh nothing. */
export const systemLiveExemptions: LiveExemptions = {
  types: [
    "BackfillStarted",
    "BackfillItemCompleted",
    "BackfillSkipped",
    "SeasonEscalatedAfterEpisodeFailures",
    "SeasonFellBackToEpisodes",
    "VerifyItemDone",
    "StepItemStatus",
    "ItemProgressed",
    "PipelinePaused",
    "PipelineResumed",
    "StepStarted",
    "StepCompleted",
  ],
  because:
    "every one of them is per-item or per-step progress, and this page reads "
    + "state rather than progress. `BackfillItemCompleted` in particular fires "
    + "once per item of a backfill that walks the whole library — mapping it to "
    + "the index's health would refetch that read thousands of times for one "
    + "number that moves once, at the end (`BackfillCompleted`, above)",
};
