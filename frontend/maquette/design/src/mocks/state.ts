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
import LIBRARY_ITEMS from "./seeds/library-items.json";
import STUCK from "./seeds/stuck.json";
import MOVING from "./seeds/moving.json";
import SETTLED from "./seeds/settled.json";
import SETTINGS from "./seeds/settings.json";
import SECRETS from "./seeds/secrets.json";
import type { components } from "../contract/types";

/** The contract's own vocabulary for what the pipeline is doing. */
export type PipelineState = components["schemas"]["PipelineState"];

// The state a pipeline is in when nothing is running. It is a token of the
// contract's enum, and the type above is what refuses a misspelling of it.
const IDLE: PipelineState = "idle";

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
  pendingDecisions: Schemas["PendingDecision"][];
  settledDecisions: Schemas["SettledDecision"][];
  pipeline: Schemas["Pipeline"];
  library: Schemas["LibraryItem"][];
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
  pendingDecisions: copyOf<Schemas["PendingDecision"][]>(PENDING_DECISIONS),
  settledDecisions: copyOf<Schemas["SettledDecision"][]>(SETTLED_DECISIONS),
  pipeline: copyOf<Schemas["Pipeline"]>(PIPELINE),
  library: copyOf<Schemas["LibraryItem"][]>(LIBRARY_ITEMS),
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
  restartRequired: false,
  changedFiles: [],
  conflict: false,
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
