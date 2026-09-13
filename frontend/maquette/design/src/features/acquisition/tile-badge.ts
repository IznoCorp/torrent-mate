// Which badge a follow's tile wears over its poster.
//
// THE TONE A FOLLOW'S STATUS NAMES is the page's vocabulary, so it is read here
// and the tile only hears whether its badge carries a fill. A rating's `note`
// tone reads over the picture on the neutral scrim. Every status tone — `muted`,
// `pending`, `acquiring` and the rest — was drawn with a fill naming a custom
// property no stylesheet declares, so it has always painted none, and it still
// paints none: the badge is its ring and its figure.
import type { TileBadgeTone } from "../../ui/variants";

/**
 * The tile's badge for a status badge.
 *
 * @param badge The status badge, or null when the follow has none.
 * @returns The tile's badge, or null.
 */
export function tileBadgeOf(
  badge: { tone: string; txt?: string } | null | undefined,
): { tone?: TileBadgeTone; text: string } | null {
  if (!badge) return null;
  return { tone: badge.tone === "note" ? "overlay" : undefined, text: String(badge.txt) };
}
