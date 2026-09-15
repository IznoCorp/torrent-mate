// Maintenance — the commands run against the library
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

import type { EngineDrawing, Fact } from "../../lib/engine-drawing";

// The deletion journal: how many destructive operations the library has been
// through, and the rows describing them.
export type DeletionJournal = { total: number; lignes: Fact[] };

// One maintenance COMMAND. `g` is its rubric, `r` its risk (a key of `RISQUES`),
// `long` whether it can take a while, `blanc` whether it can run dry.
export type MaintenanceAction = {
  id: string;
  l: string;
  d: string;
  g: string;
  r: string;
  long?: boolean;
  blanc?: boolean;
};

export type MaintenanceReference = EngineDrawing;

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
export function useMaintenanceReference(): MaintenanceReference {
  return window.__referentiel;
}
