// A folder set aside: « Laisser tel quel » means LATER (ruling 6, placed by
// ruling 16).
//
// THE CARD IS KEPT, NEVER TAKEN OUT. Its files are still on the machine and
// still have to be dealt with, so leaving a folder as it is changes where its
// ladder stands and nothing else: the rung it was stopped on is set aside,
// dated today. The lists that draw it read that rung — the counted part of the
// queue loses it, the folded « Mis de côté » gains it.
//
// ITS OWN FILE because the queue's module is at its size ceiling; it is the
// optimistic half of one verb of that module, and only that module calls it.
import type { QueryClient } from "@tanstack/react-query";
import { today } from "./clock";
import { currentRung } from "./current-rung";
import type { Schemas } from "./contract-schemas";

type Card = Schemas["QueueCard"];
// The queue's answer, as this module reads it: lists of cards, whatever their names.
type Lists = Record<string, unknown>;

// The rung state of a card the operator set aside, the contract's own token.
const ASIDE = "aside";

/**
 * Whether a card was set aside by the operator.
 *
 * @param card The card.
 * @returns True when one of its rungs is set aside.
 */
export function isSetAside(card: { ladder?: { state: string }[] }): boolean {
  return (card.ladder ?? []).some((rung) => rung.state === ASIDE);
}

/**
 * The same card, set aside on the rung it stands on.
 *
 * @param card The card.
 * @returns The card, its current rung set aside and dated today — or the card
 *     as it was when it carries no ladder, or has passed every rung.
 */
function setAsideOn(card: Card): Card {
  const ladder = card.ladder;
  if (ladder === undefined || ladder.length === 0) return card;
  // THE RUNG IT STANDS ON, the card's own derivation — never the first rung
  // not done, which for a folder whose first rungs were never lived is « demandé ».
  const standing = currentRung(ladder);
  if (ladder[standing].state === "done") return card;
  return {
    ...card,
    ladder: ladder.map((rung, index) =>
      index === standing ? { rung: rung.rung, state: ASIDE, when: today() } : rung),
  };
}

/**
 * Sets one card aside in the cached queue, at once.
 *
 * IN EVERY LIST THE ANSWER CARRIES, not in two named ones: a title is queued in
 * one list only, so the card is set aside wherever it is, and this module need
 * not know what the queue calls its lists (invariant 10).
 *
 * @param queryClient The cache.
 * @param key The queue's key, scenario included.
 * @param title The card's own title, which is how the queue keys one.
 * @returns What the cache held before, so a refusal can put it back.
 */
export function setAsideInQueue<Queue extends Lists>(
  queryClient: QueryClient, key: unknown[], title: string,
): Queue | undefined {
  const queue = queryClient.getQueryData<Queue>(key);
  if (queue === undefined) return undefined;
  const aside = (value: unknown) => (Array.isArray(value)
    ? (value as Card[]).map((card) => (card.title === title ? setAsideOn(card) : card))
    : value);
  queryClient.setQueryData<Queue>(key, Object.fromEntries(
    Object.entries(queue).map(([name, value]) => [name, aside(value)])) as Queue);
  return queue;
}
