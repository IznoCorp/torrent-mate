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
import { DETECTION_MILLISECONDS, scenario } from "../scenario";
import { emit } from "../stream";
import { log } from "../stream-server";
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

// WHAT ENDS A DETECTION RUN: the event the backend sends when a run ends. The
// layer sends it itself once the run has lasted its time, and a named state
// that wants the figures at once sends it sooner. A read never ends a run —
// reading a run is not a reason for it to be over.
const RUN_ENDED = "PipelineEnded";

const MILLISECONDS_PER_SECOND = 1000;

// Why a run nobody holds is refused, in the problem body's own words.
const UNKNOWN_RUN = "no run carries that identifier";

// Why a second pass is refused, in the problem body's own words.
const RUN_ALREADY_GOING = "a pipeline pass is already going";

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
  // A RUN STARTED BY HAND IS DATED AFTER THE HISTORY (see `afterTheLastRun`),
  // which is after the frozen clock: on a clock that does not move it has just
  // begun, never a negative age.
  return Math.max(0, (Date.parse(scenario().now) - Date.parse(since)) / MILLISECONDS_PER_SECOND);
}

/**
 * The instant a run started by hand is dated: when the last run ended.
 *
 * The layer's clock is frozen before the seeded history, so a run dated by it
 * would be drawn before, and sorted under, passages it followed. The seed
 * carries no period, but every run carries its own end: the new run begins
 * where the last one stopped — its `endedAt`, or its start plus a detection's
 * length while it is still going — and so lands at the top of the list.
 *
 * @param state The layer's state.
 * @returns The instant, as the history writes one.
 */
function afterTheLastRun(state: ReturnType<typeof mockState>): string {
  const finished = state.pipelineRuns.map((run) =>
    run.endedAt !== null && run.endedAt !== undefined
      ? Date.parse(run.endedAt)
      : Date.parse(run.startedAt) + DETECTION_MILLISECONDS);
  if (finished.length === 0) return scenario().now;
  return new Date(Math.max(...finished)).toISOString();
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
 * Ends every detection run in flight once a run-ending event nobody answered has been sent.
 *
 * COUNTED, NOT POSITIONED. A named state asks for a veille and sends the event
 * in the same breath, and the launch may reach the layer after the event does;
 * an event is therefore answered by whatever runs are in flight when it is
 * first noticed, and never twice.
 *
 * @param state The layer's state.
 */
function advanceEveryDetection(state: ReturnType<typeof mockState>): void {
  const endedCount = log.entries.filter((entry) => entry.type === RUN_ENDED).length;
  if (endedCount <= state.runEndingsSeen) return;
  state.runEndingsSeen = endedCount;
  state.pipelineRuns
    .filter((run) => run.outcome === STILL_RUNNING && run.runUid.startsWith(DETECTION_RUN_PREFIX))
    .forEach((run) => endDetection(state, run));
}

/**
 * Ends one detection run.
 *
 * The figures are the acquisition queue's, which is where the three numbers
 * DOIT-6 requires have always been derived from in this layer.
 *
 * @param state The layer's state.
 * @param run The run to end.
 */
function endDetection(state: ReturnType<typeof mockState>, run: RunDetail): void {
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
 * The maintenance run holding the pipeline's lock, when one is in flight.
 *
 * @param state The layer's state.
 * @returns The run, or undefined.
 */
function maintenanceInFlight(state: ReturnType<typeof mockState>): RunDetail | undefined {
  advanceEveryDetection(state);
  return state.pipelineRuns.find(
    (run) => run.kind === DETECTION_KIND && run.outcome === STILL_RUNNING,
  );
}

/**
 * Launches the veille: appends a detection run to the history, still running.
 *
 * The run lasts its time on a real clock and then the layer sends the event
 * that ends it — unless the layer was reset meanwhile, in which case the timer
 * belongs to a state nobody is looking at any more and does nothing.
 *
 * @returns The run's identifier, which is what the 202 names.
 */
export function launchDetection(): { runUid: string } {
  const state = mockState();
  advanceEveryDetection(state);
  const runUid = DETECTION_RUN_PREFIX + String(state.pipelineRuns.length);
  state.pipelineRuns = [
    {
      runUid,
      trigger: DETECTION_TRIGGER,
      dryRun: false,
      startedAt: afterTheLastRun(state),
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
  setTimeout(() => {
    if (mockState() === state) emit(RUN_ENDED, {});
  }, DETECTION_MILLISECONDS);
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
    // THE BACKEND'S OWN ANSWER. A second pipeline pass asked while one is
    // going is the same action on the same target already under way — the
    // strict duplicate the interface may refuse — so it is answered 409. A pass
    // WAITS only behind a maintenance run holding the lock, and says so. Each
    // verb states the transition it makes rather than flipping between values.
    route("runPipeline", POST, "/api/pipeline/run", () => {
      const state = mockState();
      if (state.pipelineState !== IDLE) return refused(409, RUN_ALREADY_GOING);
      state.pipelineState = maintenanceInFlight(state) === undefined ? RUNNING : QUEUED;
      state.pipelineSince = scenario().now;
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
      advanceEveryDetection(state);
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
      advanceEveryDetection(state);
      return run;
    }),
    route("readLocks", GET, "/api/maintenance/locks", () => {
      const state = mockState();
      // A STALE LOCK IS STILL A HELD ONE. The file is there; what is gone is
      // the process that wrote it, which is the whole difference between « the
      // pipeline is working » and « nothing is running and nothing can start ».
      // A MAINTENANCE RUN HOLDS IT TOO: the lock is the pipeline's, and a
      // maintenance command takes it for its whole run.
      const maintenance = maintenanceInFlight(state);
      const held = state.pipelineState !== IDLE || state.lockStale || maintenance !== undefined;
      return {
        pipelineLock: {
          held,
          ageS: held ? ageSince(state.pipelineSince ?? maintenance?.startedAt ?? null) : null,
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
