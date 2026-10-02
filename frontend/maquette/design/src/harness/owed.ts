// THE ACTS A NAMED STATE STILL OWES — so a reader waits for them instead of betting a number.
//
// Some named states act on a timer of their own: a card is tapped once its read has
// answered, a panel's act is pressed once the panel has its data. The page cannot say
// by itself that such a timer is still owed, and a rule that read a state at a fixed
// delay read it mid-act — `responsive.py` caught « Marquer comme vu »'s panel still
// rising, with its scrim over the menu button (`acq-closure-panel`, `acq-closure-seen`,
// webkit at 390 px, develop and PR #687 alike). So every timer a state arms goes through
// `owed`, which counts it, and the readers (`common.py` READY, `responsive.py`) wait for
// the count to reach zero before they read.
//
// HARNESS ONLY: this module is reached from the named states, which are installed
// behind `__MOCKS_BUILT_IN__`.

const pending = new Set<number>();

function publish(): void {
  (window as unknown as { __owedActs: number }).__owedActs = pending.size;
}

/**
 * Runs an act after a delay, and says it is owed until it has run.
 *
 * A nested `owed` armed by the act itself is counted before this one is released,
 * so a chain of acts reads as owed from its first link to its last.
 *
 * @param act What the state does.
 * @param ms How long after it is asked for.
 * @returns The timer's handle, to hand to `forgetOwed`.
 */
export function owed(act: () => void, ms: number): number {
  const handle = window.setTimeout(() => {
    try {
      act();
    } finally {
      pending.delete(handle);
      publish();
    }
  }, ms);
  pending.add(handle);
  publish();
  return handle;
}

/**
 * Drops an act that is no longer owed — the next state was driven first.
 *
 * @param handle What `owed` returned.
 */
export function forgetOwed(handle: number): void {
  window.clearTimeout(handle);
  pending.delete(handle);
  publish();
}
