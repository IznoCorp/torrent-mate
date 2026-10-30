// WHICH SEASONS OF A MEDIUM ARE BEING RECOVERED WHOLE — « Demandée » on the
// season's row, on the media sheet and on the follow panel (Q5).
//
// A WHOLE SEASON'S RECOVERY IS ONE ACQUISITION CARD (the season named, no
// episode), followed or not, asked by a person or launched by the engine. While
// that card is live — on its way, arrived in the staging area, or stopped for his
// hand in « À traiter » — the row says « Demandée » and withdraws the act; it
// goes when the card is shelved, and the fraction then reads the library.
//
// READ FROM THE ONE DERIVATION « En cours » reads (`liveCards`, §13), never from
// one list filtered on one requester, and the season from the card's served
// `season` field, never off its line (DECIDED 5).
import { liveCards } from "../../lib/arrival-slots";
import { useAcquisitionQueue, type AcquisitionQueue } from "../../lib/queue";
import { useStoreContent } from "../../lib/store-access";

// The contract's token for an acquisition the engine launched on its own.
const AUTOMATIC = "automatic";

/**
 * The seasons of one medium a whole-season recovery is live for.
 *
 * @param queue The queue as the server answered it.
 * @param title The medium, as the queue names it.
 * @returns Each season recovered, and whether the engine launched it (Q19).
 */
export function askedSeasons(queue: AcquisitionQueue | undefined, title: string): Map<number, boolean> {
  const seasons = new Map<number, boolean>();
  if (queue === undefined) return seasons;
  for (const card of liveCards(queue)) {
    if (card.title !== title || card.season == null || card.episode != null) continue;
    seasons.set(card.season, card.trigger === AUTOMATIC);
  }
  return seasons;
}

/**
 * The seasons of one medium being recovered whole, for a surface drawing its rows.
 *
 * @param title The medium.
 * @returns Each season recovered and whether the engine launched it, redrawn
 *     when the queue is read again.
 */
export function useAskedSeasons(title: string): Map<number, boolean> {
  const scenario = useStoreContent((content) => (content.state.scen === "loaded" ? "loaded" : ""));
  const { data } = useAcquisitionQueue(scenario);
  return askedSeasons(data, title);
}
