// A whole season's recovery, as the engine holds it: ONE acquisition of the
// season, and every episode of that season it covers.
//
// THE ENGINE ALREADY ABSORBS the open episode wanteds of the season into the
// season's row, with a pointer column `absorbed_by` (`acquisition_seasons.py`,
// `_wanted_store.py`); the layer answers what the contract asks it to serve
// (demand SR1): the season's card, and `absorbedBy` on every card it covers. A
// FOLLOWED series' ask used to queue no card at all — the one-off's guard was
// the only path that queued one (DESIGN maquette-season-recovery § 0.1 item 1).
import SEASONS from "../seeds/seasons.json";
import { mockState } from "../state";
import { acquisitionKey } from "../../lib/arrival-slots";
import { forgetLadder, ladderOf, rungIndex, stripPosition, type Position } from "./ladder";
import type { components } from "../../contract/types";

type QueueCard = components["schemas"]["QueueCard"];

// The lists an acquisition card lives in, one pair per world, and where an
// episode it covers can wait: in flight, or takeable.
const FLIGHT_LISTS = ["inFlight", "inFlightReel"] as const;
const COVERABLE_LISTS = [...FLIGHT_LISTS, "takeable"] as const;

// A strip's cell stopped: the card waits for his hand, in « À traiter ».
const BLOCKED = "blocked";

/**
 * Whether two cards share one provider identifier — the same series.
 *
 * @param one A card.
 * @param other Another card.
 * @returns True when an identifier is shared.
 */
function sameSeries(one: QueueCard, other: QueueCard): boolean {
  const own = (one.ids ?? {}) as Record<string, unknown>;
  const second = (other.ids ?? {}) as Record<string, unknown>;
  return Object.entries(second).some(([provider, value]) => value != null
    && own[provider] != null && String(own[provider]) === String(value));
}

/**
 * Whether a card is a whole season's acquisition.
 *
 * @param card The card.
 * @returns True for a season named with no episode.
 */
function isSeason(card: QueueCard): boolean {
  return card.season != null && card.episode == null;
}

/**
 * The season card a medium's recovery of one season holds, in flight, if any.
 *
 * @param title The medium.
 * @param season The season, 1-based.
 * @returns The card, or undefined.
 */
export function seasonCardOf(title: string, season: number): QueueCard | undefined {
  const state = mockState();
  return [...state.inFlight, ...state.inFlightReel, ...state.blocked]
    .find((card) => card.title === title && isSeason(card) && card.season === season);
}

/**
 * Writes the pointer on every card the season's recovery covers: an episode of
 * that season of that series, in flight or takeable (the engine's rule R5).
 *
 * @param season The season's card.
 * @returns How many cards it covers now.
 */
function absorbInto(season: QueueCard): number {
  const state = mockState();
  const key = acquisitionKey(season);
  let covered = 0;
  for (const list of COVERABLE_LISTS) {
    state[list] = state[list].map((card) => {
      if (card.episode == null || card.season !== season.season || !sameSeries(card, season)) return card;
      covered += 1;
      return { ...card, absorbedBy: key };
    });
  }
  return covered;
}

/**
 * A season's recovery asked for: ONE card for the season, followed or not, and
 * the episodes of that season it covers.
 *
 * ONE ITEM, ONE CARD: a second ask queues nothing more and says so — `reused`,
 * the engine's own answer (a 200 there).
 *
 * @param card The season's card, as the ask composes it.
 * @returns Whether a live recovery of that season was already there.
 */
export function recoverSeason(card: QueueCard): { reused: boolean } {
  const state = mockState();
  // EACH WORLD HOLDS ITS OWN LISTS: the dense world's recovery of a season is
  // not the real world's, so an ask is queued in every world that lacks it, and
  // answered `reused` only where every world already held it.
  const holds = (cards: QueueCard[]) => [...cards, ...state.blocked].some((one) => one.title === card.title
    && isSeason(one) && one.season === card.season);
  let reused = true;
  for (const list of FLIGHT_LISTS) {
    if (holds(state[list])) continue;
    state[list] = [card, ...state[list]];
    reused = false;
  }
  if (!reused) absorbInto(card);
  return { reused };
}

/**
 * Lifts a season's recovery, as it stood BEFORE the ask — a derivation, shown
 * as one: the dense world holds the recovery running, and the moment before
 * the finger's ask is posed, never seeded (RULINGS 7).
 *
 * @param title The medium.
 * @param season The season, 1-based.
 */
export function poseBeforeAsk(title: string, season: number): void {
  const state = mockState();
  const lifted = seasonCardOf(title, season);
  if (lifted === undefined) return;
  const key = acquisitionKey(lifted);
  for (const list of [...FLIGHT_LISTS, "blocked", "takeable"] as const) {
    state[list] = state[list]
      .filter((card) => card !== lifted && !(isSeason(card) && acquisitionKey(card) === key))
      .map((card) => (card.absorbedBy === key ? { ...card, absorbedBy: null } : card));
  }
  forgetLadder(key);
}

/**
 * Stands a season's card at one rung, until the layer is next reset.
 *
 * @param title The medium.
 * @param season The season, 1-based.
 * @param position Where its ladder stands.
 */
export function poseSeasonAt(title: string, season: number, position: Position): void {
  const card = seasonCardOf(title, season);
  if (card === undefined) return;
  const key = acquisitionKey(card);
  forgetLadder(key);
  ladderOf(key, position);
}

/**
 * Stops a season's card for his hand — it leaves « En cours » for
 * « À traiter », where it waits on the rung it had reached.
 *
 * @param title The medium.
 * @param season The season, 1-based.
 */
