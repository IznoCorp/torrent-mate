// Arrivées — the pipeline, and the folders it could not name
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

// One TVDB/TMDB candidate offered for a decision still awaiting arbitration,
// exactly as `PENDING_DECISIONS[].c` shapes one. `sans` marks a candidate
// with no poster at the provider (the placeholder is what says so on the
// card, never a truncating sentence); `resume` is the synopsis shown there.
export type DecisionCandidate = {
  t: string;
  y: number;
  p: string;
  id: number;
  s: number;
  sans?: boolean;
  resume?: string;
};

// The choice recorded once a decision resolves — the winning candidate's
// identity plus how it was reached: picked from the offered list, or found
// through a manual search override that bypassed that list. `via` keys
// `VIA_LABEL`.
export type DecisionChoice = {
  t: string;
  p: string;
  id: number;
  via: "pick" | "search_override";
};

// Fields common to a decision whichever side of resolution it is on — the
// folder's display name (`d`, always spelled `staging_path`-derived, never a
// medium title), its kind, the title/year the automatic pass landed on, and
// when the scrape ran. `reason` keys `REASON_LABEL` / `REASON_TONE` /
// `REASON_DETAIL`.
type DecisionCommon = {
  d: string;
  k: "movie" | "show";
  t: string;
  y?: number;
  reason: string;
  when: string;
};

// A folder still waiting on an operator's call, exactly as `PENDING_DECISIONS`
// shapes one. `c` is empty when the provider returned no candidate at all
// (see refonte.html's "Backrooms" row) — the other shape besides a populated
// list, never absent outright.
export type PendingDecision = DecisionCommon & { c: DecisionCandidate[] };

export type Pipeline = {
  steps: PipelineStep[];
  declencheurs: Record<string, string>;
  last: {
    uid: string;
    when: string;
    duree: string;
    declencheur: string;
    issue: string;
    facts: PipelineFact[];
  };
};

export type PipelineFact = {
  n: string;
  r?: string;
  s?: string;
  blockedCount?: number;
};

// THE PIPELINE, as the page that carries its health reads it: the nine steps in
// the engine's own order, the trigger vocabulary said in words rather than in
// the engine's token, and the last run exactly as `pipeline_run` recorded it.
// A step's `facts` entry may carry nothing at all — that is the em dash the
// interface draws for « nothing to do », and it is not the same sentence as a
// step that looked and found everything already in order.
export type PipelineStep = { n: string; l: string; d: string };

// A decision already settled, exactly as `DECISIONS_REGLEES` shapes one.
// `state` keys `DECISION_STATE` / `DECISION_STATE_DETAIL`. `choice` is present
// only for a "resolved" row — a "superseded" or "dismissed" row never
// recorded one, because no candidate was ever chosen.
export type SettledDecision = DecisionCommon & {
  state: string;
  choice?: DecisionChoice;
};

export type ArrivalsReference = EngineDrawing & EngineQueue & {
  REASON_LABEL: Record<string, string>;
  REASON_TONE: Record<string, string>;
  REASON_DETAIL: Record<string, string>;
  // Unlike the other label maps here, each value is a [tone, label] pair —
  // the same shape a chip carries — not a bare string: `DECISION_STATE`
  // supplies both the chip's tone and its text in one lookup.
  DECISION_STATE: Record<string, [string, string]>;
  DECISION_STATE_DETAIL: Record<string, string>;
  VIA_LABEL: Record<string, string>;
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
export function useArrivalsReference(): ArrivalsReference {
  return window.__referentiel;
}
