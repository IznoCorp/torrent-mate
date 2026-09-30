// A folder « continued » with a candidate: it goes back through the pipeline.
//
// ITS OWN MODULE because `staging.ts` stands at the 400-line ceiling, and this
// is the one answer the continuation's proof (DOIT-5) reads: after « Choisir »
// the card leaves « À traiter », stands PAST « identifié » on « En cours », and
// the decision it waited on is settled with the candidate chosen.
import { mockState } from "../state";
import { FROM_BLOCKED, FROM_DENSE, FROM_REAL } from "./staged-folders";
import { forgetLadder } from "./ladder";
import { settleChosen } from "./decisions";

// Where a folder stands once a candidate answered it: identified, and the
// pipeline running on « rangé » — the strip's fifth cell, the first four done.
// « now » is the engine's own token for it, carried like every other value.
const RUNNING_NOW = "now";

// The tone a card wears once it went back through the pipeline.
const INFORMATIVE = "info";

// The list a continued card goes to, per staging world; the lists it comes
// from are `staged-folders.ts`'s. Named because the pairing is the decision.
const TO_REAL = "movingReel";
const TO_DENSE = "moving";
const SCRAPING_LABEL = "Scraping";          // french-ok: a carried fixture value

// The rung state of a folder the operator set aside: the contract's own token.
const ASIDE = "aside";

/**
 * Puts one folder back through the pipeline under the candidate chosen.
 *
 * FROM WHEREVER IT IS QUEUED, and the list it leaves decides the list it
 * joins: a card released from the real world moves within the real world, and
 * one released from the dense world moves within it. A BLOCKED card is served
 * in both worlds, so it joins both « en cours » lists — it went to the dense
 * one alone, and under the real scenario the card chosen simply vanished.
 *
 * THE DECISION IT WAITED ON IS SETTLED with the candidate chosen, whether or
 * not a card stood for it: a decision « Corriger » created for a medium already
 * in flight has no « À traiter » card, and its choice must still be recorded.
 *
 * @param asked The folder, as the queue names it.
 * @param named The candidate chosen, or an empty string.
 * @returns Whether anything was continued.
 */
export function continueMedia(asked: string, named: string): boolean {
  const state = mockState();
  const decided = settleChosen(asked, named);
  const lists = [
    { from: FROM_REAL, to: [TO_REAL] },
    { from: FROM_DENSE, to: [TO_DENSE] },
    { from: FROM_BLOCKED, to: [TO_REAL, TO_DENSE] },
  ] as const;
  for (const { from, to } of lists) {
    const found = state[from].find((card) => card.title === asked);
    if (found === undefined) continue;
    state[from] = state[from].filter((card) => card !== found);
    // A folder set aside and then resolved does not carry its aside rung
    // into the pipeline: its ladder is laid again from where it now stands.
    if (state.journeyStages[found.title]?.some((rung) => rung.state === ASIDE)) forgetLadder(found.title);
    for (const list of to) {
      state[list] = [
        {
          ...found,
          title: named === "" ? found.title : named,
          strip: [1, 1, 1, 1, RUNNING_NOW],
          chip: { tone: INFORMATIVE, text: SCRAPING_LABEL },
        },
        ...state[list],
      ];
    }
    return true;
  }
  return decided;
}
