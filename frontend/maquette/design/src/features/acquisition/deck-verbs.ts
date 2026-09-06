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
import { registerVerb } from "../../lib/verbs";
import { dismissSug } from "./discover-feed";

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
