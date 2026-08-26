// What has arrived and not yet settled, and the run that moves it.
import PIPELINE_EXECUTIONS from "../seeds/pipeline-executions.json";
import MOVING from "../seeds/moving.json";
import SETTLED_LOADED from "../seeds/settled-loaded.json";
import STUCK_LOADED from "../seeds/stuck-loaded.json";
import { GET, POST, route } from "./shared";
import { mockState } from "../state";
import type { MockRequest, MockRoute } from "../router";
import type { components } from "../contract-types";

type PipelineState = components["schemas"]["PipelineState"];

// The contract's own vocabulary for what the pipeline is doing. The engine
// holds this in its STORE and not in a fixture, which is why every operation
// answering with one of these carries `x-unseeded` in the contract.
const RUNNING: PipelineState = "running";
const QUEUED: PipelineState = "queued";
const PAUSED: PipelineState = "paused";
const IDLE: PipelineState = "idle";

// The dense body of data, asked for by name. The engine has always carried two
// and the prototype's own harness switches between them.
const LOADED = "loaded";

/** Every route this subject answers. */
export function stagingRoutes(): MockRoute[] {
  return [
    route("readStaging", GET, "/api/staging/media", (request: MockRequest) => {
      const state = mockState();
      if (request.query.get("scenario") === LOADED) {
        return { stuck: STUCK_LOADED, moving: MOVING, settled: SETTLED_LOADED };
      }
      return { stuck: state.stuck, moving: state.moving, settled: state.settled };
    }),
    route(
      "continueStagedMedia",
      POST,
      "/api/staging/media/{mediaId}/continue",
      (request) => {
        const state = mockState();
        const found = state.stuck.find(
          (card) => card.title === request.parameters.mediaId,
        );
        if (found !== undefined) {
          state.stuck = state.stuck.filter((card) => card !== found);
          state.moving = [found, ...state.moving];
        }
        return { ok: found !== undefined };
      },
    ),
    route(
      "discardStagedMedia",
      POST,
      "/api/staging/media/{mediaId}/discard",
      (request) => {
        const state = mockState();
        const before = state.stuck.length;
        state.stuck = state.stuck.filter(
          (card) => card.title !== request.parameters.mediaId,
        );
        return { ok: state.stuck.length !== before };
      },
    ),
    route("readPipeline", GET, "/api/pipeline/status", () => mockState().pipeline),
    // A run asked for during a run is QUEUED and visibly so — never refused,
    // and never demoted back to running by the next tap, which is what a
    // toggle did. Each verb states the transition it makes rather than
    // flipping between two values.
    route("runPipeline", POST, "/api/pipeline/run", () => {
      const state = mockState();
      state.pipelineState = state.pipelineState === IDLE ? RUNNING : QUEUED;
      return { state: state.pipelineState, uid: null };
    }),
    route("pausePipeline", POST, "/api/pipeline/pause", () => {
      const state = mockState();
      if (state.pipelineState === RUNNING) state.pipelineState = PAUSED;
      return { state: state.pipelineState };
    }),
    route("resumePipeline", POST, "/api/pipeline/resume", () => {
      const state = mockState();
      if (state.pipelineState === PAUSED) state.pipelineState = RUNNING;
      return { state: state.pipelineState };
    }),
    route("killPipeline", POST, "/api/pipeline/kill", () => {
      const state = mockState();
      state.pipelineState = IDLE;
      return { state: state.pipelineState };
    }),
    route("readPipelineHistory", GET, "/api/pipeline/history", () => PIPELINE_EXECUTIONS),
  ];
}
