// WHO ANSWERS A TAP ON A `data-*` VERB, once the engine no longer does.
//
// THE PROBLEM THIS SOLVES, and it appears the moment a NEW verb is added rather
// than moved. A panel action is `{ text, icone, target }` and `target` is a map
// of DATA ATTRIBUTES — `ui/panel` draws them and attaches no handler of its own,
// by contract. Until now every one of those attributes was read by the dying
// engine's document delegation, so a verb that had never existed there had
// nobody to answer it, and giving it one meant adding a branch to `legacy.js` —
// which D5 forbids and which the size ledger refuses outright.
//
// So the reader moves to this side BEFORE the engine's does. A feature declares
// the attribute it owns and what to do about it; one listener, here, dispatches.
// When the engine's own delegation dies, its branches move onto this same
// registry rather than needing a mechanism invented for them at that moment.
//
// IT NAMES NO DOMAIN. The registry is a map from an attribute name to a
// function; every name in it comes from a feature that registered it, so `lib/`
// carries the SHAPE and never the subject (invariant 10). A verb about a
// journey is spelled in `features/acquisition/`, where a journey is known.
//
// IT DOES NOT FIGHT THE ENGINE. Both listeners sit on the document, and they
// answer disjoint attributes: the engine has no branch for a name it never
// knew, and this registry answers nothing it was not given. A name that ends up
// in both is a defect, not an arbitration — and it is one a rule can read,
// because a verb answered twice acts twice.

/** What answers a tap on one verb. */
type VerbAction = (value: string, element: HTMLElement) => void;

const actions = new Map<string, VerbAction>();

// The `dataset` key for an attribute name, which is what a DOM element is read
// through: `data-journey-requeue` arrives as `journeyRequeue`. Computed rather
// than declared twice, so the two spellings of one name cannot drift.
function keyForAttribute(name: string): string {
  return name.replace(/-([a-z])/g, (_whole, letter: string) =>
    letter.toUpperCase());
}

/**
 * Declares what answers a tap on one `data-*` verb.
 *
 * Called at module evaluation by the feature that owns the verb, exactly as
 * `registerBlock` and `registerProducer` are. The shell imports those feature
 * modules at boot, before anything can be tapped.
 *
 * Args:
 *     name: The attribute, without its `data-` prefix and in its markup
 *         spelling — `journey-requeue`, not `journeyRequeue`.
 *     act: What to do, given the attribute's value and the element carrying it.
 */
export function registerVerb(name: string, act: VerbAction): void {
  actions.set(keyForAttribute(name), act);
}

/**
 * Names every verb a handler has been registered for.
 *
 * Published for the rule that reads the seam from outside, exactly as
 * `registeredProducers` is: a rule that had to import this module to ask would
 * be coupled to how the module is built.
 *
 * Returns:
 *     The dataset keys, sorted, so a reading is comparable with the one before.
 */
export function registeredVerbNames(): string[] {
  return [...actions.keys()].sort();
}

/**
 * Starts answering taps.
 *
 * ONE LISTENER, walking up from what was tapped — the same shape the engine's
 * delegation has, and for the same reason: the elements carrying these
 * attributes are drawn and re-drawn by producers, so a listener bound to a node
 * would be a listener bound to one render of it.
 *
 * IT READS THE ELEMENT'S OWN KEYS rather than asking the registry for each
 * name in turn: a tap is on the hot path of every gesture in the application,
 * and walking the registry per ancestor would make the cost grow with the
 * number of verbs the interface has.
 */
export function installVerbs(): void {
  // THE SEAM A RULE READS THE REGISTRY THROUGH, published here because this is
  // where the registry starts answering. `registeredVerbNames` said in its own
  // docstring that it was « published for the rule that reads the seam from
  // outside » and it was exported and called by NOBODY — a seam nothing reaches
  // is a seam that does not exist, and the first rule to want it (R171, holding
  // that `data-rescrape` is answered HERE and no longer by the dying engine)
  // found nothing to ask.
  window.__verbNames = registeredVerbNames;
  document.addEventListener("click", (event) => {
    let node = event.target as HTMLElement | null;
    while (node !== null && node !== document.body) {
      for (const key of Object.keys(node.dataset)) {
        const act = actions.get(key);
        if (act === undefined) continue;
        // PROPAGATION STOPS HERE, so the engine's delegation does not also
        // walk this element looking for a branch of its own. A verb answered
        // twice acts twice, and an undo that ran twice would put back something
        // nobody removed. The DEFAULT is left alone: these are `<button>`s
        // outside a form, so preventing it would suppress focus and the
        // browser's own affordances for nothing.
        event.stopPropagation();
        act(node.dataset[key] ?? "", node);
        return;
      }
      node = node.parentElement;
    }
  }, true);
}

declare global {
  interface Window {
    /** Every verb the registry answers, for a rule reading it from outside. */
    __verbNames?: () => string[];
  }
}
