// « Suivre », PROPOSED on an arrival (ruling 1) — never done unasked.
//
// An arrival creates a punctual acquisition, never a follow. On the card of an
// arrival that is an IDENTIFIED SERIES nobody follows, the interface offers the
// follow; nothing is followed until it is tapped. ONE derivation, read by the
// card's foot and by its panel (one card, one behaviour).

/** What the offer reads of a card: who asked for it, and its identity. */
type Offered = { requester?: unknown; ids?: Record<string, unknown> | null };

/** What the offer reads of a follow: its identity. */
type Followed = { ids?: Record<string, unknown> | null };

// A series is known by its TVDB identifier — TVDB is the series provider; a
// film carries none (and a card without identity carries nothing to follow).
const SERIES_PROVIDER = "tvdb";

/**
 * Whether a card is offered « Suivre ».
 *
 * @param card The card.
 * @param follows Every follow the operator has.
 * @returns True for an arrival of an identified series no follow shares an
 *     identifier with — by provider identity, never by title.
 */
export function followOffered(card: Offered, follows: Followed[]): boolean {
  const ids = card.ids;
  if (card.requester === undefined || ids == null || ids[SERIES_PROVIDER] == null) return false;
  return !follows.some((follow) => Object.entries(follow.ids ?? {}).some(([provider, value]) =>
    value != null && ids[provider] != null && String(ids[provider]) === String(value)));
}
