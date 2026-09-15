// the Médiathèque — the library as a browsable list
//
// The shapes this feature's reads answer, declared where the subject lives.

import type { Schemas } from "../../lib/contract-schemas";

// A show the index knows is INCOMPLETE: owned over announced, and the year
// that tells two shows of the same name apart.
export type IncompleteShow = Schemas["IncompleteShow"];

// A library CATEGORY pill: its id, its name, the count it claims, and the
// engine's own category ids it stands for (`null` for « Tout »).
export type LibraryCategory = Schemas["LibraryCategory"];

// A library ROW as the recent list holds one: a title and the line under it.
export type LibraryRow = Schemas["LibraryItem"];

// THE WINDOW'S GEOMETRY (P24), MEASURED on the served prototype at 390x844
// rather than read off a stylesheet: tiles 203.34px and cards 126px, both
// uniform across every rendered item.
//
// The two heights the first measurement showed in the gallery were SKELETONS
// (`.sk.tile`, 171px), which `[data-part="tile"]` selects as well as the real
// tile — a virtualiser configured from that reading would have run in
// variable-height mode for a spread no rendered list ever contains. The gaps
// are the scale's own steps: `--spacing-5` for the gallery, `--spacing-4` for
// the list.
//
// THE TILE'S HEIGHT IS WRITTEN TO THE PIXEL IT MEASURES, 203.34375 and not
// 203.34, and the three thousandths matter. The spacers derive the container's
// height from this number, so a truncation accumulates once per line — eight
// lines put the gallery 0.28px short, which the oracle read as eight
// divergences of 0.1px. A measurement rounded for a comment is a measurement
// wrong for arithmetic.
export const LIBRARY_WINDOW = {
  gallery: { rowHeight: 203.34375, gap: 10, lanes: 3 },
  list: { rowHeight: 126, gap: 8, lanes: 1 },
} as const;
