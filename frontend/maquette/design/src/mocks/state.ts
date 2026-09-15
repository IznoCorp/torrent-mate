// What a mutation changes, and what a reset puts back.
//
// A MUTATION MUST CHANGE WHAT THE NEXT READ RETURNS, or it proves nothing:
// L09's optimistic paths and their rollbacks are written against a layer where
// following a mutation with a read shows the change. So the seeds are copied
// once into a mutable state, and the copies are what the handlers read.
//
// AND THE RESET IS WHAT KEEPS THE ORACLE POSSIBLE. A named state that mutates
// and is then measured must measure the same thing every time it is driven, so
// the layer returns to its seeded state on demand — `window.__mocks.reset()`,
// the same door the harness already goes through for the scenario.
//
// EVERY VALUE HERE COMES FROM A SEED. Nothing in this file invents one; the
// only literals are the identifiers of the seeds themselves.
import BLOCKED from "./seeds/blocked.json";
import DONE_TODAY from "./seeds/done-today.json";
import FOLLOWS from "./seeds/follows.json";
import IN_FLIGHT from "./seeds/in-flight.json";
import NOT_FOUND_LOADED from "./seeds/not-found-loaded.json";
import NOT_FOUND from "./seeds/not-found.json";
import STUCK_LOADED from "./seeds/stuck-loaded.json";
import SETTLED_LOADED from "./seeds/settled-loaded.json";
import TAKEABLE from "./seeds/takeable.json";
import PENDING_DECISIONS from "./seeds/pending-decisions.json";
import SETTLED_DECISIONS from "./seeds/settled-decisions.json";
import PIPELINE from "./seeds/pipeline.json";
import PIPELINE_RUNS from "./seeds/pipeline-runs.json";
import TMP_ORPHANS from "./seeds/tmp-orphans.json";
import LIBRARY_ITEMS from "./seeds/library-items.json";
import STUCK from "./seeds/stuck.json";
import MOVING from "./seeds/moving.json";
import SETTLED from "./seeds/settled.json";
import SETTINGS from "./seeds/settings.json";
import SECRETS from "./seeds/secrets.json";

/**
 * The configuration file that has MOVED on disk since it was read.
 *
 * A notifications file rather than a storage one on purpose: the paths are
 * what one edits first when trying the editor out, and having THAT save answer
 * « le fichier a bougé » would make the ordinary case the surprising one.
 */
const CHANGED_ON_DISK = "notify";
import { scenario } from "./scenario";
import type { components } from "../contract/types";

/** The contract's own vocabulary for what the pipeline is doing. */
export type PipelineState = components["schemas"]["PipelineState"];

// The state a pipeline is in when nothing is running. It is a token of the
// contract's enum, and the type above is what refuses a misspelling of it.
const IDLE: PipelineState = "idle";

// How many steps the run caught in flight had finished.
const STEPS_FINISHED = 5;

// The state a paused pipeline is in, for the dial that puts it there.
const PAUSED: PipelineState = "paused";

type Schemas = components["schemas"];

/**
 * What the layer holds and a mutation may change.
 *
 * TYPED BY THE CONTRACT, never by `typeof <seed>`. TypeScript infers a literal
 * type from a JSON import — `showStatus: null` for the four films — so a state
 * typed off the seeds refuses the eight shows the same field carries a string
 * on. Typing it by the contract turns that around: the compiler now checks
 * every handler against the shape the contract declares, which is what D2
 * adopted typed variants for in the first place.
 */
