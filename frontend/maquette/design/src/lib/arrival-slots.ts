// Where an arrival sits in Acquisition — by the state of its ladder, never by
// where it came from (ruling 7: the section is a function of the state).
//
// An arrival is an acquisition card (ruling 2). One stopped — for his hand, or
// for an external cause the engine lifts on its own (Q7), or closed and not yet
// seen (Q8, Q9) — is « À traiter »'s; one still on its way is « En vol »'s; one in the library, its
// last rung still to come, has left both — what arrived reads in the
// Médiathèque's « Récents ». One he set aside is « Mis de côté »'s, folded at
// the end of « À traiter » and outside everything it counts (ruling 16).
import { type QueueCard } from "./engine-queue";
import { isSetAside } from "./set-aside";

/** The three lists an arrival can join. */
export type ArrivalSection = { blocked: QueueCard[]; inFlight: QueueCard[]; setAside: QueueCard[] };

// The rung « rangé »: an arrival past it is in the library.
const SHELVED = "shelved";

/**
 * Whether a card stands in « À traiter » (Q7): a rung stopped for his hand
 * (`blocked`), a rung the ENGINE classifies as stopped — `resumes` set, an
 * external cause it lifts on its own — or a closure not yet seen. A rung merely
 * queued (a maintenance run, the supervisor's bound) carries no `resumes`: it
 * waits in « En cours ». The engine decides; no token list is read here.
 *
 * @param card A card of any list of the queue's answer.
 * @returns True when the card is a block or an unseen closure.
 */
export function isBlock(card: QueueCard): boolean {
  if (card.closure != null) return true;
  return (card.ladder ?? []).some((rung) => rung.state === "blocked" || rung.resumes != null);
}

/**
 * Sorts the arrivals into the lists that draw them.
 *
 * @param arrivals The arrival cards, each on its ladder.
 * @returns The cards each list gains; a shelved arrival joins neither.
 */
export function slotArrivals(arrivals: QueueCard[]): ArrivalSection {
  const section: ArrivalSection = { blocked: [], inFlight: [], setAside: [] };
  for (const card of arrivals) {
    const ladder = card.ladder ?? [];
    if (isSetAside(card)) section.setAside.push(card);
    else if (isBlock(card)) section.blocked.push(card);
    else if (!ladder.some((rung) => rung.rung === SHELVED && rung.state === "done")) section.inFlight.push(card);
  }
  return section;
}

/**
 * Every card « À traiter » counts: EVERY block wherever the queue's answer holds
 * it (Q7) — what the queue has stopped, the arrivals stopped on their ladder,
 * and the cards in flight stopped by an external cause — never one he set
 * aside. ONE derivation, read by the tab, its count, the bar's badge and the
 * season pointer's landing (§13); « En cours » reads its complement.
 *
 * ONE CARD PER MEDIUM: an in-flight row whose arrival is drawn already is the
 * arrival's.
 *
 * @param queue The queue's answer.
 * @returns The cards, in the order the queue answers them.
 */
export function todoCards(queue: { blocked: QueueCard[]; arrivals: QueueCard[]; inFlight: QueueCard[] }): QueueCard[] {
  const arrivals = slotArrivals(queue.arrivals).blocked;
  const inFlight = queue.inFlight.filter((row) => !isSetAside(row) && isBlock(row)
    && !queue.arrivals.some((arrival) => sameMedium(row, arrival)));
  return [...queue.blocked.filter((card) => !isSetAside(card)), ...arrivals, ...inFlight];
}

/**
 * Every card « Mis de côté » holds: what he set aside, from the queue and from
 * the arrivals. Read by the folded section alone — it counts for nothing else.
 *
 * @param queue The queue's answer.
 * @returns The cards, in the order the section draws them.
 */
export function setAsideCards(queue: { blocked: QueueCard[]; arrivals: QueueCard[]; inFlight: QueueCard[] }): QueueCard[] {
  return [...queue.blocked.filter(isSetAside), ...slotArrivals(queue.arrivals).setAside];
}

// The episode a card's subtitle opens with, when it names one.
const EPISODE = /S\d+E\d+/;
// How the key spells a season and an episode: « S03 », « E07 ».
const SEASON_MARK = "S";
const EPISODE_MARK = "E";
const DIGITS = 2;
const KEY_SEPARATOR = "|";

/** What an acquisition is named by: its title, and the season or episode it is of. */
export type AcquisitionNamed = Pick<QueueCard, "title" | "season" | "episode">;

/**
 * The key an acquisition is named by — what `absorbedBy` names, what its
 * ladder and its journey are held under.
 *
 * COMPOSED FROM THE SERVED FIELDS, never from the line (DECIDED 5): the title,
 * then the season and the episode the engine's wanted row holds. A card that
 * names no season is named by its title alone, as every acquisition was before.
 *
 * @param card The acquisition.
 * @returns « Silo|S03 », « Silo|S03E07 », or the title.
 */
