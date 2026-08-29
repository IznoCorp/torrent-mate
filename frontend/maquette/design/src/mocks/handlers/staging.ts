// What has arrived and not yet settled, and the run that moves it.
import PIPELINE_EXECUTIONS from "../seeds/pipeline-executions.json";
import { GET, POST, route, text } from "./shared";
import { mockState } from "../state";
import type { MockRequest, MockRoute } from "../router";
import type { components } from "../../contract/types";

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

// What « continue » was asked to mean. Agreeing with the MACHINE keeps the
// automatic result and re-scrapes nothing; agreeing with a CANDIDATE puts the
// folder back through the pipeline under the name that was picked.
const ACCEPTED_AS_FOUND = "left";

// What the card says once it has moved. These are the engine's own words,
// carried verbatim (D-L08-5) — a layer that invented them would be inventing
// interface copy, and one that decomposed them would forfeit the proof that the
// card renders what it rendered. The demand register asks the backend for the
// FACT behind them.
const LEFT_LABEL = "Laissé tel quel";       // french-ok: a carried fixture value

// THE STRIP'S FOURTH STEP, which is where a folder stands once it has been
// answered: the first three are done and this one is running. « now » is the
// engine's own token for it, carried like every other value on a card.
const RUNNING_NOW = "now";

// The two tones a settled card wears. Neutral for a result that was accepted as
// it stood, informative for one that went back through the pipeline.
const NEUTRAL = "neutral";
const INFORMATIVE = "info";

// Which of the two staging worlds a card came from and goes to. Named because
// the pairing is the decision, not the spelling.
const FROM_REAL = "stuck";
const TO_REAL = "movingReel";
const FROM_DENSE = "stuckLoaded";
const TO_DENSE = "moving";
const FROM_BLOCKED = "blocked";
const SCRAPING_LABEL = "Scraping";          // french-ok: a carried fixture value

/** Every route this subject answers. */
export function stagingRoutes(): MockRoute[] {
  return [
    route("readStaging", GET, "/api/staging/media", (request: MockRequest) => {
      const state = mockState();
      // THE SCENARIO PICKS THE WORLD, and the pairing is the engine's own
      // `derived`. Under the DENSE one the queue is what a busy morning looks
      // like; under the REAL one it is what the operator's own run recorded —
      // and what has MOVED starts empty there, because nothing has moved yet.
      // Answering the dense lists under the real scenario would put cards on
      // screen that no run produced.
      if (request.query.get("scenario") === LOADED) {
        return {
          stuck: state.stuckLoaded,
          moving: state.moving,
          settled: state.settledLoaded,
        };
      }
      return { stuck: state.stuck, moving: state.movingReel, settled: state.settled };
    }),
    route(
      "continueStagedMedia",
      POST,
      "/api/staging/media/{mediaId}/continue",
      (request) => {
        const state = mockState();
        // FROM WHEREVER IT IS QUEUED, and the list it leaves decides the list
        // it joins. The engine's `leaveQueue` walked the real stuck list, the
        // dense one and the blocked one in that order; a card released from the
        // real world moves within the real world, and one released from the
        // dense world moves within it. Mixing them put a card in a queue no
        // scenario would ever show it in.
        const asked = request.parameters.mediaId;
        const lists = [
          { from: FROM_REAL, to: TO_REAL },
          { from: FROM_DENSE, to: TO_DENSE },
          { from: FROM_BLOCKED, to: TO_DENSE },
        ] as const;
        for (const { from, to } of lists) {
          const found = state[from].find((card) => card.title === asked);
          if (found === undefined) continue;
          state[from] = state[from].filter((card) => card !== found);
          // WHAT THE CARD SAYS AFTERWARDS is the engine's own: agreeing with a
          // candidate puts it back in the pipeline and says « Scraping »;
          // agreeing with the machine keeps the automatic result and says it
          // was left as it stood. The strip is the same in both — the folder
          // has passed the first three steps and is at the fourth.
          const settled = text(request.body, "outcome") === ACCEPTED_AS_FOUND;
          const named = text(request.body, "choice");
          state[to] = [
            {
              ...found,
              title: named === "" ? found.title : named,
              strip: [1, 1, 1, RUNNING_NOW, 0],
              chip: settled
                ? { tone: NEUTRAL, text: LEFT_LABEL }
                : { tone: INFORMATIVE, text: SCRAPING_LABEL },
            },
            ...state[to],
          ];
          return { ok: true };
        }
        return { ok: false };
      },
    ),
    route(
      "discardStagedMedia",
      POST,
      "/api/staging/media/{mediaId}/discard",
      (request) => {
        // THE SAME THREE LISTS ITS SIBLING WALKS. This filtered `stuck` alone,
        // so a card served from the DENSE world — or from « ça bloque » — was
        // asked to be discarded, nothing was removed, `{ok: false}` came back
        // and the card stayed on screen. The list a card is IN is a fact about
        // the scenario in force, never about the operation being asked for.
        const state = mockState();
        const asked = request.parameters.mediaId;
        for (const list of [FROM_REAL, FROM_DENSE, FROM_BLOCKED] as const) {
          const before = state[list].length;
          state[list] = state[list].filter((card) => card.title !== asked);
          if (state[list].length !== before) return { ok: true };
        }
        return { ok: false };
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