export type MockState = {
  follows: Schemas["Follow"][];
  /**
   * THE FOLLOWS A REMOVAL TOOK AWAY, whole, so that an undo can put one back.
   *
   * A removal used to DROP the record, which left the interface only one road
   * back — a create — and a create carries a title and a kind and nothing
   * else. So « Retirer », then « Annuler », returned a medium with no year, no
   * « suivi depuis » and no search count: a stranger wearing the same name
   * (B-353). The removal is soft here for that reason, and the record waits
   * intact until something restores it.
   *
   * IT IS HELD ASIDE RATHER THAN FLAGGED IN PLACE, so that `follows` keeps the
   * exact shape the contract declares. A tombstone field on a follow would be
   * a field every reader of the listing has to know to ignore, and one of them
   * eventually would not.
   */
  removedFollows: Schemas["Follow"][];
  pendingDecisions: Schemas["PendingDecision"][];
  settledDecisions: Schemas["SettledDecision"][];
  pipeline: Schemas["Pipeline"];
  library: Schemas["LibraryItem"][];
  /**
   * THE TITLES A DELETE REMOVED, which the listing alone could not say.
   *
   * A media sheet's ownership comes from a static seed keyed by title, so a
   * delete that filtered `library` changed the LIST and nothing else: the sheet
   * of a deleted medium went on answering « Possédés 24 » and offering
   * « Supprimer » to whoever reopened it. A layer that cannot show a mutation's
   * effect on the surface the reader is looking at cannot be used to prove that
   * surface right, which is what a repair for it was measured against.
   */
  deletedTitles: string[];
  /**
   * Whether the library database answers at all.
   *
   * The contract makes a media sheet's `ownership` nullable and says why: null
   * « when the library database is unavailable ». That is a state a backend
   * reaches on its own, so the layer answers it on demand — without it, the
   * screen's « ownership unknown » branch is unreachable and no rule can drive
   * it, which is how a null answer came to be drawn as « non ».
   */
  libraryDatabaseAvailable: boolean;
  /**
   * THE QUEUE, IN BOTH SCENARIOS, and the pairing is the engine's own.
   *
   * The prototype has always carried two worlds — a DENSE one, which is what a
   * busy morning looks like, and the REAL one recorded off the operator's own
   * run — and the harness switches between them. The engine held both and
   * derived which to answer with; the layer holds both now, because a mutation
   * has to change what the next read returns in whichever one it happened in.
   *
   * WHAT THE `Reel` LISTS ARE, and they are not a mirror of the others: under
   * the real scenario the engine starts them EMPTY and an action fills them.
   * « Nothing has moved yet » is the true state of a run that has just been
   * read off the disk, and seeding them from the dense world would have the
   * layer answer with cards no run ever produced.
   */
  stuck: Schemas["QueueCard"][];
  stuckLoaded: Schemas["QueueCard"][];
  moving: Schemas["QueueCard"][];
  movingReel: Schemas["QueueCard"][];
  settled: Schemas["QueueCard"][];
  settledLoaded: Schemas["QueueCard"][];
  takeable: Schemas["QueueCard"][];
  blocked: Schemas["QueueCard"][];
  inFlight: Schemas["QueueCard"][];
  inFlightReel: Schemas["QueueCard"][];
  notFound: Schemas["QueueCard"][];
  notFoundReal: Schemas["QueueCard"][];
  doneToday: Schemas["QueueCard"][];
  doneReel: Schemas["QueueCard"][];
  settings: Schemas["SettingsTopic"][];
  secrets: Schemas["Secret"][];
  /**
   * What the pipeline is doing. A run asked for while one is running is
   * QUEUED and visibly so — never refused (DOIT-4, NE-DOIT-PAS-3).
   *
   * NOT SEEDED, AND IT COULD NOT BE. The engine holds its `pipe` field in the
   * STORE, so it is not a fixture family at all; the tokens are the contract's
   * own `PipelineState` enum, and every operation answering with one carries
   * `x-unseeded` saying so.
   */
  pipelineState: PipelineState;
  /**
   * EVERY RUN THE HISTORY HOLDS, in full — the list and a run's detail read
   * this one array, so they cannot disagree. Seeded from a snapshot of real
   * `pipeline_run` rows; a launched veille appends to it.
   */
  pipelineRuns: Schemas["RunDetail"][];
  /**
   * Whether the automatic trigger opens runs on its own. ONE field: the
   * pipeline's status projects it and the locks project it inverted (§13).
   * Store state, not a fixture, as `pipelineState` is.
   */
  watcherEnabled: boolean;
  /** When the pipeline took its lock, or null while it is idle. */
  pipelineSince: string | null;
  /** When the pipeline was paused, or null while it is not. */
  pausedSince: string | null;
  /** When the automatic trigger was turned off, or null while it is on. */
  watcherPausedSince: string | null;
  /** How many run-ending events the running veilles have already answered. */
  runEndingsSeen: number;
  /**
   * Whether the lock file outlived the process that took it.
   *
   * A PROPERTY OF THE FILE, not of the request, so it is a dial and never a
   * scenario: no verb of this layer produces a stale lock, and the state that
   * stands for « the machine crashed holding it » has to be able to say so.
   */
  lockStale: boolean;
  /** Whether the bounded sweep for temporary entries has finished. */
  sweepFinished: boolean;
  /**
   * Whether the history read came back SHORT. The backend says so when its own
   * read failed: the list may be missing rows, and drawing it as complete is
   * the clause NE-DOIT-PAS-5 names.
   */
  historyDegraded: boolean;
  /** The temporary entries a crash left behind, as the sweep found them. */
  tmpOrphans: Schemas["TmpOrphan"][];
  /**
   * The stages of each journey the operator has opened, PER MEDIUM.
   *
   * WHY PER MEDIUM AND WHY MUTABLE. The layer answered ONE seeded list to every
   * journey ever asked for, which was enough while the sheet only displayed
   * them. It is not enough once the tunnel has verbs: « Remettre en file » and
   * « Re-scraper » are proved by the stages MOVING — a `now` pip where a `todo`
   * was — and a static answer moves for nobody. A rule reading a literal
   * instead would pass over a build that called the operation and ignored what
   * it answered, which is the shape this wave exists to refuse.
   *
   * FILLED ON FIRST READ, never at seeding: a journey is read per medium and
   * nothing knows in advance which media will be asked for.
   */
  journeyStages: Record<string, Schemas["JourneyStage"][]>;
  /**
   * When each medium's metadata was last re-read, keyed by TITLE.
   *
   * WHAT THE RE-SCRAPE MOVES (B-383). The verb « Re-scraper les métadonnées »
   * said a sentence and sent nothing; a verb is proved by the state it changes
   * and never by the message it answers, so the operation writes here and the
   * sheet's own « Métadonnées rafraîchies » row reads it back.
   *
   * EMPTY AT SEEDING, and that is the honest starting point: no medium has been
   * re-read in a session that has just begun. The sheet then shows what it
   * always showed, which is why the row keeps a fallback.
   */
  metadataRefreshedAt: Record<string, string>;
  /** Whether a configuration change is waiting for a restart. */
  restartRequired: boolean;
  /**
   * Which configuration files carry a pending edit. A write must change what
   * the next read returns, or the interface contradicts itself: save a file,
   * list the files, and nothing had changed.
   */
  changedFiles: string[];
  /**
   * Whether a file moved under an edit. NOT SEEDED and it could not be — the
   * engine holds it in its store, and the contract's operation says so in
   * `x-unseeded`.
   */
  conflict: boolean;
  /**
   * Which configuration files have MOVED on disk since they were read.
   *
   * THE DIAL ABOVE IS A PROPERTY OF THE REQUEST; this is a property of the
   * FILE, and B-345's settings half is the difference. A rule can raise the
   * dial and reach B-299's banner; a HAND has no dial, so at rest one file
   * answers `conflict: true` on its own write and the banner is reachable by
   * saving a setting that lives in it — which is what « the seeds hold at
   * least one subject in every state every surface can draw » means here.
   */
  movedFiles: string[];
  /** Whether the configuration refuses writes. Layer state, as above. */
  readOnly: boolean;
};