export function acquisitionKey(card: AcquisitionNamed): string {
  if (card.season == null) return card.title;
  const pad = (value: number) => String(value).padStart(DIGITS, "0");
  const episode = card.episode == null ? "" : EPISODE_MARK + pad(card.episode);
  return card.title + KEY_SEPARATOR + SEASON_MARK + pad(card.season) + episode;
}

/**
 * Whether two cards name the same medium: one provider identifier shared, and
 * the same season and episode.
 *
 * BY PROVIDER IDENTITY, NEVER BY TITLE ALONE, and a seed spells one identifier
 * as a number and another as a string. The episode keeps two episodes of one
 * series apart: two torrents, two cards. Where both cards carry the served
 * season, the fields decide; the line is read only where a card carries none.
 *
 * @param one A card.
 * @param other Another card.
 * @returns True when both are the same medium.
 */
function sameMedium(one: QueueCard, other: QueueCard): boolean {
  const own = one.ids as Record<string, unknown> | null;
  const identifiers = other.ids as Record<string, unknown> | null;
  if (own == null || identifiers == null) return false;
  const shared = Object.entries(own).some(([provider, value]) => value != null
    && identifiers[provider] != null && String(identifiers[provider]) === String(value));
  if (one.season != null && other.season != null)
    return shared && one.season === other.season && (one.episode ?? null) === (other.episode ?? null);
  const episode = (card: QueueCard) => card.secondaryLine.match(EPISODE)?.[0] ?? "";
  return shared && episode(one) === episode(other);
}

/**
 * Every card on its way, before anything is absorbed: what the queue has in
 * flight, and the arrivals on their way — one card per medium.
 *
 * ONE CARD PER MEDIUM. The queue's in-flight row and the arrival of the same
 * torrent are two answers about one medium; drawn both, the tab counts one
 * torrent twice. The arrival stands for both — it carries the ladder and who
 * asked — at the place the queue's row held.
 *
 * @param queue The queue's answer.
 * @returns The cards, in the order the tab draws them.
 */
function onTheirWay(queue: { inFlight: QueueCard[]; arrivals: QueueCard[] }): QueueCard[] {
  const arrivals = slotArrivals(queue.arrivals).inFlight;
  const drawn = queue.inFlight.map((row) => arrivals.find((arrival) => sameMedium(row, arrival)) ?? row);
  return [...drawn, ...arrivals.filter((arrival) => !drawn.includes(arrival))];
}

/**
 * Every card « En cours » holds — « En vol » alone: the cards on their way,
 * less every one a whole season's recovery COVERS and every block (Q7). ONE derivation, read by the
 * tab, its count and every surface that asks what is on its way (§13).
 *
 * THE ABSORPTION READS THE SERVED POINTER (DECIDED 5): a card whose
 * `absorbedBy` names the acquisition covering it is not drawn; the season's
 * card covers it (Q6), and once that recovery has ended its episodes are not
 * revived by the interface — the engine re-enqueues what it is still short of
 * as ORDINARY cards, which carry no pointer. No label is compared.
 *
 * @param queue The queue's answer.
 * @returns The cards, in the order the tab draws them.
 */
export function inFlightCards(queue: { inFlight: QueueCard[]; arrivals: QueueCard[] }): QueueCard[] {
  // A BLOCK IS NOT ON ITS WAY (Q7): « À traiter » draws it, whichever list holds it.
  return onTheirWay(queue).filter((card) => card.absorbedBy == null && !isBlock(card));
}

/**
 * The tab of Acquisition that holds a live acquisition's card NOW — « En
 * cours » while on its way, « À traiter » while stopped (Q7) — or
 * nothing once it has left both.
 *
 * @param queue The queue's answer.
 * @param key The acquisition's key.
 * @returns `now`, `todo`, or undefined.
 */
export function tabHolding(
  queue: { inFlight: QueueCard[]; arrivals: QueueCard[]; blocked: QueueCard[] }, key: string,
): "now" | "todo" | undefined {
  if (inFlightCards(queue).some((card) => acquisitionKey(card) === key)) return "now";
  return todoCards(queue).some((card) => acquisitionKey(card) === key) ? "todo" : undefined;
}

/**
 * Every acquisition still live — « En cours »'s cards and « À traiter »'s: what
 * the season's row reads to say « Demandée » until the library (Q5). ONE
 * derivation with « En cours » (§13): a card shelved has left both.
 *
 * @param queue The queue's answer.
 * @returns The cards.
 */
export function liveCards(queue: { inFlight: QueueCard[]; arrivals: QueueCard[]; blocked: QueueCard[] }): QueueCard[] {
  return [...inFlightCards(queue), ...todoCards(queue)];
}
