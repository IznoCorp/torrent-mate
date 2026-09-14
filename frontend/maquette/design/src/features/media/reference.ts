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

// A media sheet, exactly as the served read shapes one in the engine's names — a
// movie and a show share most fields but not all (a show carries `seasons`
// and `eps`, a movie carries `duree`), and the source stays untyped JS. A
// loose index type is the honest shape here rather than a speculative
// closed one: a component narrows the fields it actually reads.
export type MediaSheet = Record<string, unknown>;

// One YouTube trailer reference, as a sheet's `trailerVideo` carries it.
export type Trailer = {
  key: string;
  name: string;
  language: string;
};

export type MediaReference = EngineDrawing & {
  EP_LABEL: Record<string, string>;
  TODAY: string;
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
