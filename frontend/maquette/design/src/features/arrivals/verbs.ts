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
import i18next from "i18next";
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
      take: (value: string | undefined) => boolean;
    };
  }
}

/**
 * Takes the medium a `data-take` value names, if it names one.
 *
 * ONE DOOR, ANSWERING WHETHER IT ACTED, so the delegation's branch is a single
 * line and the act is entirely here — which is the direction D5 asks the engine
 * to move in. The release screen's own take is left to fall through.
 *
 * WHETHER THE VALUE IS OURS IS READ FROM THE QUEUE, never from its SHAPE. « is
 * it a number? » would be a rule about spelling, and a medium whose title is a
 * year would break it — `2012`, `1917`, `300`. The queue is the thing that
 * knows.
 *
 * THE PANEL CLOSES AND THE PAGE IS REDRAWN HERE, inside the tap's own commit:
 * the branch this replaces closed the panel and waited 260 ms before acting,
 * which is B-249's shape, and R123 reads the queue at 120 ms to say it is gone.
 *
 * Args:
 *     value: The attribute's value, or undefined when there is none.
 *
 * Returns:
 *     True when this feature took the medium — the delegation stops there.
 */
function take(value: string | undefined): boolean {
  if (value === undefined) return false;
  if (!queueNow().takeable.some((one) => one.t === value)) return false;
  const reference = window.__referentiel;
  window.__panel.close();
  window.__queueActions?.take(value);
  reference.render();
  window.__toast?.show({
    message: i18next.t("verbs.arrivals.taken", {
      title: reference.baseTitle(value),
    }),
  });
  return true;
}

window.__arrivalsVerbs = { take };
