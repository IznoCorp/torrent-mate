// the Médiathèque — the library as a browsable list
//
// The slice of `window.__referentiel` this feature reads, and nothing else.
//
// The engine publishes ONE object; what it publishes is not one subject. A
// single 340-line declaration of all of it made every module that needed two
// members depend on all hundred and eight, and seventeen of twenty-five
// modules did. Each slice is declared where its subject lives instead, and the
// global's own type is their intersection (app/reference.d.ts) — so a
// reader imports nothing to be typed, and a member nobody's subject claims has
// nowhere to be written down.

import type { QueueCard } from "../../lib/engine-queue";

import type { EngineDrawing } from "../../lib/engine-drawing";

// A show the index knows is INCOMPLETE: owned over announced, and the year
// that tells two shows of the same name apart.
export type IncompleteShow = { t: string; o: number; a: number; y: number };

// A library CATEGORY pill: its id, its name, the count it claims, and the
// engine's own category ids it stands for (`null` for « Tout »).
export type LibraryCategory = {
  id: string;
  l: string;
  c: number;
  of: string[] | null;
};

// A library ROW as the recent list holds one: a title and the line under it.
export type LibraryRow = { t: string; f: string };

export type LibraryReference = EngineDrawing & {
  libRowHTML: (item: LibraryRow | QueueCard, index: number) => string;
  // The selection bar lives in `#device` and stays the FRAGMENT's: a component
  // asks for a repaint after it draws, exactly where `fillLib` asked for one.
  paintSelBar: () => void;
  // Every sort, in both directions, each with its own name — the table E-001
  // made two-dimensional. A rule reads the NAMES from here rather than
  // restating them.
};

/**
 * Reads this feature's slice of the engine's published reference object.
 *
 * The object is read-only reference data the engine publishes ONCE, at
 * definition time, well before any component's module evaluates — so a plain
 * accessor is the right shape, not a subscription: there is nothing here for a
 * component to miss by reading it straight.
 *
 * Returns:
 *     The slice, typed. The global's own declaration (app/reference.d.ts) is the
 *     intersection of every slice, so no cast is needed here.
 */
export function useLibraryReference(): LibraryReference {
  return window.__referentiel;
}

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
