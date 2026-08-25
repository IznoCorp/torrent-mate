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
import FOLLOWS from "./seeds/FOLLOWS.json";
import PENDING_DECISIONS from "./seeds/PENDING_DECISIONS.json";
import DECISIONS_REGLEES from "./seeds/DECISIONS_REGLEES.json";
import PIPELINE from "./seeds/PIPELINE.json";
import LIBRARY from "./seeds/LIBRARY.json";
import STUCK_REAL from "./seeds/STUCK_REAL.json";
import MOVING from "./seeds/MOVING.json";
import SETTLED_REAL from "./seeds/SETTLED_REAL.json";
import SETTINGS from "./seeds/SETTINGS.json";
import SECRETS from "./seeds/SECRETS.json";
import type { components } from "./contract-types";

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
  stuck: Schemas["QueueCard"][];
  moving: Schemas["QueueCard"][];
  settled: Schemas["QueueCard"][];
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

// THE CAST ABOVE IS A CLAIM, AND IT IS PROVED ELSEWHERE. Each seed is asserted
// to answer the contract shape it is copied into — that is exactly what
// `scripts/check-mock-seeds.py --arm schema` validates, over all 47 of them,
// with every declared object closed to unknown properties. A cast whose proof
// runs in a gate is a different thing from a cast that asks to be believed.

const seeded = (): MockState => ({
  follows: copyOf<Schemas["Follow"][]>(FOLLOWS),
  pendingDecisions: copyOf<Schemas["PendingDecision"][]>(PENDING_DECISIONS),
  settledDecisions: copyOf<Schemas["SettledDecision"][]>(DECISIONS_REGLEES),
  pipeline: copyOf<Schemas["Pipeline"]>(PIPELINE),
  library: copyOf<Schemas["LibraryItem"][]>(LIBRARY),
  stuck: copyOf<Schemas["QueueCard"][]>(STUCK_REAL),
  moving: copyOf<Schemas["QueueCard"][]>(MOVING),
  settled: copyOf<Schemas["QueueCard"][]>(SETTLED_REAL),
  settings: copyOf<Schemas["SettingsTopic"][]>(SETTINGS),
  secrets: copyOf<Schemas["Secret"][]>(SECRETS),
  pipelineState: IDLE,
  restartRequired: false,
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
