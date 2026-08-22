// the media catalogue — what a work IS, and what we own of it
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

import type { EngineDrawing } from "../../lib/engine-drawing";

// A media sheet, exactly as `SHEETS_RAW` shapes one in refonte.html — a
// movie and a show share most fields but not all (a show carries `seasons`
// and `eps`, a movie carries `duree`), and the source stays untyped JS. A
// loose index type is the honest shape here rather than a speculative
// closed one: a component narrows the fields it actually reads.
export type MediaSheet = Record<string, unknown>;

// One YouTube trailer reference, as `trailerIds` shapes one per title.
export type Trailer = {
  key: string;
  name: string;
  language: string;
};

export type MediaReference = EngineDrawing & {
  sheetFor: (title: string) => MediaSheet | null;
  seasonsOf: (title: string) => [number, number | null, number][];
  ownedFor: (title: string, season: number) => Set<number> | null;
  EP_LABEL: Record<string, string>;
  TODAY: string;
  CAST: Record<string, string>;
  // Media-sheet data: hero banners, posters, cast portraits, trailers and
  // episode-status labels, plus the lookup/formatting helpers a sheet or a
  // season list reads them through — see refonte.html's `sheetFor` /
  // `seasonsOf` / `ownedFor` neighbourhood for the exact resolution rules
  // (title normalisation, year-suffix stripping) a re-implementation would
  // otherwise silently diverge from.
  HERO_IMAGES: Record<string, string>;
  trailerIds: Record<string, Trailer>;
  SYNOPSIS: Record<string, string>;
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
export function useMediaReference(): MediaReference {
  return window.__referentiel;
}
