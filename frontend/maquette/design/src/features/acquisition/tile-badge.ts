// Which badge a follow's tile wears over its poster.
//
// THE TONE A FOLLOW'S STATUS NAMES is the page's vocabulary, so it is read here
// — the same `STATUS_TONE` its chip reads — and the tile only hears which of
// its declared tones to paint. A rating's `note` tone reads over the picture on
// the neutral scrim. Every status tone was drawn with a fill naming a custom
// property no stylesheet declared, so it painted none (B-498).
import type { TileBadgeTone } from "../../ui/variants";
import { STATUS_TONE } from "./follow-vocabulary";

/* The tones the tile draws; a status naming another is drawn neutral. */
const DRAWN: readonly TileBadgeTone[] = ["warning", "info", "waiting", "neutral"];

/**
 * The tile's badge for a status badge.
 *
 * @param badge The status badge, or null when the follow has none. Its tone is
 *     a follow status, or a tone already (`neutral`, `note`).
 * @returns The tile's badge, or null.
 */
export function tileBadgeOf(
  badge: { tone: string; txt?: string } | null | undefined,
): { tone?: TileBadgeTone; text: string } | null {
  if (!badge) return null;
  if (badge.tone === "note") return { tone: "overlay", text: String(badge.txt) };
  const tone = (STATUS_TONE[badge.tone] ?? badge.tone) as TileBadgeTone;
  return { tone: DRAWN.includes(tone) ? tone : "neutral", text: String(badge.txt) };
}