/**
 * Copies a seed so a mutation cannot reach the imported module.
 *
 * A JSON import is one object shared by every reader in the bundle: mutating it
 * would change what a later reset restores, which is the reset failing to be
 * one.
 *
 * @param value The seed.
 * @returns A copy nothing else holds.
 */
function copyOf<Value>(value: unknown): Value {
  return structuredClone(value) as Value;
}

// THE CAST_PORTRAITS ABOVE IS A CLAIM, AND IT IS PROVED ELSEWHERE. Each seed is asserted
// to answer the contract shape it is copied into — that is exactly what
// `scripts/check-mock-seeds.py --arm schema` validates, over all 47 of them,
// with every declared object closed to unknown properties. A cast whose proof
// runs in a gate is a different thing from a cast that asks to be believed.

const seeded = (): MockState => ({
  follows: copyOf<Schemas["Follow"][]>(FOLLOWS),
  removedFollows: [],
  pendingDecisions: copyOf<Schemas["PendingDecision"][]>(PENDING_DECISIONS),
  settledDecisions: copyOf<Schemas["SettledDecision"][]>(SETTLED_DECISIONS),
  pipeline: copyOf<Schemas["Pipeline"]>(PIPELINE),
  library: copyOf<Schemas["LibraryItem"][]>(LIBRARY_ITEMS),
  deletedTitles: [],
  libraryDatabaseAvailable: true,
  stuck: copyOf<Schemas["QueueCard"][]>(STUCK),
  stuckLoaded: copyOf<Schemas["QueueCard"][]>(STUCK_LOADED),
  moving: copyOf<Schemas["QueueCard"][]>(MOVING),
  movingReel: [],
  settled: copyOf<Schemas["QueueCard"][]>(SETTLED),
  settledLoaded: copyOf<Schemas["QueueCard"][]>(SETTLED_LOADED),
  takeable: copyOf<Schemas["QueueCard"][]>(TAKEABLE),
  blocked: copyOf<Schemas["QueueCard"][]>(BLOCKED),
  inFlight: copyOf<Schemas["QueueCard"][]>(IN_FLIGHT),
  inFlightReel: [],
  notFound: copyOf<Schemas["QueueCard"][]>(NOT_FOUND_LOADED),
  notFoundReal: copyOf<Schemas["QueueCard"][]>(NOT_FOUND),
  doneToday: copyOf<Schemas["QueueCard"][]>(DONE_TODAY),
  doneReel: [],
  settings: copyOf<Schemas["SettingsTopic"][]>(SETTINGS),
  secrets: copyOf<Schemas["Secret"][]>(SECRETS),
  pipelineState: IDLE,
  pipelineRuns: copyOf<Schemas["RunDetail"][]>(PIPELINE_RUNS),
  watcherEnabled: true,
  pipelineSince: null,
  pausedSince: null,
  watcherPausedSince: null,
  runEndingsSeen: 0,
  lockStale: false,
  sweepFinished: true,
  historyDegraded: false,
  tmpOrphans: copyOf<Schemas["TmpOrphan"][]>(TMP_ORPHANS),
  journeyStages: {},
  metadataRefreshedAt: {},
  restartRequired: false,
  changedFiles: [],
  conflict: false,
  // THE FILE A HAND CAN REACH THE CONFLICT BANNER THROUGH (B-345). One file,
  // and a notifications one rather than a storage one on purpose: the paths
  // are what an operator edits first when trying the editor out, and having
  // THAT save answer « le fichier a bougé » would make the ordinary case the
  // surprising one. Saving anything in `notify` reaches the banner; saving
  // anything else does not.
  movedFiles: [CHANGED_ON_DISK],
  readOnly: false,
});

