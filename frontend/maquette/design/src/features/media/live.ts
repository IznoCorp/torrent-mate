// What a server event refreshes on a media sheet.
//
// THE NARROWEST KEYS IN THE MAP, and the ones that prove the fan-out rule is
// doing something. A sheet is keyed per identity — `["/api/media", provider,
// identifier]` — so an event about one title must not refresh another's sheet.
// A key one element short (`["/api/media"]`) would refresh every sheet the
// cache holds: it compiles, its types agree, and only a measurement against the
// cache tells the difference.
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

/**
 * The sheets. THE PREFIX IS THE ADDRESS, and here that is a decision AGAINST
 * the narrow key rather than for it: the events below carry no identity this
 * table can read, so a rule scoped to one title could only be written by
 * guessing which. Refreshing every open sheet is the honest answer while the
 * events say nothing — and the demand for an identity on them is filed in
 * `docs/reference/frontend-backend-demands.md`, so this widening has a date of
 * death rather than being the shape forever.
 */
const SHEETS_KEY = ["/api/media"];

/** What a server event refreshes on a media sheet. */
export const mediaLiveRules: readonly LiveRule[] = [
  {
    types: ["ItemDispatched", "SeasonAbsorbedEpisodes", "FilmAcquired"],
    keys: [SHEETS_KEY],
    because:
      "each changes whether we own the title, or how much of it — which is the "
      + "half of a sheet that is about US rather than about the work (§11: a "
      + "sheet says what a media IS and where it stands here)",
  },
];

/** The events that reach a media sheet and deliberately refresh nothing. */
export const mediaLiveExemptions: LiveExemptions = {
  types: ["SeriesFollowed", "SeriesUnfollowed", "TrailerDownloaded"],
  keys: ["/api/media"],
  /* the seasons read shares its address with the sheet, so the sheet's rule covers it */
  because:
    "following is acquisition's state, not the sheet's, and it is refreshed "
    + "there. A trailer arriving changes a file on disk and nothing the sheet "
    + "reads — the day the sheet shows a trailer's presence, this line is the "
    + "one that has to change, which is why it names the event rather than "
    + "leaving it unlisted",
};
