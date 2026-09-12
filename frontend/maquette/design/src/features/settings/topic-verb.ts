// Entering a settings rubric — an ARRIVAL, and therefore a place one can leave.
//
// Entering one used to write the rubric and call `replacePath()`, the verb D1b
// reserves for an ADJUSTMENT — a filter, an inner tab, a sort. A rubric is none of those: it is a surface the reader
// ENTERS and has to leave, which D1b rule 1 calls a deliberate arrival, and an
// arrival PUSHES. Replaced, it left Back nothing to pop, so the system gesture
// popped the PAGE.
//
// THE ENTRY CARRIES THE RUBRIC, and that is what makes the way back work
// without adding a dial to the address model. `SETTINGS_STATE.topic` is not an
// addressable dial today — `lib/addresses.ts` carries one for Maintenance's
// rubric and none for this one — so the entry's own STATE is where the rubric
// travels, and a pop reads it back. Two ends, one shape: what the push writes
// is what the pop reads.
//
// WHY `popstate` AND NOT THE BRIDGE'S SUBSCRIPTION. `__bridge.subscribe` has
// one reader — the engine's own back handler — and a second subscriber would be
// a second mechanism for one signal (NE-DOIT-PAS-7). The native event is what
// the bridge itself is built over, it fires for the system gesture, the
// browser's control and `history.back()` alike, and it costs this feature one
// listener that dies with the surface.
import { giveTheEntryBackFirst } from "../../lib/stacked-surface";
import { registerVerb } from "../../lib/verbs";

/** The key the rubric travels under, on the entry this verb pushes. */
const CARRIED = "settingsTopic";

/**
 * Opens one rubric, and records the arrival.
 *
 * Args:
 *     rubric: The rubric's id, as the row spells it.
 */
function openTopic(rubric: string): void {
  const reference = window.__referentiel;
  reference.SETTINGS_STATE.topic = rubric;
  // The search is cleared with the same gesture the engine's branch cleared it
  // with: a rubric and a search are two answers to one question, and leaving
  // the query behind showed the rubric under a count of matches.
  reference.SETTINGS_STATE.q = "";
  reference.render();
  try {
    window.__bridge.record(
      { ...(window.__navigationState?.() ?? {}), [CARRIED]: rubric },
      window.__address.compose(window.__store.read().state),
    );
    // SAID ONLY WHEN IT REALLY PUSHED. A cold load of a rubric's address opens
    // one without an entry of its own, and a driven state opens one without
    // touching history at all; either counted would have the ladder step over
    // something that is not there.
    entryPosed();
  } catch (error) {
    console.error("entering a settings rubric: navigation write failed", error);
    window.__navEchec = true;
  }
}

/**
 * Closes the rubric the reader has just stepped off.
 *
 * A LAYER'S ENTRY HAS NO OPINION ABOUT THE RUBRIC UNDER IT, and that is the
 * whole of the guard below. A panel is addressable — it pushes an entry of its
 * own, laid OVER the rubric — so stepping back onto one is stepping back onto
 * something the rubric is still showing through. Read without this, the first
 * Back that shut a panel also shut the rubric beneath it, and the reader who
 * had just filed an edit found themselves on the list of rubrics: measured by
 * R166's own walk, on this verb's first build.
 */
function leaveTopic(): void {
  const reference = window.__referentiel;
  const entry = history.state as Record<string, unknown> | null;
  if (entry?.layer !== undefined) return;
  const carried = entry?.[CARRIED];
  const topic = typeof carried === "string" ? carried : null;
  if (reference.SETTINGS_STATE.topic === topic) return;
  reference.SETTINGS_STATE.topic = topic;
  reference.render();
}

/* DECLARED AT MODULE EVALUATION, as every other verb in this tree is, and
   named once in `app/panel-contributions.ts` — the boot is where a feature's
   side effect is named whatever it is. The listener is added once, for the
   life of the document, exactly as the tap registry's own is. */
registerVerb("topic", openTopic);
window.addEventListener("popstate", leaveTopic);
/* AND THE ENTRY IS GIVEN BACK BEFORE THE PAGE CHANGES. The switch beneath was
   written against a stack of « the entry page plus at most one » and steps back
   exactly one entry; with a rubric open that step lands on the rubric's entry
   and the page never changes at all. */
const entryPosed = giveTheEntryBackFirst(
  () => window.__referentiel.SETTINGS_STATE.topic !== null);
