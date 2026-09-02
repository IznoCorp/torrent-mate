// The fields the media screen and its parts read off a sheet, narrowed.
// The fields this screen reads off a `SHEETS_RAW` entry. The source stays
// untyped JS and a movie and a show do not carry the same keys, so every
// field is optional — a narrowed view of `MediaSheet`, never a claim about
// what a sheet always has.
export type SheetEpisode = { n: number; t: string; air?: string | null };
export type CatalogSeason = { n: number; ep: number | null; air?: string };
export type MediaSheetFields = {
  k?: string;
  y?: string;
  note?: number;
  g?: string;
  duree?: number | null;
  ov?: string;
  real?: string | null;
  crea?: string | null;
  cast?: { n: string; r?: string }[];
  ids?: Record<string, string | number>;
  status?: string;
  seasons?: CatalogSeason[];
  eps?: Record<string, SheetEpisode[]>;
  /**
   * Whether the reader holds it: true, false, or NULL for « nobody knows ». The
   * contract's own third value — `ownership` is nullable, null when the library
   * database is unavailable — and a type that admitted only two made the third
   * indistinguishable from « not owned ».
   */
  possede?: boolean | null;
};

// The slice of the simulated world this screen reads: the follow list, and
// only its titles.
export type Follow = { t: string };

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
