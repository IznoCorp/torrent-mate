// Arrivées — the pipeline, and the folders it could not name
//
// The shapes this feature's reads answer, declared where the subject lives.

import type { components } from "../../contract/types";

type Schemas = components["schemas"];

// One TVDB/TMDB candidate offered for a decision still awaiting arbitration.
// `withoutPoster` marks a candidate with no poster at the provider (the
// placeholder is what says so on the card, never a truncating sentence);
// `overview` is the synopsis shown there.
export type DecisionCandidate = Schemas["DecisionCandidate"];

// The choice recorded once a decision resolves — the winning candidate's
// identity plus how it was reached (`via`): picked from the offered list, or
// found through a manual search override that bypassed that list.
export type DecisionChoice = Schemas["DecisionChoice"];

// A folder still waiting on an operator's call. `candidates` is empty when the
// provider returned no candidate at all — the other shape besides a populated
// list, never absent outright. `folder` is the staging folder's display name,
// never a medium title; `reason` keys the reason vocabulary.
export type PendingDecision = Schemas["PendingDecision"];

// THE PIPELINE, as the page that carries its health reads it: the nine steps in
// the engine's own order, the trigger vocabulary said in words rather than in
// the engine's token, and the last run exactly as `pipeline_run` recorded it.
// A step's `facts` entry may carry nothing at all — that is the em dash the
// interface draws for « nothing to do », and it is not the same sentence as a
// step that looked and found everything already in order.
export type Pipeline = Schemas["Pipeline"];

export type PipelineFact = Schemas["PipelineFact"];

export type PipelineStep = Schemas["PipelineStep"];

// A decision already settled. `state` keys the settled-state vocabulary.
// `choice` is present only for a resolved row — a superseded or dismissed row
// never recorded one, because no candidate was ever chosen.
export type SettledDecision = Schemas["SettledDecision"];
