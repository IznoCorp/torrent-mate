// What the mock layer is asked to answer, and how — failure, latency, and the
// clock.
//
// SET SYNCHRONOUSLY, IN THE PAGE, and that is the whole reason there is no
// service worker (D-L08-2). The named states this prototype is driven by
// already flip `phase: "loading" | "error"` through the store, in the same tick
// as the state is entered; a failure negotiated across a worker's message
// channel would arrive after the surface had already asked. A mock whose
// failure lands late is a mock that cannot reproduce a loading state.
//
// DETERMINISTIC, AND NEVER JITTERED. The same state driven twice waits the same
// number of milliseconds and answers the same bytes. The oracle is asked to
// depend on this layer once L09 wires a surface to it, and an oracle cannot
// depend on a number drawn at random.

/** How a scenario answers one operation. */
export type OperationOutcome = {
  /** The HTTP status to answer with. 200 unless a failure is asked for. */
  status: number;
  /** How long the answer is held back, in milliseconds. Always the same. */
  latencyMilliseconds: number;
};

/** What the whole layer is currently asked to do. */
export type Scenario = {
  /**
   * The instant the layer calls now. It is the engine's own frozen clock, and
   * they must AGREE: every date-derived state — an episode that has aired, a
   * follow's next search — moves the moment they do not. R85 holds it.
   */
  now: string;
  /** The latency every operation answers with unless it is named below. */
  defaultLatencyMilliseconds: number;
  /** Per-operation overrides, keyed by operationId. */
  operations: Record<string, Partial<OperationOutcome>>;
};

// The engine's frozen clock. It is a COPY of `TODAY` in `legacy.js`, and the
// copy is deliberate: `mocks/` imports nothing from `engine/` (D-L08-10),
// because the engine dies at L13 and a layer importing it would die with it.
// What holds the two together is R85, which reads both and refuses a
// disagreement — a copy nothing compares is exactly the drift this lot exists
// to make impossible elsewhere.
const FROZEN_CLOCK = "2026-08-10";

// No wait at all, by default. A latency is something a scenario ASKS for; a
// layer that made every answer slow would make every rule slower and would
// prove nothing about a surface nobody asked to be slow.
const NO_LATENCY = 0;

const initial = (): Scenario => ({
  now: FROZEN_CLOCK,
  defaultLatencyMilliseconds: NO_LATENCY,
  operations: {},
});

let current: Scenario = initial();

/** Returns the scenario in force. */
export function scenario(): Scenario {
  return current;
}

/**
 * Asks one operation to answer differently.
 *
 * @param operationId The operation, as the contract names it.
 * @param outcome What it should answer with.
 */
export function setOperationOutcome(
  operationId: string,
  outcome: Partial<OperationOutcome>,
): void {
  current.operations[operationId] = { ...current.operations[operationId], ...outcome };
}

/**
 * Sets the latency every operation answers with unless it says otherwise.
 *
 * @param milliseconds How long, always the same.
 */
export function setDefaultLatency(milliseconds: number): void {
  current.defaultLatencyMilliseconds = milliseconds;
}

/** Returns the layer to its starting scenario: no failure, no latency. */
export function resetScenario(): void {
  current = initial();
}

/**
 * Resolves what one operation should answer with.
 *
 * @param operationId The operation, as the contract names it.
 * @returns Its status and its latency.
 */
export function outcomeFor(operationId: string): OperationOutcome {
  const asked = current.operations[operationId] ?? {};
  return {
    status: asked.status ?? 200,
    latencyMilliseconds:
      asked.latencyMilliseconds ?? current.defaultLatencyMilliseconds,
  };
}
