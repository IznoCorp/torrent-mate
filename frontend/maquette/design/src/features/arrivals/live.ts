// What a server event refreshes on Arrivées.
//
// THE MAP IS DOMAIN KNOWLEDGE, so it lives with the domain (invariant 10, and
// D-L10-1). `app/live-updates.ts` names this feature and hands the table to the
// relay; it does not name an event or a key, and a central map that did would
// be the one production has — forty event names and twenty keys in a file
// belonging to no domain at all.
//
// A KEY IS A PREFIX, AND ITS WIDTH IS A DECISION. One element too short covers
// siblings nobody listed: it compiles, its types agree, and nothing but a
// measurement against the cache tells the difference. R91 is that measurement,
// and it holds both directions — too wide and missing.
//
// EVERY EVENT NAME IS THE BACKEND'S OWN CLASS NAME, spelled as
// `event_to_envelope` writes it. They are not this file's to invent: an event
// this map names and the server never emits refreshes nothing, silently, and
// `check-live-relay.py --arm map-completeness` is what refuses one.
import type { LiveRule } from "../../lib/live-rule";

/** The address of the pipeline's own status. */
const PIPELINE_KEY = ["/api/pipeline/status"];
/** The address of what is sitting in staging. Its scenario is the second
    element, so THE PREFIX IS DELIBERATELY THE ADDRESS ALONE: an item moving
    changes the staging of whichever dataset is being read, and a key naming one
    scenario would leave the other stale until the process ended. */
const STAGING_KEY = ["/api/staging/media"];
/** The address of the decisions the scrape could not make alone. */
const DECISIONS_KEY = ["/api/decisions/"];

/** What a server event refreshes on Arrivées. */
export const arrivalsLiveRules: readonly LiveRule[] = [
  {
    types: [
      "PipelineStarted",
      "PipelineEnded",
      "PipelinePaused",
      "PipelineResumed",
      "StepStarted",
      "StepCompleted",
      "StepErrored",
    ],
    keys: [PIPELINE_KEY],
    because:
      "the run's lifecycle and every step boundary are what the status IS — a "
      + "step that started and a screen that still says the previous one is the "
      + "§8 defect this lot exists to end",
  },
  {
    types: ["ItemProgressed", "StepItemStatus"],
    keys: [STAGING_KEY],
    because:
      "an item advancing moves it between stuck, moving and settled, which is "
      + "the whole of what this read answers",
  },
  {
    types: ["PipelineEnded"],
    keys: [STAGING_KEY, DECISIONS_KEY],
    because:
      "a run that ended has settled everything it was going to settle, and may "
      + "have queued decisions it could not make alone. It is a SECOND rule on "
      + "the same event rather than a longer type list on the first: what it "
      + "refreshes is different, and the reason it refreshes them is different",
  },
  {
    types: ["ItemDispatched"],
    keys: [STAGING_KEY],
    because:
      "a dispatched item has LEFT staging, so the list it was in is one shorter",
  },
];

/**
 * The events that reach Arrivées and deliberately refresh nothing.
 *
 * WRITTEN DOWN RATHER THAN OMITTED. An event nobody handles is not an error; an
 * event nobody can COUNT is how a map silently stops covering its subject.
 */
export const arrivalsLiveExemptions = {
  types: ["DiskFullWarning", "WatcherRunTriggered", "LibraryScanCompleted"],
  because:
    "none of the three changes what this feature reads. A disk warning and a "
    + "watcher trigger belong to the system feature, and a library scan to the "
    + "library one — each is claimed by its own table, and naming them here "
    + "would make two features answer for one event",
} as const;
