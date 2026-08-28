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
 * The sheets. THE PREFIX IS THE ADDRESS, and the reason first written here was
 * WRONG: it said the events carry no identity this table can read.
 * `FilmAcquired` carries `media_ref: MediaRef` — `tvdb_id | tmdb_id | imdb_id`,
 * encoded as a nested object by `event_to_dict` — so a narrow key IS
 * constructible for it today. `ItemDispatched` genuinely carries only a source
 * folder name, and it is the one event that justifies the widening.
 *
 * IT IS KEPT WIDE FOR NOW, and that is a stated cost rather than a discovery:
 * the two events share one rule, and splitting them so `FilmAcquired` keys on
 * its `media_ref` is a change to what this lot MEASURES, not to what it
 * refuses. The demand register is corrected to ask for an identity on
 * `ItemDispatched` alone.
 */
const SHEETS_KEY = ["/api/media"];

/** What a server event refreshes on a media sheet. */
export const mediaLiveRules: readonly LiveRule[] = [
  {
    types: ["ItemDispatched", "FilmAcquired"],
    keys: [SHEETS_KEY],
    because:
      "both change whether we own the title — the half of a sheet that is about "
      + "US rather than about the work (§11). `SeasonAbsorbedEpisodes` was here "
      + "too and does not belong: it absorbs WANTED rows and downloads nothing, "
      + "so a sheet's owned counts do not move",
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
