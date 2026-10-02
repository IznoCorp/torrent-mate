// « Marquer comme vu » — a closed tunnel read, once (Q8, Q9; maquette-blocked §
// 1.5, § 1.6). DECIDED 2: an act of the card's panel, never a « × » on the card.
//
// OPTIMISTIC, AND HONEST ABOUT A REFUSAL (NE-DOIT-PAS-5): the card leaves every
// list at once, the panel closes, and the mark is sent; a layer that refuses
// puts the card back where it stood and the message says it was not marked. A
// held send (offline) has not failed: the card stays gone, the outbox says it
// has not left yet. Seen is the ENGINE's (BK5): the queue asked again does not
// bring it back.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { panel, toast } from "../../lib/shell-doors";
import { HELD, send, sharedQueryClient } from "../../lib/query-client";
import { acquisitionKey } from "../../lib/arrival-slots";
import type { Schemas } from "../../lib/contract-schemas";

/** The queue's reads, in every world the cache holds one for. */
const QUEUE = ["/api/acquisition/to-handle"];
// Between a title and the season or episode it is of, in a key.
const KEY_SEPARATOR = "|";

type Queue = Partial<Record<string, Schemas["QueueCard"][]>>;

/**
 * Takes one closed tunnel's card out of every list of every queue read held.
 *
 * ONLY THE CLOSED ONE: a medium that came back has a new card under the same
 * key, and that card stays (Q8).
 *
 * @param subject The acquisition's key.
 * @returns What the cache held before, to put back on a refusal.
 */
function takeOut(subject: string): [readonly unknown[], Queue | undefined][] {
  const held = sharedQueryClient?.getQueriesData<Queue>({ queryKey: QUEUE }) ?? [];
  for (const [key, queue] of held) {
    if (queue === undefined) continue;
    sharedQueryClient?.setQueryData<Queue>(key, Object.fromEntries(Object.entries(queue).map(([name, cards]) => [
      name,
      Array.isArray(cards) ? cards.filter((card) => card.closure == null || acquisitionKey(card) !== subject) : cards,
    ])));
  }
  return held;
}

/**
 * Marks one closed tunnel seen, for the account.
 *
 * @param subject The acquisition's key.
 */
async function markSeen(subject: string): Promise<void> {
  const before = takeOut(subject);
  panel?.close();
  try {
    const outcome = await send("POST", `/api/acquisition/journeys/${encodeURIComponent(subject)}/closure/seen`);
    if (outcome !== HELD) await sharedQueryClient?.invalidateQueries({ queryKey: QUEUE });
  } catch {
    for (const [key, queue] of before) sharedQueryClient?.setQueryData(key, queue);
    toast?.show({
      message: i18next.t("verbs.acquisition.closureSeenRefused", { title: subject.split(KEY_SEPARATOR)[0] }),
    });
  }
}

registerVerb("closure-seen", (subject) => {
  void markSeen(subject);
});
