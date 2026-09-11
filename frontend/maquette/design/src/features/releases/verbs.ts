// THE RELEASE PICKER'S OWN VERB, declared to the tap registry.
//
// Choosing a candidate is the picker's act: the operator has compared what a
// search turned up and says which one to fetch.
//
// IT HAS A NAME OF ITS OWN, AND THAT IS THE REPAIR (B-309). The picker used to
// emit `data-take` — the same attribute a medium's own panel emits — and the
// engine's delegation carried two branches for it, told apart by guessing at
// the VALUE: an index was the screen's, a title was the panel's. `Number("The
// Hawk")` is NaN, the lookup answered undefined, reading its `res` threw, and
// the panel's own branch further down the chain was unreachable. Guarding that
// collision was possible; not having it is better. Two different subjects wore
// one name, and now each wears its own — the panel keeps `take`, the picker
// says `pick-release`.
//
// SO THERE IS NOTHING LEFT TO ARBITRATE, and nothing left in the engine: the
// registry holds ONE handler per name, which is exactly why one shared name
// could never have moved onto it, and why two names can.
//
// WHY IT SAYS ONE SENTENCE, and it is B-322. The branch this replaces wrote
// TWO into the single message element — `actionTake`'s « … récupéré — suivez-le
// dans « En vol ». » and the delegation's own « « res src lang » retenue —
// récupération lancée. » The second overwrote the first inside the same task,
// so which one the operator read was a race, and each carried only half of
// what they needed to know. What they need after choosing a release is both
// halves at once: WHICH candidate was retained, and WHERE the medium went.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";

/** The address the picker lives at, and the only one this verb acts on. */
const RELEASES_ADDRESS = "/releases/";

/**
 * The medium the picker is open on, read from the ADDRESS.
 *
 * THE ADDRESS AND NOT THE STORE, deliberately. `state.relatedTitle` is written
 * by the screen bridge on the way in, so an entry reached by a typed or
 * bookmarked URL never set it — the same accepted debt `/add` and `/releases`
 * already carry — and a door acting on a stale subject takes the wrong medium
 * in silence. The address is the screen's identity and cannot be stale.
 *
 * Returns:
 *     The title, or null when the picker is not the screen on show.
 */
function titleOnScreen(): string | null {
  const path = window.location.pathname;
  if (!path.startsWith(RELEASES_ADDRESS)) return null;
  const title = decodeURIComponent(path.slice(RELEASES_ADDRESS.length));
  return title === "" ? null : title.normalize("NFC");
}

/**
 * Takes the release the tapped row names.
 *
 * THE ACT HAPPENS IN THE TAP'S OWN COMMIT. The branch this replaces popped the
 * router and then waited 260 ms before doing anything, which is B-249's shape:
 * long enough for the operator to wonder whether the tap registered, and long
 * enough for a rule reading the queue promptly to see nothing at all. The
 * screen is left first, because leaving is what the operator asked for by
 * choosing; the act follows immediately.
 *
 * A VALUE NAMING NO ROW DOES NOTHING, and it is not defensive dressing: the
 * list is asked rather than the value's spelling, so a picker drawn from a
 * list that has since been answered again cannot take a candidate nobody is
 * looking at.
 */
registerVerb("pick-release", (value) => {
  const title = titleOnScreen();
  if (title === null) return;
  const chosen = (window.__releases?.() ?? [])[value as unknown as number];
  if (chosen === undefined) return;
  const reference = window.__referentiel;
  window.__bridge.back();
  window.__queueActions?.take(title);
  reference.render();
  window.__toast?.show({
    message: i18next.t("verbs.releases.taken", {
      quality: `${chosen.res} ${chosen.src} ${chosen.lang}`,
      title: reference.baseTitle(title),
    }),
  });
});