// BUILT ON FIRST USE, never at module evaluation. A top-level `seeded()` call
// is a side effect, and a module with one cannot be dropped by the bundler even
// when nothing reads it — which left 69 kB of unreferenced seed data in the
// build that had the layer switched OFF.
let current: MockState | null = null;

/** Returns the state the handlers read and write. */
export function mockState(): MockState {
  if (current === null) current = seeded();
  return current;
}

/** Puts every seed back exactly as it was committed. */
export function resetMockState(): void {
  current = seeded();
}

/**
 * The dials a named state turns to reach a state no verb of this layer produces.
 *
 * A DIAL, NEVER A SCENARIO. A scenario says how an operation ANSWERS — its
 * status, its latency; these say what the machine IS: its lock outlived a dead
 * process, its sweep has not finished, a crash left entries behind. A named
 * state runs synchronously, so it cannot ask the layer through the network and
 * wait; it turns these instead.
 */
export type MockDials = {
  setPipelineState: (state: PipelineState) => void;
  setLockStale: (stale: boolean) => void;
  setWatcherEnabled: (enabled: boolean) => void;
  setAcquisitionQueueEmpty: (empty: boolean) => void;
  setHistoryEmpty: (empty: boolean) => void;
  setHistoryDegraded: (degraded: boolean) => void;
  setSweepFinished: (finished: boolean) => void;
  setTmpOrphans: (present: boolean) => void;
  setRunInProgress: (going: boolean) => void;
};

