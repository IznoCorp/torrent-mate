// THE CANDIDATES SCREEN'S VERBS, and the take, declared to the tap registry.
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
import { queueNow, queueActions } from "../../lib/queue";
import { bridge, panel, screens, toast, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { baseTitle } from "../../lib/titles";
import { answerMatch, heldMatch } from "./plex-verbs";

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
  if (!queueNow().takeable.some((one) => one.title === value)) return;
  panel.close();
  queueActions?.take(value);
  redraw();
  toast?.show({
    message: i18next.t("verbs.acquisition.taken", {
      title: baseTitle(value),
    }),
  });
});

/* THE ARBITRATION'S VERBS. The folder answered is the one the screen was opened
   on (`state.resolveTarget`), never an attribute's value: what `data-resolve`
   carries is the CHOSEN CANDIDATE. Each leaves the screen and acts in the same
   tap. */

/**
 * Opens the arbitration: a folder's, or the first stuck one when none is named.
 */
registerVerb("resolution", (folder) => screens.resolution(folder || undefined));

// A candidate picked: the folder becomes it, and the pick waits out its undo.
// ON A PLEX MATCH, the pick IS the correction: it is sent now, carrying the
// identity picked — the one held when it is the one picked.
registerVerb("resolve", (choice) => {
  const target = store.read().state.resolveTarget as string;
  bridge.back();
  const held = heldMatch(target);
  if (held !== null) {
    void answerMatch("correct", target, held.title === choice ? held : { title: choice });
    return;
  }
  const undo = queueActions?.pick(target, choice);
  store.touch();
  const message = i18next.t("verbs.acquisition.resolved", { choice: choice || target });
  toast?.show(typeof undo === "function" ? { message, undo } : { message });
});

// Agreeing with the machine: the automatic result stands and the folder leaves
// the queue, because the operator has answered.
// On a Plex match, agreeing with the machine is confirming the match.
registerVerb("leave", () => {
  const target = store.read().state.resolveTarget as string;
  bridge.back();
  if (heldMatch(target) !== null) {
    void answerMatch("confirm", target);
    return;
  }
  if (!queueActions?.leave(target)) return;
  store.touch();
  toast?.show({ message: i18next.t("verbs.acquisition.left", { title: target }) });
});

// No match for the folder: a pre-filled identification search, its query the
// folder's name without its release tags.
registerVerb("manual", (folder) => {
  const query = folder
    .replace(/\.(mkv|mp4|avi)$/i, "")
    .replace(/[._]+/g, " ")
    .replace(/\b(MULTi|VOSTFR|WEB-DL|WEBRip|BluRay|x264|x265|HEVC|1080p|2160p|720p|FRENCH|TRUEFRENCH)\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
  // The search STACKS over the arbitration (DECIDED 2 = A): its Retour gives
  // the arbitration back, and a pick in it gives back the list.
  screens.add(query, "identify");
});
