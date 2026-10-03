// The library's rows as the windowed list draws them: a tile in the gallery; in
// the list, a card inside a swipe row — or a selection row while a selection is
// being made.
//
// KEYED BY THE TITLE, never by the position. The index is the row's rank IN THE
// LISTING ON SCREEN, which the layer orders and filters: index 1 of « A → Z » is
// not index 1 of the source, and a tick read as a key into the source selected a
// different medium, which the delete dialog then named and destroyed.
//
// THE SELECTION IS READ WHEN A ROW IS DRAWN, from the store rather than from the
// render that scheduled it: the windowed list composes its rows after React has
// painted, and a tick taken in between is already on the row it redraws.
import { posterArtwork, type EngineDrawing } from "../../lib/engine-drawing";
import { escapeHtml, svgIcon } from "../../lib/markup-text";
import { libraryCardMarkup } from "./card-markup";
import { store } from "../../lib/store-access";
import { selectionRowMarkup, swipeRowMarkup } from "../../ui/rows";
import { tileMarkup } from "../../ui/tile";
import type { LibraryRow } from "./types";
import { swipeAction } from "../../ui/variants";
import { heldRights } from "../../lib/account";
import { libraryLine } from "./card-markup";

/** A row of the listing: the title, the line under it and, where the medium has one, its synopsis. */
type Row = LibraryRow & { k?: string };

/**
 * One tile of the gallery.
 *
 * @param reference What the engine publishes for drawing.
 * @param row The row.
 * @param index Its rank in the listing on screen.
 * @returns The tile's markup.
 */
export function libraryTileMarkup(reference: EngineDrawing, row: Row, index: number): string {
  const { selMode } = store.read().state;
  const selected = store.read().state.selected as Set<string>;
  return tileMarkup({
    title: row.title,
    subtitle: libraryLine(row),
    artwork: posterArtwork(reference.icons, row.poster, row.title, row.k),
    check: selMode ? svgIcon(reference.icons.check, 3) : undefined,
    // WHAT A TAP MEANS IS WRITTEN FIRST. The registry answers the first
    // registered key in ATTRIBUTE order, so the key a tap is FOR — the
    // selection while one is being made, the medium's sheet otherwise — comes
    // before `data-panel`, which the long press reaches. Written the other way
    // round, a tap on a tile opened the panel and nothing opened the medium.
    attributes: {
      "data-tile": index,
      // A ROW NOTHING IDENTIFIES IS NOT TICKED: the layer deletes by identity.
      ...(selMode
        ? row.ids
          ? { "aria-pressed": selected.has(row.title), "data-selected-title": row.title }
          : { "aria-disabled": "true" }
        : { "data-mediasheet": row.title }),
      "data-panel": `media:${row.title}`,
    },
  });
}

/**
 * One row of the list.
 *
 * @param reference What the engine publishes for drawing.
 * @param row The row.
 * @param index Its rank in the listing on screen.
 * @param removeLabel The removal action's label.
 * @returns The row's markup.
 */
export function libraryRowMarkup(
  reference: EngineDrawing,
  row: Row,
  index: number,
  removeLabel: string,
): string {
  const { selMode } = store.read().state;
  const selected = store.read().state.selected as Set<string>;
  if (selMode) {
    return selectionRowMarkup({
      title: row.title,
      subtitle: libraryLine(row),
      artwork: posterArtwork(reference.icons, row.poster, row.title),
      check: svgIcon(reference.icons.check, 3),
      attributes: row.ids
        ? { "data-tile": index, "data-selected-title": row.title, "aria-pressed": selected.has(row.title) }
        : { "data-tile": index, "aria-disabled": "true" },
    });
  }
  const card = libraryCardMarkup({ title: row.title, secondaryLine: libraryLine(row), overview: row.overview, poster: row.poster, ids: row.ids });
  // THE SWIPE DELETES, so it is offered to an account that may delete (§ 17):
  // without `library.delete` the row is the card alone — and so is a row no
  // provider identity names, since the layer deletes by identity (Q5 A).
  if (!heldRights().holds("library.delete") || !row.ids) return card;
  return swipeRowMarkup(
    card,
    `<button class="${swipeAction({ tone: "remove" })}" data-part="swipe/action" data-action="remove" data-swipeact="del" data-del="${escapeHtml(row.title)}">${svgIcon(reference.icons.trash)}${removeLabel}</button>`,
  );
}
