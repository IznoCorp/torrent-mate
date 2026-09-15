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
import { queueNow, queueActions } from "../../lib/queue";
import { bridge, panel, screens, toast, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { isRequestFailure, sharedQueryClient, send } from "../../lib/query-client";
import { pendingDecisions } from "./queries";
import { baseTitle } from "../../lib/titles";

// The status the layer refuses a second pass with: the same action, already going.
const ALREADY_GOING = 409;

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
    message: i18next.t("verbs.arrivals.taken", {
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
registerVerb("resolve", (choice) => {
  const target = store.read().state.resolveTarget as string;
  bridge.back();
  const undo = queueActions?.pick(target, choice);
  store.touch();
  const message = i18next.t("verbs.arrivals.resolved", { choice: choice || target });
  toast?.show(typeof undo === "function" ? { message, undo } : { message });
});

// Agreeing with the machine: the automatic result stands and the folder leaves
// the queue, because the operator has answered.
registerVerb("leave", () => {
  const target = store.read().state.resolveTarget as string;
  bridge.back();
  if (!queueActions?.leave(target)) return;
  store.touch();
  toast?.show({ message: i18next.t("verbs.arrivals.left", { title: target }) });
});

// The next folder waiting, on the same screen: the address is the screen's
// identity, so the same depth is a REPLACE.
registerVerb("next", (current) => {
  const lists = queueNow();
  const decisions = pendingDecisions?.() ?? [];
  const following = lists.blocked
    .concat(lists.stuck)
    .map((card) => decisions.find((decision) => decision.folder === card.title) ?? null)
    .find((decision) => decision !== null && decision.folder !== current);
  if (following) screens.resolution(following.folder, true);
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
  // The search takes the arbitration's place: a REPLACE, the ladder a pop and a
  // push used to leave.
  screens.add(query, "identify", true);
});

/* THE PIPELINE'S TWO COMMANDS ASK THE LAYER. « lancer » runs a pass — asked
   while a maintenance run holds the lock, the pass is QUEUED and says so
   (DOIT-4); asked while a pass is already going, it is the same action already
   under way and the layer answers 409, which is SAID in its own sentence and
   never read as a stop. « arrêter » stops it. The status read is asked again
   afterwards, so the bar draws what the pipeline is doing rather than what the
   tap hoped for — AND THE LOCKS READ IS INVALIDATED beside it: a pass taking or
   freeing the pipeline's lock is one fact with two readers, and Système's
   block, cached from an earlier visit, would otherwise say « Libre » over a
   running pipeline. It is invalidated rather than refetched because Système is
   not on screen here: the read is marked stale and asked again when the block
   is next drawn. */
const LOCKS = ["/api/maintenance/locks"];

registerVerb("pipe", (command) => {
  const path = command === "stop" ? "/api/pipeline/kill" : "/api/pipeline/run";
  void send("POST", path, {})
    .then((answered) => {
      const state = (answered as { state?: string } | undefined)?.state;
      return state === "running"
        ? "verbs.arrivals.pipelineStarted"
        : state === "queued"
          ? "verbs.arrivals.pipelineQueued"
          : "verbs.arrivals.pipelineStopped";
    })
    .catch((refusal: unknown) => {
      if (isRequestFailure(refusal) && refusal.status === ALREADY_GOING) {
        return "verbs.arrivals.pipelineAlreadyRunning";
      }
      throw refusal;
    })
    .then(async (sentence) => {
      await sharedQueryClient?.refetchQueries({ queryKey: ["/api/pipeline/status"] });
      await sharedQueryClient?.invalidateQueries({ queryKey: LOCKS });
      toast?.show({ message: i18next.t(sentence) });
    });
});
