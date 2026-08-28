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
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

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
    types: ["ItemProgressed"],
    keys: [STAGING_KEY],
    // THE STATUSES THAT MOVE AN ITEM BETWEEN THE THREE LISTS, and not the ones
    // that merely report it is still going. `started` fires in all nine steps
    // and changes which list nothing.
    when: (data) => data.status !== "started",
    sample: { status: "moved" },
    because:
      "an item advancing moves it between stuck, moving and settled, which is "
      + "the whole of what this read answers — but only when it really moves: "
      + "the vocabulary also carries a per-step « started » that changes no "
      + "list, and firing on it turned this rule into a refetch per round trip "
      + "for the length of a run",
  },
  {
    types: ["ItemProgressed"],
    keys: [DECISIONS_KEY],
    // ONE STATUS OUT OF THE VOCABULARY. `ItemProgressed` carries a
    // `StepItemStatus`, and exactly one of its values queues a decision. The
    // rule was written without this and fired on all of them — for a
    // sixty-item run, some five hundred and forty invalidations of a list that
    // changes at the scrape step alone.
    when: (data) => data.status === "queued_for_decision",
    sample: { status: "queued_for_decision" },
    because:
      "a decision is QUEUED at the scrape step, fourth of nine, and dispatch is "
      + "~50 minutes of a 57-minute run. Refreshed only at `PipelineEnded`, the "
      + "screen showed zero decisions for the whole time acting on them would "
      + "have helped — silent on the one surface this lot opens with",
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
export const arrivalsLiveExemptions: LiveExemptions = {
  types: ["DiskFullWarning", "WatcherRunTriggered", "LibraryScanCompleted"],
  keys: [],
  /* every address this feature reads is refreshed by a rule above */
  because:
    "none of the three changes what this feature reads. A disk warning and a "
    + "watcher trigger belong to the system feature, and a library scan to the "
    + "library one — each is claimed by its own table, and naming them here "
    + "would make two features answer for one event",
};
