// Arrivées — the pipeline, and the folders it could not name
//
// The shapes this feature's reads answer, declared where the subject lives.

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
  // The candidate's own picture, never one found under its title without the year.
  poster: string | null;
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
  poster: string | null;
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
// (see refonte.html@60530dbd8's "Backrooms" row) — the other shape besides a populated
// list, never absent outright.
export type PendingDecision = DecisionCommon & { c: DecisionCandidate[] };

export type Pipeline = {
  /** What the pipeline is doing right now, as the status read answers it. */
  state?: "idle" | "running" | "queued" | "paused" | "stopping";
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
