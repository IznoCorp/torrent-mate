// The rows a list draws around its cards — the swipe row and the selection row,
// drawn as markup.
//
// THEY KNOW NO DOMAIN (invariant 10). A swipe row wraps whatever row it is given
// and uncovers whatever actions its caller wrote; a selection row takes a title,
// a line, the artwork, the check and the attributes the caller's delegation
// reads. What an action does is the caller's, never the row's.
//
// MARKUP, NOT ELEMENTS, for the tile's reason (`ui/tile.ts`): the lists that hold
// these rows compose them as strings, and the windowed one compares each row's
// string to decide whether to redraw it.
import { escapeMarkup } from "./markup";
import { posterArtworkMarkup, type Artwork } from "./poster";
import { attributesMarkup, type MarkupAttributes } from "./tile";
import {
  cardSubtitle,
  cardTitle,
  selectionCheck,
  selectionRow,
  selectionRowText,
  swipeActions,
  swipeRow,
  swipeSide,
} from "./variants";

/**
 * A row that slides aside to uncover its actions.
 *
 * THE RIGHT DRAWER IS ALWAYS THERE, the left one only when there is something to
 * put in it: the gesture measures a drawer by the actions it holds, and a
 * direction with no drawer does not open.
 *
 * @param row The row's own markup.
 * @param right The actions the row uncovers by travelling left.
 * @param left The actions it uncovers by travelling right, if there are any.
 * @returns The swipe row's markup.
 */
export function swipeRowMarkup(row: string, right: string, left?: string): string {
  return `<div class="${swipeRow()}" data-part="swipe"><div class="${swipeActions()}">${
    left ? `<div class="${swipeSide({ edge: "left" })}" data-part="swipe/side" data-side="left">${left}</div>` : ""
  }<div class="${swipeSide({ edge: "right" })}" data-part="swipe/side" data-side="right">${right}</div></div>${row}</div>`;
}

/**
 * A row in selection mode.
 *
 * SELECTION WORKS IN BOTH MODES OF A LIST, which is why this row exists: a
 * selection that could be entered in list mode with nothing selectable is worse
 * than no selection at all.
 *
 * @param rowContent The title, the line under it, the artwork, the check's icon
 *     markup and the attributes the caller's delegation reads.
 * @returns The row's markup.
 */
export function selectionRowMarkup({
  title,
  subtitle,
  artwork,
  check,
  attributes,
}: {
  title: string;
  subtitle: string;
  artwork: Artwork;
  check: string;
  attributes: MarkupAttributes;
}): string {
  return `<button class="${selectionRow()}" data-part="selection/row"${attributesMarkup(attributes)}>
        <span class="${selectionCheck({ within: "row" })}" data-part="selection/check">${check}</span>
        <span class="poster" data-part="card/poster">${posterArtworkMarkup(artwork)}</span>
        <span class="${selectionRowText()}"><span class="${cardTitle()}" data-part="card/title" title="${escapeMarkup(title)}">${escapeMarkup(title)}</span><span class="${cardSubtitle()}" data-part="card/subtitle">${escapeMarkup(subtitle)}</span></span>
      </button>`;
}
