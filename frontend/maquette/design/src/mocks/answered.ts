// WHAT THIS LAYER ANSWERED, in order — the record a rule reads a CALL from.
//
// WHY IT EXISTS AT ALL, and it is not a convenience. The mock layer replaces
// `globalThis.fetch`, so a mocked call reaches no network: measured, a verb
// that demonstrably ran — a follow moving from `pending` to `acquiring` —
// produced ZERO of the browser's own request events. Every hold written as
// `page.on("request")` or `page.on("response")` over one of these operations is
// therefore green whatever the interface does, which is a guard certifying
// precisely what it cannot see.
//
// The alternative a rule falls back on is reading the SCREEN, and that is the
// defect this record exists to make unnecessary: a build that draws the right
// thing and sends nothing passes a screen-reading hold, which is what
// « Récupérer maintenant » did for a whole wave under a green gate.
//
// A FILE OF ITS OWN because `mocks/index.ts` sits at the 400-line ceiling, and
// a file at the ceiling is never extended (invariant 6). The cut is on a
// SUBJECT — what was asked of this layer, as opposed to how it answers — which
// is the cut this repository has now taken three times.

/** One call this layer answered, as a rule reads it back. */
export type AnsweredCall = {
  /** The operation, as the contract names it. */
  operationId: string;
  /** The method, upper case. */
  method: string;
  /** The path asked for, with its parameters resolved. */
  path: string;
  /** The status the layer answered with. */
  status: number;
};

const answered: AnsweredCall[] = [];

/**
 * Records one call the layer answered.
 *
 * Args:
 *     call: What was asked for, and what it was answered with.
 */
export function recordAnswered(call: AnsweredCall): void {
  answered.push(call);
}

/**
 * Every call the layer has answered, in order.
 *
 * COPIES ARE HANDED OUT, so a reader cannot edit the record it is reading —
 * a rule that mutated this list would change what the next hold measures.
 *
 * Returns:
 *     The calls, oldest first.
 */
export function answeredCalls(): AnsweredCall[] {
  return answered.map((call) => ({ ...call }));
}

/**
 * Forgets every call.
 *
 * Called by the layer's own `reset()`, like every other piece of its state: a
 * record that survived a reset would let one measurement inherit the calls of
 * the one before it.
 */
export function clearAnswered(): void {
  answered.length = 0;
}
