// One acquisition ITEM: a medium and, for a series, its episode — what a
// follow waits for, so what one card stands for (ruling 1: one acquisition per
// episode).
//
// BY PROVIDER IDENTITY, NEVER BY TITLE, and the episode read off the card's
// `secondaryLine` — the only place a queue card carries it today. That is
// fragile, and said: a line reworded loses the episode. The backend is asked for
// the field on the card (DESIGN § 6.2).
import type { components } from "../../contract/types";

type QueueCard = components["schemas"]["QueueCard"];

// A season and an episode, as a card's line spells them.
const EPISODE = /S\d+E\d+/i;

/**
 * The episode a card's line names, upper-cased, or nothing for a film.
 *
 * @param card The card.
 * @returns « S01E02 », or an empty string.
 */
function episodeOf(card: QueueCard): string {
  return (card.secondaryLine.match(EPISODE)?.[0] ?? "").toUpperCase();
}

/**
 * Whether two cards stand for the same item.
 *
 * @param one A card.
 * @param other Another card.
 * @returns True when a provider identifier is shared and the episode is the same.
 */
export function sameItem(one: QueueCard, other: QueueCard): boolean {
  const own = one.ids as Record<string, unknown> | null;
  const second = other.ids as Record<string, unknown> | null;
  if (own == null || second == null) return false;
  // A seed spells one identifier as a number and another as a string.
  const shared = Object.entries(second).some(([provider, value]) => value != null
    && own[provider] != null && String(own[provider]) === String(value));
  return shared && episodeOf(one) === episodeOf(other);
}
