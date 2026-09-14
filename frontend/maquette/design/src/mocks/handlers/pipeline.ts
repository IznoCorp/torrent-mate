// The pipeline: its levers, its runs, and the locks that hold it.
//
// A SUBJECT OF ITS OWN, and staging is not it. What has arrived and not yet
// settled is one question; what the machine is doing about all of it at once —
// running, paused, triggered automatically or not, holding its lock — is
// another, and these routes lived under the first one's name.
//
// ONE FIELD PER FACT, AND EVERY READ A PROJECTION OF IT (§13). The automatic
// trigger is answered by the pipeline's status as `watcherEnabled` AND by the
// locks as `sentinels.watcherPaused`; the pause is answered by the pipeline's
// state AND by the locks' `pause` sentinel. The layer holds one field for each
// and both reads derive from it, so the two can never disagree — two fields
// that could is the defect, not something an interface should reconcile.
import EXECUTIONS from "../seeds/pipeline-executions.json";
import PIPELINE_RUNS from "../seeds/pipeline-runs.json";
import { GET, POST, field, route } from "./shared";
import { mockState } from "../state";
import { scenario } from "../scenario";
import { refused, type MockRequest, type MockRoute } from "../router";
import type { components } from "../../contract/types";

type Schemas = components["schemas"];
type PipelineState = Schemas["PipelineState"];
type RunDetail = Schemas["RunDetail"];
type RunSummary = Schemas["RunSummary"];
type StepCounts = Schemas["StepCounts"];
type StepTiming = Schemas["StepTiming"];

// The contract's own vocabulary for what the pipeline is doing.
const RUNNING: PipelineState = "running";
const QUEUED: PipelineState = "queued";
const PAUSED: PipelineState = "paused";
const IDLE: PipelineState = "idle";

// How a run ended, or that it has not.
const SUCCEEDED: Schemas["RunOutcome"] = "success";
const STILL_RUNNING: Schemas["RunOutcome"] = "running";

// The two states of the bounded sweep.
const SWEEP_PENDING: Schemas["TmpOrphanSweep"]["status"] = "pending";
const SWEEP_READY: Schemas["TmpOrphanSweep"]["status"] = "ready";

// The history's defaults, which are the backend's own: every kind, newest
// first, fifty at a time.
const EVERY_KIND = "all";
const OLDEST_FIRST = "started_at";
const DEFAULT_PAGE_SIZE = 50;

// THE RUN « Lancer la veille maintenant » LAUNCHES, as the backend records it:
// a maintenance run of the detection command, triggered from the interface.
const DETECTION_TRIGGER = "web";
const DETECTION_KIND = "maintenance";
const DETECTION_COMMAND = "follow-detect";
const DETECTION_RUN_PREFIX = "detection-";

// HOW LONG A DETECTION RUNS, on the layer's own clock: the run is read once
// while it is still going, and ends on the next read. The clock is a count of
// reads rather than of milliseconds because the layer is never jittered — the
// same state driven twice has to see the same thing — and a run that ended
// before anyone could read it would make « en cours » a state nobody reaches.
const READS_WHILE_DETECTING = 1;

const MILLISECONDS_PER_SECOND = 1000;

// Why a run nobody holds is refused, in the problem body's own words.
const UNKNOWN_RUN = "no run carries that identifier";

// WHICH RUN EACH FIXTURE LINE BELONGS TO. The snapshot's first rows are the six
// runs `EXECUTIONS` was read from, in its order — matched on their dates and
// durations when the snapshot was taken — so a history row can carry the line
// the list still draws until it composes one from the counts.
const CARRIED_LINES = new Map(
  PIPELINE_RUNS.slice(0, EXECUTIONS.length).map((run, index) => [run.runUid, EXECUTIONS[index]]),
);

/**
 * How long ago something happened, on the layer's frozen clock.
 *
 * @param since When it happened, or null when it has not.
 * @returns The age in seconds, or null.
 */
function ageSince(since: string | null): number | null {
  if (since === null) return null;
  return (Date.parse(scenario().now) - Date.parse(since)) / MILLISECONDS_PER_SECOND;
}

/**
 * One step reduced to what a list row needs: its name, its status, its counts.
 *
 * @param step The step in full.
 * @returns The step without its times and its reasons.
 */
function countsOf(step: StepTiming): StepCounts {
  const { startedAt: _started, endedAt: _ended, elapsedS: _elapsed, reasons: _reasons, ...counts } =
    step;
  return counts;
}

/**
 * One run as the history lists it.
 *
 * @param run The run in full.
 * @returns Its summary, with the fixture's line when the run has one.
 */
function summaryOf(run: RunDetail): RunSummary {
  const { error: _error, optionsJson: _options, outputTail: _output, steps, ...summary } = run;
  return { ...summary, steps: steps.map(countsOf), ...CARRIED_LINES.get(run.runUid) };
}

/**
 * Ends a detection run once it has been read while running.
 *
 * The figures are the acquisition queue's, which is where the three numbers
 * DOIT-6 requires have always been derived from in this layer.
 *
 * @param state The layer's state.
 * @param run The run being read.
 */
function advanceDetection(state: ReturnType<typeof mockState>, run: RunDetail): void {
  if (run.outcome !== STILL_RUNNING || !run.runUid.startsWith(DETECTION_RUN_PREFIX)) return;
  const reads = state.runReads[run.runUid] ?? 0;
  state.runReads[run.runUid] = reads + 1;
  if (reads < READS_WHILE_DETECTING) return;
  run.outcome = SUCCEEDED;
  run.endedAt = run.startedAt;
  run.durationS = ageSince(run.startedAt);
  run.steps = [{
    name: DETECTION_COMMAND,
    status: SUCCEEDED,
    counts: {
      detected: state.takeable.length + state.inFlight.length,
      available: state.takeable.length,
      grabbed: state.inFlight.length,
    },
  }];
}

