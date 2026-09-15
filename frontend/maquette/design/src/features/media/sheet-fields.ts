// The fields the media screen and its parts read off a sheet, narrowed.
// The fields this screen reads off a sheet, in the contract's names. A placeholder
// carries only what the tap knew and a movie and a show do not carry the same keys, so every
// field is optional — a narrowed view of `MediaSheet`, never a claim about
// what a sheet always has.
import type { Schemas } from "../../lib/contract-schemas";

export type SheetEpisode = { number: number; title: string; airDate?: string | null };
export type CatalogSeason = Schemas["SeasonSummary"];
export type MediaSheetFields = {
  kind?: string;
  year?: string;
  rating?: number | null;
  genres?: string | null;
  runtime?: number | null;
  overview?: string | null;
  director?: string | null;
  creator?: string | null;
  cast?: { name: string; role?: string }[];
  ids?: Record<string, string | number>;
  status?: string;
  seasons?: CatalogSeason[];
  episodes?: Record<string, SheetEpisode[]>;
  /**
   * When the metadata was last re-read from the providers, or null.
   *
   * NULL IS THE ORDINARY ANSWER, not an absence to paper over: nothing has been
   * re-read in a session that has just begun, and the « Métadonnées rafraîchies »
   * row says what it always said until a re-scrape moves it (B-383).
   */
  metadataRefreshedAt?: string | null;
  /**
   * Whether the reader holds it: true, false, or NULL for « nobody knows ». The
   * contract's own third value — `ownership` is nullable, null when the library
   * database is unavailable — and a type that admitted only two made the third
   * indistinguishable from « not owned ».
   */
  owned?: boolean | null;
};

// The slice of the simulated world this screen reads: the follow list, and
// only its titles.
export type Follow = { title: string };

// One row of the season list: an owned-seasons row (`[n, aired, own]` from
// `seasonsOf`) and a catalogue row (`{ n, ep, air }` from the sheet) are
// folded into the same shape before rendering, exactly as `sheetSeasonsHTML`
// folds them.
export type SeasonRow = {
  n: number;
  aired: number | null;
  own: number;
  air?: string;
};
