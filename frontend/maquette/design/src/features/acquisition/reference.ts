// acquisitions — what is followed, and how it is chased
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
import type { EngineQueue } from "../../lib/engine-queue";

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

export type AcquisitionReference = EngineDrawing & EngineQueue & {
  // The suggestion machinery. It stays the FRAGMENT's — the deck's gesture
  // mutates its own DOM and a replaced node cannot animate — and a migrated
  // page asks it to fill the containers React has just drawn.
  addVerb: (result: SearchResult, index: number) => string;
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
export function useAcquisitionReference(): AcquisitionReference {
  return window.__referentiel;
}
