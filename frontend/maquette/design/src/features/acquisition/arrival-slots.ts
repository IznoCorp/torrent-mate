// Where an arrival sits in « En cours » — by the state of its ladder, never by
// where it came from (ruling 7: the section is a function of the state).
//
// An arrival is an acquisition card (ruling 2). One stopped for his hand joins
// the blocked section; one in the library, its last rung still to come, joins
// what was shelved today; any other is on its way.
import { type QueueCard } from "../../lib/engine-queue";

/** The three sections of « En cours » an arrival can join. */
export type ArrivalSection = { blocked: QueueCard[]; inFlight: QueueCard[]; doneToday: QueueCard[] };

// The rung « rangé »: an arrival past it is in the library.
const SHELVED = "shelved";

/**
 * Sorts the arrivals into the sections of « En cours ».
 *
 * @param arrivals The arrival cards, each on its ladder.
 * @returns The cards each section gains.
 */
export function slotArrivals(arrivals: QueueCard[]): ArrivalSection {
  const section: ArrivalSection = { blocked: [], inFlight: [], doneToday: [] };
  for (const card of arrivals) {
    const ladder = card.ladder ?? [];
    if (ladder.some((rung) => rung.state === "blocked")) section.blocked.push(card);
    else if (ladder.some((rung) => rung.rung === SHELVED && rung.state === "done")) section.doneToday.push(card);
    else section.inFlight.push(card);
  }
  return section;
}
