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
  /**
   * How many calls answer normally before the status above takes effect.
   *
   * WHY IT EXISTS. « The list loaded, and then the next page did not » is a
   * real state the interface has to draw, and it cannot be asked for by a
   * status alone: an operation set to fail fails its FIRST call, so the list
   * never appears and the surface shows a whole-surface error instead of a
   * footer one. The engine drew that state from a `libFailedOnce` flag it kept
   * in the interface's own store — server state in a client store, invariant 4
   * — and this is where that flag goes.
   *
   * Zero means « from the first call », which is what a scenario that does not
   * mention it asks for.
   */
  afterCalls: number;
  /**
   * How many calls fail before the operation answers normally again.
   *
   * WHY IT IS NOT ALWAYS « every call from now on ». « The next page failed »
   * and « this resource is down » are different states, and the interface draws
   * them differently: the first offers to try again and the retry WORKS, which
   * is the whole of what a retry is for. The engine expressed the first with a
   * `libFailedOnce` flag it kept in the interface's own store; this is where
   * that flag goes.
   *
   * Absent means « every call from `afterCalls` on », which is what a scenario
   * that does not mention it asks for.
   */
  failingCalls?: number;
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

// How many times each operation has been asked for since the last reset. It is
// the counter `afterCalls` is read against, and a reset puts it back — a
// scenario that survived a reset would make a named state depend on which
// states were driven before it.
let calls: Record<string, number> = {};

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
  calls = {};
}

/**
 * Resolves what one operation should answer with.
 *
 * @param operationId The operation, as the contract names it.
 * @returns Its status and its latency.
 */
export function outcomeFor(operationId: string): OperationOutcome {
  const asked = current.operations[operationId] ?? {};
  const seen = calls[operationId] ?? 0;
  calls[operationId] = seen + 1;
  const afterCalls = asked.afterCalls ?? 0;
  // THE COUNT IS TAKEN BEFORE THE ANSWER, so « fail after one call » means the
  // second call is the one that fails — the call that has one before it.
  const failingCalls = asked.failingCalls;
  const armed =
    seen >= afterCalls
    && (failingCalls === undefined || seen < afterCalls + failingCalls);
  return {
    status: armed ? (asked.status ?? 200) : 200,
    latencyMilliseconds:
      asked.latencyMilliseconds ?? current.defaultLatencyMilliseconds,
    afterCalls,
    ...(failingCalls === undefined ? {} : { failingCalls }),
  };
}
