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

/**
 * Every card « En cours » holds — « En vol » alone: what the queue has in
 * flight, and the arrivals on their way. ONE derivation, read by the tab and
 * its count (§13).
 *
 * @param queue The queue's answer.
 * @returns The cards, in the order the tab draws them.
 */
export function inFlightCards(queue: { inFlight: QueueCard[]; arrivals: QueueCard[] }): QueueCard[] {
  return [...queue.inFlight, ...slotArrivals(queue.arrivals).inFlight];
}
