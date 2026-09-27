// Arrivées — the pipeline
//
// The shapes this feature's reads answer, declared where the subject lives.

import type { Schemas } from "../../lib/contract-schemas";

// THE PIPELINE, as the page that carries its health reads it: the nine steps in
// the engine's own order, the trigger vocabulary said in words rather than in
// the engine's token, and the last run exactly as `pipeline_run` recorded it.
// A step's `facts` entry may carry nothing at all — that is the em dash the
// interface draws for « nothing to do », and it is not the same sentence as a
// step that looked and found everything already in order.
export type Pipeline = Schemas["Pipeline"];

export type PipelineFact = Schemas["PipelineFact"];

export type PipelineStep = Schemas["PipelineStep"];
