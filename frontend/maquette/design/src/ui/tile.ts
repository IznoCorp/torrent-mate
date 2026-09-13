// The tile — one poster in a gallery, drawn as markup.
//
// IT KNOWS NO DOMAIN (invariant 10): a title, the line under it, the artwork, a
// badge or a check, and the attributes its caller's delegation reads. Which panel
// a tile addresses and what a tap on it opens are the caller's to say.
//
// MARKUP, NOT AN ELEMENT, because of where tiles are drawn: the windowed list
// compares each row's STRING to decide whether to redraw it, and the other
// galleries are composed as strings around it. The poster's artwork has the same
// spelling for the same reason (`ui/poster.tsx`).
//
// AT MOST ONE OVERLAY sits on the poster. The check belongs to selection mode,
// where the badge is not drawn, and the tile does not change at rest: the check
// exists only while a selection is being made.
import { escapeMarkup } from "./markup";
import { posterArtworkMarkup, type Artwork } from "./poster";
import { selectionCheck, tile, tileBadge, tilePoster, tileSubtitle, tileTitle, type TileBadgeTone } from "./variants";

/** The attributes an element carries for its reader, written out as given; an undefined one is left out. */
export type MarkupAttributes = Record<string, string | number | boolean | undefined>;

/**
 * Writes attributes into a start tag, each one escaped.
 *
 * @param attributes The attributes, in the order they are written.
 * @returns The attributes, each preceded by a space.
 */
export function attributesMarkup(attributes: MarkupAttributes): string {
  return Object.entries(attributes)
    .filter(([, value]) => value !== undefined)
    .map(([name, value]) => ` ${name}="${escapeMarkup(String(value))}"`)
    .join("");
}

/**
 * One tile.
 *
 * @param tileContent The title, the line under it, the artwork, whether the tile
 *     is muted, its badge, the check's icon markup while a selection is being made,
 *     and the attributes the caller's delegation reads.
 * @returns The tile's markup.
 */
export function tileMarkup({
  title,
  subtitle,
  artwork,
  muted,
  badge,
  check,
  attributes,
}: {
  title: string;
  subtitle: string;
  artwork: Artwork;
  muted?: boolean;
  badge?: { tone?: TileBadgeTone; text: string } | null;
  check?: string;
  attributes: MarkupAttributes;
}): string {
  const overlay =
    check !== undefined
      ? `<span class="${selectionCheck({ within: "tile" })}" data-part="selection/check">${check}</span>`
      : badge
        ? `<span class="${tileBadge({ tone: badge.tone })}" data-part="tile/badge">${escapeMarkup(badge.text)}</span>`
        : "";
  return `<button class="tile ${tile({ muted })}" data-part="tile"${attributesMarkup(attributes)}>
      <span class="${tilePoster({ muted })}">${posterArtworkMarkup(artwork)}</span>
      ${overlay}
      <span class="${tileTitle({ muted })}" data-part="tile/title">${escapeMarkup(title)}</span>
      <span class="fr ${tileSubtitle()}" data-part="tile/subtitle">${escapeMarkup(subtitle)}</span>
    </button>`;
}
