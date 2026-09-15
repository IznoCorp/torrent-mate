// acquisitions — what is followed, and how it is chased
//
// The shapes this feature's reads answer, declared where the subject lives.

// A FOLLOW, as the world holds one: a title, its kind, its year, the status the
// acquisition engine last put it in, and — for a series — whether the show is
// still running. `fresh` is what pushes a newly-added follow to the top.
export type Follow = {
  t: string;
  k: string;
  y: number | string;
  st: string;
  serie?: string;
  fresh?: boolean;
  since?: string;
  searches?: number;
  poster?: string | null;
  /** The provider identifiers. A follow always has them (B-366). */
  ids?: Record<string, number | string> | null;
  /** A series' episodes aired, when its catalogue is known. */
  aired?: number | null;
  /** A series' episodes held. */
  own?: number;
};

// A search hit, exactly as the mock `SEARCH` constant shapes one. `k` is the
// French kind label used throughout the legacy templates ("Film" / "Série"),
// not the English "movie"/"show" token `cardHTML` itself expects for a
// poster's aspect ratio — the two are deliberately different vocabularies at
// two different seams, and a migrated screen converts between them exactly
// where `openAddScreen` used to.
export type SearchResult = {
  t: string;
  y: string;
  k: "Film" | "Série"; // french-ok: a data VALUE — the label is read from fr.json at the render
  ov: string;
  owned: boolean;
  followed: boolean;
  poster?: string | null;
  /** The provider identifiers — null for a title no sheet stands behind. */
  ids?: Record<string, number | string> | null;
};

export type SearchResults = {
  total: number;
  shown: number;
  results: SearchResult[];
};
