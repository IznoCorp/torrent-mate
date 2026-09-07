// THE ARRIVALS' VERBS, declared to the tap registry.
//
// « Récupérer maintenant » — take a medium the queue is holding — is the
// arrivals' act: it moves an item out of what is waiting and into what is in
// flight. The verb's NAME (`data-take`) does not change; what moved is the
// reader.
//
// WHY THE READER HAD TO MOVE, and it is **B-309**. The document's delegation
// carried TWO branches for `data-take`. The release picker's was checked first
// and had no guard, so it swallowed the one a medium's own panel emits — where
// the value is a TITLE and not an index into the releases. `Number(title)` is
// NaN, the lookup answered undefined, and reading its `res` threw. The tap
// raised a TypeError, the panel closed, and nothing was taken. The panel's own
// branch, further down the same chain, was unreachable.
//
// THE FIRST REPAIR TOLD THE TWO APART BY WHAT THEY CARRIED — an index is the
// picker's, a title is the panel's — through a door the engine asked before
// its own branch. THAT GUARD HAS NO SUBJECT ANY MORE: the picker says
// `data-pick-release` now, so this name has one meaning and one reader, and
// the arbitration it needed is gone rather than guarded. Which is also what
// let this move onto the registry at all: the registry holds one handler per
// name, and a name two features claimed could never have had one.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { queueNow } from "../../lib/queue";

/**
 * Takes the medium a `data-take` value names.
 *
 * WHETHER THE QUEUE IS STILL HOLDING IT IS READ FROM THE QUEUE, never from the
 * value's SHAPE. This is no longer telling two doors apart — it is refusing to
 * act on a medium that has since left what is waiting, which a panel drawn
 * before a refresh can still name.
 *
 * THE PANEL CLOSES AND THE PAGE IS REDRAWN HERE, inside the tap's own commit:
 * the branch this replaces closed the panel and waited 260 ms before acting,
 * which is B-249's shape, and R123 reads the queue at 120 ms to say it is gone.
 */
registerVerb("take", (value) => {
  if (!queueNow().takeable.some((one) => one.t === value)) return;
  const reference = window.__referentiel;
  window.__panel.close();
  window.__queueActions?.take(value);
  reference.render();
  window.__toast?.show({
    message: i18next.t("verbs.arrivals.taken", {
      title: reference.baseTitle(value),
    }),
  });
});
