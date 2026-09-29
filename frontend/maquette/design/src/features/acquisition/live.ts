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
/** One acquisition's journey. The medium follows in the key. */
const JOURNEY_KEY = ["/api/acquisition/journeys"];
/** The address of what is sitting in staging. Its scenario is the second
    element, so THE PREFIX IS DELIBERATELY THE ADDRESS ALONE: an item moving
    changes the staging of whichever dataset is being read, and a key naming one
    scenario would leave the other stale until the process ended. */
const STAGING_KEY = ["/api/staging/media"];
/** The address of the decisions the scrape could not make alone. */
const DECISIONS_KEY = ["/api/decisions/"];

/** What a server event refreshes on acquisition. */
export const acquisitionLiveRules: readonly LiveRule[] = [
  {
    // THE JOURNEY IS THE TUNNEL (§20), and a tunnel that stops moving while the
    // pipeline moves is the thing the sheet exists to disprove. The engine's
    // producer carried its five stages as a literal, so the question of
    // freshness could not arise; reading them from the layer is what
    // raises it. Every event below advances a stage the sheet DRAWS — taken,
    // downloaded, ingested, scraped, shelved — and the key is prefixed, so one
    // rule refreshes whichever journey is open.
    // THE NAMES ARE THE BACKEND'S, and two of them were invented on the first
    // attempt — `ItemIngested` and `ItemScraped` do not exist, and the guard
    // said so: « a rule names it and the backend emits nothing by that name —
    // the rule is dead, and its surface will never refresh ». The middle stages
    // are `ItemProgressed`, which is the one event the pipeline emits per item
    // per step.
    types: ["GrabSucceeded", "DownloadCompleted", "ItemProgressed",
            "ItemDispatched"],
    keys: [JOURNEY_KEY],
    because:
      "each is a stage of the journey the sheet draws, in the order it draws "
      + "them. A tunnel that stands still while the pipeline moves is what §20 "
      + "asks the operator to be able to watch, and `staleTime: Infinity` makes "
      + "silence permanent rather than momentary",
  },
  {
    types: ["ItemProgressed"],
    keys: [FOLLOWED_KEY],
    because:
      "the rung an item reaches may be its last, « vérifié dans Plex », and a "
      + "film confirmed in the library leaves the follows by itself (ruling 3). "
      + "The engine's per-step event is what carries a rung; ending the follow "
      + "at the Plex confirmation rather than at detection is a demand owed",
  },
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
    types: ["DownloadStarted", "DownloadProgressed", "DownloadCompleted"],
    keys: [QUEUE_KEY],
    because:
      "the three boundaries of a download, and they are BOUNDED — which is the "
      + "opposite of what this file first claimed. `DownloadStarted` fires « at "
      + "most once per info-hash » (the mark is persisted before the emit); "
      + "`DownloadProgressed` fires only on 25/50/75 and « only the HIGHEST "
      + "threshold crossed per reconcile pass », never regressing. That is four "
      + "invalidations for a whole download, against the ~540 `ItemProgressed` "
      + "already sends per pipeline pass. The card draws « Téléchargement 68 % » "
      + "and a stage strip; refusing these froze that number for the life of the "
      + "tab",
  },
  {
    types: ["FilmAcquired"],
    keys: [FOLLOWED_KEY, QUEUE_KEY],
    because:
      "acquiring a film DELETES its follow row and closes its wanted row — "
      + "`detect.py` and `dispatch_reconcile.py` both do exactly that before "
      + "emitting. The event's own docstring calls itself the operator-visible "
      + "trace of a film leaving the follows, and it was claimed only by the "
      + "library and the media sheet — so the two lists it really changes went "
      + "on showing a film that had left both",
  },
  {
    types: ["SeasonEscalatedAfterEpisodeFailures", "SeasonFellBackToEpisodes",
            "SeasonAbsorbedEpisodes"],
    keys: [QUEUE_KEY],
    because:
      "all three are wanted-queue routing: a season pack replaces starved "
      + "episode rows, a season falls back to individual episodes, or episode "
      + "rows are absorbed into a season. Each rewrites what this list holds AND "
      + "the reason each card states — and the first two exist, by their own "
      + "docstrings, so that reason can be right",
  },
  {
    types: ["ItemDispatched"],
    keys: [FOLLOWED_KEY],
    because:
      "a follow shows « 95 sur 96 », and a dispatched episode is what will "
      + "move it. ⚠ NOT YET, and the sentence used to say so in the present "
      + "tense: today `ItemDispatched` is emitted per item and the ownership "
      + "counts are derived from the index, which the post-dispatch scan writes "
      + "AFTERWARDS — so at this instant the number has not moved and "
      + "`LibraryScanCompleted` is the event that carries the change. It is "
      + "kept because the maquette's contract is what the backend will follow "
      + "(D7) and a dispatched item is where this belongs; the demand is filed",
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
 * The events that reach acquisition and deliberately refresh nothing.
 *
 * `DownloadProgressed` WAS REFUSED HERE, AND THE REFUSAL WAS WRONG. It read
 * « it fires per torrent per tick », which its own docstring contradicts: only
 * the HIGHEST threshold crossed per reconcile pass fires, the persisted mark
 * only moves forward, and the thresholds are 25/50/75 — three emissions for a
 * whole download. `DownloadStarted` fires once per info-hash, exactly once. The
 * volume argument was applied to the two bounded events and not to
 * `ItemProgressed`, which fires per item per step across nine steps and IS
 * mapped. Both are rules above now.
 *
 * A progress BAR is still a different mechanism — a value pushed into the
 * component that draws it — and that remains a demand. What is not a demand is
 * a card stuck on « Téléchargement 68 % » for the life of the tab.
 *
 * `RatioMeasured` and the seed-obligation events are claimed by the « Trackers »
 * page, whose reads they move (`features/trackers/live.ts`); the cross-seed
 * events belong to a surface that has no page yet.
 */
export const acquisitionLiveExemptions: LiveExemptions = {
  types: [
    "CrossSeedInjected",
    "CrossSeedRejected",
    "TrackerAuthFailed",
  ],
  keys: ["/api/acquisition/search", "/api/acquisition/status"],
  /* a search is a QUESTION the reader just asked, not a resource that ages: refreshing it behind them would replace the results they are reading with different ones, which is the one thing a search must not do */
  /* the status carries the grab SCHEDULE, which is configuration: it changes when the operator edits it, and no backend event announces a schedule change */
  because:
    "the cross-seed events belong to a surface that has no page yet, and "
    + "claiming them here would refresh a list that does not show them. "
    + "`TrackerAuthFailed` is neither: it is a FAILURE, and it is claimed by "
    + "the system feature's errors read — named here so that « acquisition does "
    + "not refresh on it » is a decision rather than an omission, and not "
    + "because the sentence about cross-seed events describes it. The acquisition "
    + "status carries the grab schedule, which is configuration no event announces",
};
