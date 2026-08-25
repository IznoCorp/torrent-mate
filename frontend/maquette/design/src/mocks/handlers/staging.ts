// What has arrived and not yet settled, and the run that moves it.
import EXECUTIONS from "../seeds/EXECUTIONS.json";
import { GET, POST, route } from "./shared";
import { mockState } from "../state";
import type { MockRoute } from "../router";

// The contract's own vocabulary for what the pipeline is doing. The engine
// holds this in its STORE and not in a fixture, which is why every operation
// answering with one of these carries `x-unseeded` in the contract.
const RUNNING = "running";
const QUEUED = "queued";
const PAUSED = "paused";
const IDLE = "idle";

/** Every route this subject answers. */
export function stagingRoutes(): MockRoute[] {
  return [
    route("readStaging", GET, "/api/staging/media", () => {
      const state = mockState();
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
        return { ok: true };
      },
    ),
    route(
      "discardStagedMedia",
      POST,
      "/api/staging/media/{mediaId}/discard",
      (request) => {
        const state = mockState();
        state.stuck = state.stuck.filter(
          (card) => card.title !== request.parameters.mediaId,
        );
        return { ok: true };
      },
    ),
    route("readPipeline", GET, "/api/pipeline/status", () => mockState().pipeline),
    route("runPipeline", POST, "/api/pipeline/run", () => {
      const state = mockState();
      // DOIT-4 and NE-DOIT-PAS-3: a run asked for during a run is QUEUED and
      // visibly so. It is never refused, and there is no 409 here.
      state.pipelineState = state.pipelineState === RUNNING ? QUEUED : RUNNING;
      return { state: state.pipelineState, uid: state.pipeline.last.uid };
    }),
    route("pausePipeline", POST, "/api/pipeline/pause", () => {
      const state = mockState();
      state.pipelineState = PAUSED;
      return { state: state.pipelineState };
    }),
    route("resumePipeline", POST, "/api/pipeline/resume", () => {
      const state = mockState();
      state.pipelineState = RUNNING;
      return { state: state.pipelineState };
    }),
    route("killPipeline", POST, "/api/pipeline/kill", () => {
      const state = mockState();
      state.pipelineState = IDLE;
      return { state: state.pipelineState };
    }),
    route("readPipelineHistory", GET, "/api/pipeline/history", () => EXECUTIONS),
  ];
}
