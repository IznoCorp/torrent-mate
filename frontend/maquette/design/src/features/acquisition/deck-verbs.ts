// THE DECK'S OWN VERBS, answered here rather than by the dying engine.
//
// A card in Découvrir asks one question and there are two answers to it: take
// it, or drop it. Taking it is the ACQUISITION's act and lives in
// `follow-verbs.ts`, because what it changes is what the operator is waiting
// for. Dropping it is the DECK's, because nothing leaves the pile anywhere
// else — and that is the whole reason the two are not in one file.
//
// WHAT MOVES IS THE READER, AND ONLY THE READER. `dismissSug` already lives in
// `discover-feed.ts`: the removal, the collapse the row is drawn for, and the
// undo that makes the gesture safe are all there. The engine's delegation
// merely called it. So this file is a declaration, not an act — the smallest
// possible shape for a verb whose body never belonged to the engine.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { dismissSug } from "./discover-feed";
import { loadMoreSuggestions } from "./queries";

// THE DECLARATION RUNS AT MODULE EVALUATION and the boot names this module in
// `app/panel-contributions.ts`, for the reason that list gives itself: the
// shell stands one line under a hard block, and a contribution must cost it
// nothing.
//
// THE PANEL LEAVES FIRST, in the tap's own commit, exactly as the engine's
// branch did — and for a reason that outlives it: the card collapses where the
// panel was, so a panel still on screen while the row goes is a reader watching
// two things happen in the wrong order.
registerVerb("dropsug", (value) => {
  window.__panel.close();
  dismissSug(Number(value));
});

// « CHARGER 30 DE PLUS », AND IT NOW DOES THAT. The engine's branch wrote
// `{ sugGone: new Set(), sugOrder: null }` and re-rendered: it CLEARED what
// the operator had dismissed and reshuffled the same reserve, then announced
// « 30 suggestions de plus ». Nothing about that sentence was true of what it
// did — and the one thing an operator is entitled to expect from a feed is
// that what they threw away stays thrown away.
//
// SO THE RESERVE GROWS. The layer is asked for its next page, the page is
// appended, and every position already spoken for keeps its meaning — which
// is why nothing dismissed comes back without a step that puts it back.
//
// AND THE MESSAGE NAMES WHAT ARRIVED, never the number on the button. A page
// at the end of the reserve is smaller than a full one, and the last press
// brings nothing at all: saying « 30 de plus » there would be the engine's own
// defect wearing a working implementation.
registerVerb("sugmore", () => {
  void loadMoreSuggestions().then(
    (arrived) => {
      const total = (window.__suggestions?.() ?? []).length;
      window.__store.touch();
      window.__toast?.show({
        message: arrived === 0
          ? i18next.t("verbs.deck.spent", { total })
          : i18next.t(arrived === 1 ? "verbs.deck.loadedOne" : "verbs.deck.loaded",
                      { count: arrived, total }),
      });
    },
    // A REFUSAL SAYS SO. The reserve is unchanged and the pile is exactly as
    // it was, so the honest report is that the load did not happen — not a
    // count of nothing, which reads like a spent reserve.
    () => {
      window.__toast?.show({ message: i18next.t("verbs.deck.refused") });
    });
});
