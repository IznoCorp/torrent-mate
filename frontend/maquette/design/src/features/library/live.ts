// What a server event refreshes on the library.
//
// The map is domain knowledge and lives with the domain (invariant 10,
// D-L10-1). `app/live-updates.ts` names this feature and nothing more.
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

/** The listing. Its query, category, sort and reversal follow in the key. */
const ITEMS_KEY = ["/api/library/items"];
/** The categories, with their counts. */
const CATEGORIES_KEY = ["/api/library/categories"];
/** What is owned but incomplete. */
const INCOMPLETE_KEY = ["/api/library/incomplete"];

/** What a server event refreshes on the library. */
export const libraryLiveRules: readonly LiveRule[] = [
  {
    types: ["ItemDispatched", "LibraryScanCompleted"],
    keys: [ITEMS_KEY, CATEGORIES_KEY, INCOMPLETE_KEY],
    because:
      "a dispatched item and a finished scan both change WHAT IS OWNED, which "
      + "is the one thing all three reads are about: the listing gains a row, a "
      + "category's count moves, and a season that was missing may not be any "
      + "more",
  },
  {
    types: ["FilmAcquired", "SeasonAbsorbedEpisodes"],
    keys: [INCOMPLETE_KEY],
    because:
      "completeness changed and nothing else did — the item was already in the "
      + "listing and already in its category. A rule that also refreshed those "
      + "two would be a wider invalidation for no reason, which is precisely "
      + "what this lot's « and nothing else » refuses",
  },
];

/**
 * The events that reach the library and deliberately refresh nothing.
 *
 * THE LISTING'S KEY IS DELIBERATELY THE ADDRESS ALONE, so every query,
 * category, sort and reversal refreshes together. A listing is a VIEW over one
 * set: a row added under one sort is added under all of them, and a key naming
 * the current view would leave every other one stale for the life of the
 * process (B-154).
 */
export const libraryLiveExemptions: LiveExemptions = {
  types: [
    "DownloadStarted",
    "DownloadProgressed",
    "DownloadCompleted",
    "GrabSucceeded",
    "GrabFailed",
  ],
  keys: [],
  /* every address this feature reads is refreshed by a rule above */
  because:
    "acquisition is not possession. A download that started, progressed or even "
    + "completed has changed nothing about what is in the library — the item "
    + "arrives here only when the pipeline dispatches it, which is "
    + "`ItemDispatched` above",
};
