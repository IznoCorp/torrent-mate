// Where an arrival sits in Acquisition — by the state of its ladder, never by
// where it came from (ruling 7: the section is a function of the state).
//
// An arrival is an acquisition card (ruling 2). One stopped for his hand is
// « À traiter »'s; one still on its way is « En vol »'s; one in the library, its
// last rung still to come, has left both — what arrived reads in the
// Médiathèque's « Récents ».
import { type QueueCard } from "../../lib/engine-queue";

/** The two lists an arrival can join. */
export type ArrivalSection = { blocked: QueueCard[]; inFlight: QueueCard[] };

// The rung « rangé »: an arrival past it is in the library.
const SHELVED = "shelved";

/**
 * Sorts the arrivals into the lists that draw them.
 *
 * @param arrivals The arrival cards, each on its ladder.
 * @returns The cards each list gains; a shelved arrival joins neither.
 */
export function slotArrivals(arrivals: QueueCard[]): ArrivalSection {
  const section: ArrivalSection = { blocked: [], inFlight: [] };
  for (const card of arrivals) {
    const ladder = card.ladder ?? [];
    if (ladder.some((rung) => rung.state === "blocked")) section.blocked.push(card);
    else if (!ladder.some((rung) => rung.rung === SHELVED && rung.state === "done")) section.inFlight.push(card);
  }
  return section;
}

/**
 * Every card « À traiter » holds: what the queue has stopped, and the arrivals
 * stopped on their ladder. ONE derivation, read by the tab, its count and the
 * bar's badge (§13).
 *
 * @param queue The queue's answer.
 * @returns The cards, in the order the tab draws them.
 */
export function todoCards(queue: { blocked: QueueCard[]; arrivals: QueueCard[] }): QueueCard[] {
  return [...queue.blocked, ...slotArrivals(queue.arrivals).blocked];
}

// The episode a card's subtitle opens with, when it names one.
const EPISODE = /S\d+E\d+/;

/**
 * Whether two cards name the same medium: one provider identifier shared, and
 * the same episode when either names one.
 *
 * BY PROVIDER IDENTITY, NEVER BY TITLE ALONE, and a seed spells one identifier
 * as a number and another as a string. The episode keeps two episodes of one
 * series apart: two torrents, two cards.
 *
 * @param one A card.
 * @param other Another card.
 * @returns True when both are the same medium.
 */
function sameMedium(one: QueueCard, other: QueueCard): boolean {
  const own = one.ids as Record<string, unknown> | null;
  const theirs = other.ids as Record<string, unknown> | null;
  if (own == null || theirs == null) return false;
  const shared = Object.entries(own).some(([provider, value]) => value != null
    && theirs[provider] != null && String(theirs[provider]) === String(value));
  const episode = (card: QueueCard) => card.secondaryLine.match(EPISODE)?.[0] ?? "";
  return shared && episode(one) === episode(other);
}

/**
 * Every card « En cours » holds — « En vol » alone: what the queue has in
 * flight, and the arrivals on their way. ONE derivation, read by the tab and
 * its count (§13).
 *
 * ONE CARD PER MEDIUM. The queue's in-flight row and the arrival of the same
 * torrent are two answers about one medium; drawn both, the tab counts one
 * torrent twice. The arrival stands for both — it carries the ladder and who
 * asked — at the place the queue's row held.
 *
 * @param queue The queue's answer.
 * @returns The cards, in the order the tab draws them.
 */
export function inFlightCards(queue: { inFlight: QueueCard[]; arrivals: QueueCard[] }): QueueCard[] {
  const arrivals = slotArrivals(queue.arrivals).inFlight;
  const merged = queue.inFlight.map((row) => arrivals.find((arrival) => sameMedium(row, arrival)) ?? row);
  return [...merged, ...arrivals.filter((arrival) => !merged.includes(arrival))];
}
