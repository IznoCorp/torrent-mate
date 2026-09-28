// WHICH SEASONS OF A MEDIUM ARE ASKED ONCE — « demandée » on the season's row.
//
// A season of a series nobody follows is a ONE-OFF acquisition (round 10 Q2):
// the ask queues one card, asked by the account (`Requester.via` = `request`),
// and begins no follow. So nothing the panel or the sheet draws of the follow
// moves, and the surface pressed would read exactly as before — the act still
// offered, a second tap one tap away. While that card lives in the queue the
// season's row says « demandée » and withdraws the act.
//
// READ FROM THE QUEUE THE SERVER ANSWERS, never remembered by the interface:
// the card is the fact, so the mark goes when the card does.
//
// THE SEASON IS READ OFF THE CARD'S `secondaryLine` (« S03 »), which is fragile:
// the queue card carries no season field, a demand filed beside the one-off.
import { useAcquisitionQueue, type AcquisitionQueue } from "../../lib/queue";
import { useStoreContent } from "../../lib/store-access";

// The contract's token for a season asked once, in the application.
const ASKED_ONCE = "request";
// A one-off card's line names its season alone: « S03 ».
const SEASON_LINE = /^S(\d+)$/;

/**
 * The seasons of one medium a one-off acquisition is asked for.
 *
 * @param queue The queue as the server answered it.
 * @param title The medium, as the queue names it.
 * @returns Their numbers, empty when none is asked.
 */
export function askedSeasons(queue: AcquisitionQueue | undefined, title: string): number[] {
  const seasons: number[] = [];
  for (const card of queue?.inFlight ?? []) {
    if (card.title !== title || card.requester?.via !== ASKED_ONCE) continue;
    const line = SEASON_LINE.exec(card.secondaryLine ?? "");
    if (line) seasons.push(Number(line[1]));
  }
  return seasons;
}

/**
 * The seasons of one medium asked once, for a surface drawing its rows.
 *
 * @param title The medium.
 * @returns Their numbers, redrawn when the queue is read again.
 */
export function useAskedSeasons(title: string): number[] {
  const scenario = useStoreContent((content) => (content.state.scen === "loaded" ? "loaded" : ""));
  const { data } = useAcquisitionQueue(scenario);
  return askedSeasons(data, title);
}
