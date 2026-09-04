// THE ARRIVALS' VERBS, as the click delegation calls them.
//
// « Récupérer maintenant » — take a medium the queue is holding — is the
// arrivals' act: it moves an item out of what is waiting and into what is in
// flight. The verb's NAME (`data-take`) does not change; what moved is the
// reader.
//
// WHY THE READER HAD TO MOVE, and it is **B-309**. The document's delegation
// carried TWO branches for `data-take`. The release-choice screen's was checked
// first and had no guard, so it swallowed the one a medium's own panel emits —
// where the value is a TITLE and not an index into the releases. `Number(title)`
// is NaN, the lookup answers undefined, and reading its `res` threw. The tap
// raised a TypeError, the panel closed, and nothing was taken. The panel's own
// branch, further down the same chain, was unreachable.
//
// THE TWO ARE TOLD APART BY WHAT THEY CARRY, which is what the engine's own
// branch never asked: an INDEX is the release screen's, a TITLE is the panel's.
// That is the whole repair, and it lives here rather than in the delegation
// because the act is the arrivals' — `frame-model.md` Part 12.
import { queueNow } from "../../lib/queue";

declare global {
  interface Window {
    /** The arrivals' verbs, called by the dying engine's delegation. */
    __arrivalsVerbs?: {
      /**
       * Whether `data-take`'s value names a MEDIUM this feature can take.
       *
       * The release screen's own take carries an index into its list; a
       * medium's panel carries its title. A value that names nothing the queue
       * holds is not this feature's, and saying so is how the delegation knows
       * which of the two branches it is in.
       */
      takes: (value: string) => boolean;
      /** Takes the medium, and says so. */
      take: (title: string) => void;
    };
  }
}

/**
 * Whether a `data-take` value names a medium waiting to be taken.
 *
 * READ FROM THE QUEUE, never from the value's SHAPE. « is it a number? » would
 * be a rule about spelling, and a medium whose title is a year would break it
 * — `2012`, `1917`, `300`. The queue is the thing that knows.
 *
 * Args:
 *     value: The attribute's value.
 *
 * Returns:
 *     True when the queue holds a takeable medium by that name.
 */
function takes(value: string): boolean {
  return queueNow().takeable.some((one) => one.t === value);
}

/**
 * Takes a medium out of the queue.
 *
 * Args:
 *     title: The medium.
 */
function take(title: string): void {
  window.__queueActions?.take(title);
}

window.__arrivalsVerbs = { takes, take };
