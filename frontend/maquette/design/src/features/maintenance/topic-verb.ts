// Entering a maintenance rubric — B-332's shape on the second page that has
// rubrics (B-361).
//
// Found by the inventory that followed the operator's report: a real tap on
// `[data-maintopic]` wrote the rubric into the address by REPLACEMENT, drew no
// way back, and left the system Back gesture popping the page. D1b rule 1 calls
// a rubric a deliberate arrival, and an arrival pushes.
//
// THE ADDRESS ALREADY CARRIES THIS ONE. `lib/addresses.ts` declares `topic` as
// a dial of this page, writing the store's `maintTopic` — so the entry pushed
// here reopens the rubric on a reload and restores it on the way back with no
// state of its own, which is the difference between this verb and Configuration's
// (`features/settings/topic-verb.ts`, whose rubric is not addressable).
import { giveTheEntryBackFirst } from "../../lib/stacked-surface";
import { registerVerb } from "../../lib/verbs";

/**
 * Opens one rubric.
 *
 * Args:
 *     rubric: The rubric's id, as the row spells it.
 */
function openTopic(rubric: string): void {
  const reference = window.__referentiel;
  if (!rubric) return;
  window.__store.write({ maintTopic: rubric });
  reference.render();
  try {
    window.__bridge.record(
      window.__navigationState?.() ?? null,
      window.__address.compose(window.__store.read().state),
    );
    // Only when it really pushed — see the note in `lib/stacked-surface.ts`:
    // this page's rubric is addressable, so a cold load opens one with no entry
    // of its own.
    entryPosed();
  } catch (error) {
    console.error("entering a maintenance rubric: navigation write failed",
                  error);
    window.__navEchec = true;
  }
}

/* Declared at module evaluation, and named in `app/panel-contributions.ts`. */
registerVerb("maintopic", openTopic);
/* And the entry is given back before the page changes — see the note in
   `lib/stacked-surface.ts`; the rubric this page draws has the same shape. */
const entryPosed = giveTheEntryBackFirst(
  () => window.__store.read().state.maintTopic != null);