/** Those dials, over the layer's own state. */
export const mockDials: MockDials = {
  setPipelineState: (state: PipelineState) => {
    const held = mockState();
    held.pipelineState = state;
    held.pipelineSince = state === IDLE ? null : scenario().now;
    held.pausedSince = state === PAUSED ? scenario().now : null;
  },
  setLockStale: (stale: boolean) => {
    const held = mockState();
    held.lockStale = stale;
    if (stale) held.pipelineSince = scenario().now;
  },
  setWatcherEnabled: (enabled: boolean) => {
    const held = mockState();
    held.watcherEnabled = enabled;
    held.watcherPausedSince = enabled ? null : scenario().now;
  },
  setAcquisitionQueueEmpty: (empty: boolean) => {
    // WHAT A VEILLE THAT FINDS NOTHING LOOKS LIKE. The three figures are
    // derived from the acquisition queue, so an empty queue is the zero case —
    // and the zero case is a real answer, not an absent one.
    const held = mockState();
    held.takeable = empty ? [] : copyOf<Schemas["QueueCard"][]>(TAKEABLE);
    held.inFlight = empty ? [] : copyOf<Schemas["QueueCard"][]>(IN_FLIGHT);
  },
  setHistoryEmpty: (empty: boolean) => {
    // A FRESH INSTALL, which is a real state and not an error: nothing has run
    // yet, and the list says so rather than drawing a heading over nothing.
    mockState().pipelineRuns = empty ? [] : copyOf<Schemas["RunDetail"][]>(PIPELINE_RUNS);
  },
  setHistoryDegraded: (degraded: boolean) => {
    mockState().historyDegraded = degraded;
  },
  setSweepFinished: (finished: boolean) => {
    mockState().sweepFinished = finished;
  },
  setTmpOrphans: (present: boolean) => {
    mockState().tmpOrphans = present ? copyOf<Schemas["TmpOrphan"][]>(TMP_ORPHANS) : [];
  },
  setRunInProgress: (going: boolean) => {
    // THE SNAPSHOT HOLDS NO RUN STILL GOING: this is its first real pipeline
    // row caught after its fifth step — those five verbatim, the sixth live and
    // knowing nothing yet, the rest not in the answer, as a run in flight is.
    const runs = copyOf<Schemas["RunDetail"][]>(PIPELINE_RUNS);
    const run = runs.find((one) => one.kind === "pipeline");
    if (going && run) {
      const live = run.steps[STEPS_FINISHED];
      run.steps = [...run.steps.slice(0, STEPS_FINISHED), { name: live.name, status: "running" }];
      Object.assign(run, { outcome: "running", endedAt: null, durationS: null, outputTail: null });
    }
    mockState().pipelineRuns = runs;
  },
};
