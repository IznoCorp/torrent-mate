// What a server event refreshes on acquisition.
//
// THE FEATURE THE BACKEND TALKS TO MOST, and the one where « no polling
// remains » has to be thought about rather than applied. Most of its events are
// state changes; one of them is a TICK.
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

/** What is proposed. */
const SUGGESTIONS_KEY = ["/api/acquisition/suggestions"];
/** What is followed. */
const FOLLOWED_KEY = ["/api/acquisition/followed"];
/** What is waiting to be handled. Its scenario follows in the key. */
const QUEUE_KEY = ["/api/acquisition/to-handle"];

/** What a server event refreshes on acquisition. */
export const acquisitionLiveRules: readonly LiveRule[] = [
  {
    types: ["WantedEnqueued", "WantedAbandoned", "GrabSucceeded", "GrabFailed",
            "GrabReswitched"],
    keys: [QUEUE_KEY],
    because:
      "each is a change of what is waiting: something joined the queue, left "
      + "it, was taken, failed to be taken, or was swapped for another release",
  },
  {
    types: ["SeriesFollowed", "SeriesUnfollowed"],
    keys: [FOLLOWED_KEY, SUGGESTIONS_KEY],
    because:
      "following a series removes it from what is proposed and adds it to what "
      + "is followed — one event, two lists, and a rule naming only the first "
      + "would leave a followed series still being suggested",
  },
  {
    types: ["DownloadCompleted"],
    keys: [QUEUE_KEY],
    because:
      "a finished download is the moment an item stops being « en cours » — "
      + "the boundary a reader is actually waiting for",
  },
];

/**
 * The events that reach acquisition and deliberately refresh nothing.
 *
 * `DownloadProgressed` IS THE DECISION OF THIS PHASE, and it is a refusal.
 * It fires per torrent per tick. Mapping it to the queue would invalidate that
 * list continuously — **a poll wearing an event's clothes**, and the third
 * clause of this lot's contract (« no polling remains where an event exists »)
 * read backwards: a `setInterval` any grep can find would at least be visible.
 * A progress BAR is a real want and it is a different mechanism: a value pushed
 * into the component that draws it, never a list refetched from the top. It is
 * filed as a demand rather than solved here.
 *
 * `RatioMeasured` and the seed-obligation events are the same shape, one order
 * of magnitude slower: they belong to a ratio surface that has no page yet
 * (B-144), and claiming them here would put them on a list that does not show
 * them.
 */
export const acquisitionLiveExemptions: LiveExemptions = {
  types: [
    "DownloadStarted",
    "DownloadProgressed",
    "RatioMeasured",
    "SeedObligationRecorded",
    "SeedObligationSatisfied",
    "SeedObligationBreached",
    "CrossSeedInjected",
    "CrossSeedRejected",
    "TrackerAuthFailed",
  ],
  because:
    "a per-tick event mapped to a list is a poll wearing an event's clothes; "
    + "the ratio and cross-seed events belong to surfaces that have no page "
    + "yet, and claiming them here would refresh a list that does not show them",
};
