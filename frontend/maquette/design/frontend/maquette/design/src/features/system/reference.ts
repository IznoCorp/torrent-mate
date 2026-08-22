// Système — the machine's own health
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

import type { Fact } from "../../lib/engine-drawing";

import type { EngineDrawing } from "../../lib/engine-drawing";

// The code-error summary the Système page draws as two rows.
export type CodeErrors = {
  total: number | string;
  outOf: number | string;
  latest: string;
  what: string;
  where: string;
};

// One pipeline run, as `EXECUTIONS` shapes it: the question it answered, its
// verdict, its date and its result line.
export type PipelineRun = {
  q: string;
  ok: boolean;
  d: string;
  r: string;
};

export type SystemReference = EngineDrawing & {
  SERVICES: Fact[];
  SERVICES_PANNE: Fact[];
  SCHEDULERS: Fact[];
  SCHEDULERS_DOWN: Fact[];
  EXECUTIONS: PipelineRun[];
  DISKS: Fact[];
  INDEX: Fact[];
  DEPENDENCIES: Fact[];
  ERRORS: CodeErrors;
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
export function useSystemReference(): SystemReference {
  return window.__referentiel;
}
