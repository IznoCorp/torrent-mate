// THE ARRIVALS' VERBS, declared to the tap registry: the pipeline's two
// commands, from the pilot's bar.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { toast } from "../../lib/shell-doors";
import { isRequestFailure, sharedQueryClient, send } from "../../lib/query-client";

// The status the layer refuses a second pass with: the same action, already going.
const ALREADY_GOING = 409;

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