/**
 * Launches the veille: appends a detection run to the history, still running.
 *
 * @returns The run's identifier, which is what the 202 names.
 */
export function launchDetection(): { runUid: string } {
  const state = mockState();
  const runUid = DETECTION_RUN_PREFIX + String(state.pipelineRuns.length);
  state.pipelineRuns = [
    {
      runUid,
      trigger: DETECTION_TRIGGER,
      dryRun: false,
      startedAt: scenario().now,
      endedAt: null,
      outcome: STILL_RUNNING,
      durationS: null,
      kind: DETECTION_KIND,
      command: DETECTION_COMMAND,
      steps: [],
      error: null,
      optionsJson: null,
      outputTail: null,
    },
    ...state.pipelineRuns,
  ];
  return { runUid };
}

/** Every route this subject answers. */
export function pipelineRoutes(): MockRoute[] {
  return [
    route("readPipeline", GET, "/api/pipeline/status", () => {
      const state = mockState();
      return {
        ...state.pipeline,
        state: state.pipelineState,
        watcherEnabled: state.watcherEnabled,
      };
    }),
    // A run asked for during a run is QUEUED and visibly so — never refused,
    // and never demoted back to running by the next tap, which is what a
    // toggle did. Each verb states the transition it makes rather than
    // flipping between two values.
    route("runPipeline", POST, "/api/pipeline/run", () => {
      const state = mockState();
      if (state.pipelineState === IDLE) state.pipelineSince = scenario().now;
      state.pipelineState = state.pipelineState === IDLE ? RUNNING : QUEUED;
      return { state: state.pipelineState, uid: null };
    }),
    route("pausePipeline", POST, "/api/pipeline/pause", () => {
      const state = mockState();
      if (state.pipelineState === RUNNING) {
        state.pipelineState = PAUSED;
        state.pausedSince = scenario().now;
      }
      return { state: state.pipelineState };
    }),
    route("resumePipeline", POST, "/api/pipeline/resume", () => {
      const state = mockState();
      if (state.pipelineState === PAUSED) {
        state.pipelineState = RUNNING;
        state.pausedSince = null;
      }
      return { state: state.pipelineState };
    }),
    route("killPipeline", POST, "/api/pipeline/kill", () => {
      const state = mockState();
      state.pipelineState = IDLE;
      state.pipelineSince = null;
      state.pausedSince = null;
      return { state: state.pipelineState };
    }),
    route("setWatcher", POST, "/api/pipeline/watcher", (request) => {
      const state = mockState();
      const enabled = field(request.body, "enabled") === true;
      if (enabled !== state.watcherEnabled) {
        state.watcherPausedSince = enabled ? null : scenario().now;
      }
      state.watcherEnabled = enabled;
      return { watcherEnabled: state.watcherEnabled };
    }),
    route("readPipelineHistory", GET, "/api/pipeline/history", (request: MockRequest) => {
      const state = mockState();
      const kind = request.query.get("kind") ?? EVERY_KIND;
      const limit = Number(request.query.get("limit") ?? DEFAULT_PAGE_SIZE);
      const offset = Number(request.query.get("offset") ?? 0);
      state.pipelineRuns.forEach((run) => advanceDetection(state, run));
      const matching = state.pipelineRuns.filter(
        (run) => kind === EVERY_KIND || run.kind === kind,
      );
      const ordered = [...matching].sort(
        (left, right) => Date.parse(right.startedAt) - Date.parse(left.startedAt),
      );
      if (request.query.get("sort") === OLDEST_FIRST) ordered.reverse();
      return {
        runs: ordered.slice(offset, offset + limit).map(summaryOf),
        total: matching.length,
        degraded: state.historyDegraded,
      };
    }),
    // AN UNKNOWN RUN IS REFUSED, as the backend refuses it: a 404 is the
    // answer « nobody holds that passage » has, and the run's own screen draws
    // it with a way back rather than an empty passage.
    route("readRun", GET, "/api/pipeline/history/{runUid}", (request) => {
      const state = mockState();
      const run = state.pipelineRuns.find((one) => one.runUid === request.parameters.runUid);
      if (run === undefined) return refused(404, UNKNOWN_RUN);
      advanceDetection(state, run);
      return run;
    }),
    route("readLocks", GET, "/api/maintenance/locks", () => {
      const state = mockState();
      // A STALE LOCK IS STILL A HELD ONE. The file is there; what is gone is
      // the process that wrote it, which is the whole difference between « the
      // pipeline is working » and « nothing is running and nothing can start ».
      const held = state.pipelineState !== IDLE || state.lockStale;
      return {
        pipelineLock: {
          held,
          ageS: held ? ageSince(state.pipelineSince) : null,
          stale: state.lockStale,
          pid: null,
        },
        sentinels: {
          pause: state.pipelineState === PAUSED,
          pauseAgeS: ageSince(state.pausedSince),
          watcherPaused: !state.watcherEnabled,
          watcherPausedAgeS: ageSince(state.watcherPausedSince),
        },
        // THE ENTRIES ARE NOT AN ANSWER UNTIL THE SWEEP HAS FINISHED (§13):
        // an unfinished sweep answers `pending` and NO list, because « none
        // found so far » and « none » are different facts.
        sweep: state.sweepFinished
          ? { status: SWEEP_READY, ageS: ageSince(scenario().now), orphans: state.tmpOrphans }
          : { status: SWEEP_PENDING, ageS: null, orphans: [] },
      };
    }),
  ];
}