export function poseSeasonBlocked(title: string, season: number): void {
  const state = mockState();
  const card = seasonCardOf(title, season);
  if (card === undefined) return;
  const strip = (card.strip ?? []).map((value) => (value === "now" ? BLOCKED : value));
  const { chip, ...stopped } = card;
  void chip;
  for (const list of FLIGHT_LISTS) state[list] = state[list].filter((one) => one !== card);
  state.blocked = [{ ...stopped, strip }, ...state.blocked];
  forgetLadder(acquisitionKey(card));
  const position = stripPosition(strip);
  if (position !== undefined) ladderOf(acquisitionKey(card), position);
}

/**
 * Makes a season's recovery the engine's own — its rule R4 launched it —
 * until the layer is next reset (demand SR5: the engine records no trigger yet).
 *
 * @param title The medium.
 * @param season The season, 1-based.
 */
export function poseAutomatic(title: string, season: number): void {
  const state = mockState();
  for (const list of [...FLIGHT_LISTS, "blocked"] as const) {
    state[list] = state[list].map((card) => (card.title === title && isSeason(card) && card.season === season
      ? { ...card, trigger: "automatic" } : card));
  }
}

/**
 * Ends a season's recovery, until the layer is next reset.
 *
 * - `closedShort`: the incomplete-pack fallback (#542) — the season's journey
 *   closes and the engine re-enqueues the episodes it is still short of, as
 *   ORDINARY cards: nothing covers them any more.
 * - `abandoned`: « Abandonner » on the season's journey — the card goes, and
 *   the episodes it covered go with it; the interface revives none of them.
 *
 * @param title The medium.
 * @param season The season, 1-based.
 * @param how How it ended.
 */
export function poseSeasonEnded(title: string, season: number, how: "closedShort" | "abandoned"): void {
  const state = mockState();
  const card = seasonCardOf(title, season);
  if (card === undefined) return;
  const key = acquisitionKey(card);
  for (const list of [...FLIGHT_LISTS, "blocked", "takeable"] as const) {
    state[list] = state[list]
      .filter((one) => one !== card && (how === "closedShort" || one.absorbedBy !== key))
      .map((one) => (one.absorbedBy === key ? { ...one, absorbedBy: null } : one));
  }
  forgetLadder(key);
}

/**
 * The season pack reaches the staging area — it JOINS the season's card, one
 * medium, one card (L22's merge), until the layer is next reset.
 *
 * @param title The medium.
 * @param season The season, 1-based.
 * @param release The pack's release name, its line's tail.
 */
export function poseSeasonArrived(title: string, season: number, release: string): void {
  const state = mockState();
  const card = seasonCardOf(title, season);
  if (card === undefined) return;
  const { requester, chip, ...pack } = card;
  void requester;
  void chip;
  forgetLadder(acquisitionKey(card));
  state.moving = [{ ...pack, secondaryLine: `${card.secondaryLine} · ${release}`, strip: [1, 1, "now", 0, 0] },
    ...state.moving];
}

// WHAT A SHELVED SEASON ADDED TO THE LIBRARY, keyed by the layer's state so a
// reset forgets it with everything else: per series, per season, its episodes.
const shelvedIn = new WeakMap<object, Map<string, Record<string, number[]>>>();

/**
 * The episodes a shelved recovery added to one series' library, per season.
 *
 * @param titles Every title the series is known under.
 * @returns The episodes by season, empty when nothing was shelved.
 */
export function shelvedEpisodes(titles: string[]): Record<string, number[]> {
  const held = shelvedIn.get(mockState());
  if (held === undefined) return {};
  const title = titles.find((one) => held.has(one)) ?? [...held.keys()].find((one) =>
    titles.some((known) => known.startsWith(`${one} (`)));
  return title === undefined ? {} : held.get(title) ?? {};
}

/**
 * The season reaches the library — its card's rung « rangé » done: the card
 * leaves, the episodes it covered with it, and the library holds every episode
 * of the season that aired, until the layer is next reset.
 *
 * @param title The medium.
 * @param season The season, 1-based.
 */
export function poseSeasonShelved(title: string, season: number): void {
  // THE EPISODES IT COVERED KEEP THEIR POINTER: covered, then shelved with their
  // season — their journey says where the season went (DESIGN § 1.4).
  const card = seasonCardOf(title, season);
  if (card !== undefined) {
    const state = mockState();
    for (const list of [...FLIGHT_LISTS, "blocked"] as const) state[list] = state[list].filter((one) => one !== card);
    forgetLadder(acquisitionKey(card));
  }
  const aired = ((SEASONS as Record<string, { season: number; aired: number }[]>)[title] ?? [])
    .find((one) => one.season === season)?.aired ?? 0;
  const state = mockState();
  const held = shelvedIn.get(state) ?? new Map<string, Record<string, number[]>>();
  shelvedIn.set(state, held);
  held.set(title, { ...held.get(title), [String(season)]: Array.from({ length: aired }, (_, index) => index + 1) });
}

/**
 * Takes one release out of a title's list — tried and abandoned, so the
 * release read no longer offers it (§14.1) — until the layer is next reset.
 *
 * @param title The medium.
 * @param name The release's name.
 */
export function poseReleaseTried(title: string, name: string): void {
  const state = mockState();
  state.triedReleases[title] = [...(state.triedReleases[title] ?? []), name];
}

/** The rung a season's card is searched on, while no release is found yet. */
export const SEARCHING: Position = { current: rungIndex("searched"), state: "now" };
