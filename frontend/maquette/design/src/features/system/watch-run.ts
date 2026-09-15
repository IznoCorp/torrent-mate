// « Relancer la veille » — the ask, the run it names, and the figures it ends with.
//
// ONE VERB, TWO EMITTERS. The « ⋮ » sheet's panel and the levers section carry
// the same `data-watch-now`, and it is registered here ONCE. §13 is one
// derivation per question, not one button per act — and a verb registered per
// surface is how one of them comes to work while the other says a sentence and
// sends nothing, which is the register row this closes.
//
// THE FIGURES ARE NOT IN THE ANSWER, AND THAT IS THE POINT. The ask is accepted
// with the run's identifier — a run takes minutes, and an answer carrying its
// results at once would be a lie about a machine that has not finished. The
// interface keeps the identifier and reads the RUN; what makes the numbers
// arrive is the stream, never a clock of this file's own (NE-DOIT-PAS-8).
import { useQuery } from "@tanstack/react-query";
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { toast } from "../../lib/shell-doors";
import { HELD, read, send, sharedQueryClient } from "../../lib/query-client";
import type { components } from "../../contract/types";

type RunDetail = components["schemas"]["RunDetail"];

/** The history, and the run the veille last launched inside it. */
const HISTORY = "/api/pipeline/history";
const LAUNCHED = ["veille/launched"];
/** What holds the pipeline, which a veille takes while it runs. */
const LOCKS = ["/api/maintenance/locks"];

/** What the interface holds about the run it asked for. */
type Launched = { runUid?: string; failed?: boolean };

/**
 * Asks for a veille, and keeps the run the server named.
 *
 * A REFUSAL IS KEPT TOO. « It failed » is a state the block must draw — loudly,
 * and with no success word anywhere near it — so it is recorded here rather
 * than swallowed into a promise nobody reads.
 *
 * @returns Whether the server accepted the veille.
 */
async function launchTheWatch(): Promise<boolean> {
  try {
    const answer = await send<{ runUid: string }>("POST", "/api/acquisition/detect");
    if (answer === undefined || answer === HELD) return false;
    sharedQueryClient?.setQueryData(LAUNCHED, { runUid: answer.runUid } satisfies Launched);
  } catch {
    sharedQueryClient?.setQueryData(LAUNCHED, { failed: true } satisfies Launched);
    return false;
  }
  // THE HISTORY IS A PREFIX OF THE RUN'S OWN KEY, so invalidating it reaches
  // the detail as well: one invalidation, and the list and the run cannot show
  // two different truths about the same passage.
  await sharedQueryClient?.invalidateQueries({ queryKey: [HISTORY] });
  // AND THE LOCKS: a veille is a maintenance run, and it takes the pipeline's
  // lock for its whole run — the block saying « Libre » over it would be the
  // same disagreement a pass started from Arrivées once caused.
  await sharedQueryClient?.invalidateQueries({ queryKey: LOCKS });
  return true;
}

// THE ACT ANSWERS WHERE THE FINGER PRESSED (DOIT-4). The « ⋮ » sheet draws no
// run, so without a message a press there changed nothing a person could see;
// the message is the verb's, so it says the same from either emitter. A named
// state launching a veille goes through `watchNow` and raises none.
registerVerb("watch-now", () => {
  void launchTheWatch().then((launched) => {
    if (launched) toast?.show({ message: i18next.t("verbs.system.watchLaunched") });
  });
});

declare global {
  interface Window {
    /** Asks for a veille. Registered here, called by a named state. */
    __watchNow?: () => void;
  }
}

/** Asks for a veille — the door a named state goes through. */
export const watchNow = () => {
  void launchTheWatch();
};

/** What the interface holds about the run the veille last launched. */
export function useLaunchedWatch(): Launched | undefined {
  const { data } = useQuery({
    queryKey: LAUNCHED,
    queryFn: async () => sharedQueryClient?.getQueryData<Launched>(LAUNCHED) ?? null,
    staleTime: Infinity,
  });
  return data ?? undefined;
}

/**
 * The run the veille launched, as the server now describes it.
 *
 * @param runUid The run's identifier, when one has been named.
 * @returns The run, or undefined while nothing has been asked for.
 */
export function useWatchRun(runUid: string | undefined) {
  return useQuery({
    queryKey: [HISTORY, runUid],
    queryFn: async () => (await read(`${HISTORY}/${runUid}`)) as RunDetail,
    enabled: runUid !== undefined,
  });
}
