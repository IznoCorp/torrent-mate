// THE THREE SHAPES A SUGGESTION IS DRAWN IN — a row, a poster, a deck card.
//
// Découvrir offers one medium three ways and the choice is the reader's, so the
// three emitters live together: what changes between them is the shape, and
// nothing else. They were the dying engine's; they move here with the feed
// because a suggestion is Acquisitions' subject.
//
// MARKUP IS TRANSPLANTED, NOT TRANSLATED: same tags, same classes, same
// `data-*`, so the document-level delegation and four harness rules keep
// reading exactly what they read before. The card STATES which panel it
// addresses and never how to build it.
//
// THE SHARED EMITTERS ARE CALLED, NEVER COPIED. The engine's `cardHTML` draws
// every card and `ui/tile.ts` every tile in this application; a copy here would
// be a second definition of one shape, and the rows they emit carry the `data-*`
// the delegation reads.
import { icons } from "../../lib/shell-doors";
import i18next from "i18next";
import { posterArtwork } from "../../lib/engine-drawing";
import { escapeHtml, svgIcon } from "../../lib/markup-text";
import { mediumCardMarkup } from "./card-markup";
import { richTextMarkup } from "./rich-text";
import { posterArtworkMarkup } from "../../ui/poster";
import { tileMarkup } from "../../ui/tile";
import { deckCaption, deckCardFrame, deckHint, deckMeta, deckPoster, deckReason, deckTitle, suggestionBack, suggestionWrap } from "./variants";

/** One suggestion, as the reserve answers it. */
export type Suggestion = {
  t: string;
  y: string;
  k: string;
  note: number | string;
  why: unknown;
  poster?: string | null;
  /** The poster at full-screen definition, for the deck's card — null when none was taken. */
  posterHighDefinition?: string | null;
  /** The provider identifiers — null for a title no sheet stands behind. */
  ids?: Record<string, number | string> | null;
};

const say = (key: string, values?: Record<string, unknown>) =>
  i18next.t(`discover.${key}`, values ?? {});

/**
 * A suggestion as a LIST ROW, wrapped in what a sideways swipe reveals.
 *
 * Args:
 *     suggestion: The suggestion.
 *     position: Its index into the reserve — what the panel and the dismissal
 *         both address it by.
 *
 * Returns:
 *     The row's markup.
 */
export function suggestionRow(suggestion: Suggestion, position: number): string {
  const dismiss = say("notInterested");
  return `<div class="${suggestionWrap()}" data-part="suggestion/wrap" data-dismissable="${position}">
      <div class="${suggestionBack()}">
        <span>${svgIcon(icons.x)}${dismiss}</span>
        <span>${dismiss}${svgIcon(icons.x)}</span>
      </div>
      ${mediumCardMarkup({
        title: suggestion.t,
        k: suggestion.k === "Film" ? "movie" : "show",
        secondaryLine: `${suggestion.y} · ${suggestion.k}`,
        note: suggestion.note,
        reason: suggestion.why,
        panel: `sug:${position}`,
        poster: suggestion.poster,
        ids: suggestion.ids,
      })}
    </div>`;
}

/**
 * A suggestion as a POSTER, in the gallery every other gallery is drawn like.
 *
 * Args:
 *     suggestion: The suggestion.
 *     position: Its index into the reserve.
 *
 * Returns:
 *     The tile's markup.
 */
export function suggestionTile(suggestion: Suggestion, position: number): string {
  return tileMarkup({
    title: suggestion.t,
    subtitle: `${suggestion.y} · ${suggestion.k}`,
    artwork: posterArtwork(icons, suggestion.poster, suggestion.t, suggestion.k === "Film" ? "movie" : "show"),
    badge: { tone: "overlay", text: String(suggestion.note) },
    // The sheet before the panel: the registry answers the first registered
    // key in attribute order, and `data-dismissable` is a gesture's marker
    // rather than a verb, so it answers nothing.
    attributes: {
      "data-dismissable": position,
      "data-mediasheet": suggestion.t,
      "data-panel": `sug:${position}`,
    },
  });
}

/**
 * A suggestion as a DECK CARD — one card fills the surface, the next ones stack
 * behind it.
 *
 * Tapping the card opens the sheet; a swipe either way dismisses it, exactly as
 * in the list, and the next card rises from the deck; a long press opens the
 * panel, exactly as in a gallery.
 *
 * Args:
 *     suggestion: The suggestion.
 *     position: Its index into the reserve.
 *     depth: How far back in the pile it sits — 0 is the one being read.
 *
 * Returns:
 *     The card's markup.
 */
export function deckCard(
  suggestion: Suggestion,
  position: number,
  depth: number,
): string {
  const escape = escapeHtml;
  const poster = suggestion.posterHighDefinition
    ? `<img src="${suggestion.posterHighDefinition}" alt="" loading="lazy">`
    : posterArtworkMarkup(posterArtwork(icons, suggestion.poster, suggestion.t, suggestion.k === "Film" ? "movie" : "show"));
  // THE GESTURE LABELS BELONG TO THE TOP CARD ALONE — it is the only one a
  // finger can reach, and `advanceDeck` moves them with the place rather than
  // with the card.
  const hints =
    depth === 0
      ? `<span class="${deckHint({ side: "left" })}">${say("skip")}</span>` +
        `<span class="${deckHint({ side: "right" })}">${say("notInterested")}</span>`
      : "";
  return `<article class="${deckCardFrame()}" data-part="deck/card" data-deck="${position}" data-depth="${depth}" data-panel="sug:${position}">
      <button class="p ${deckPoster()}" data-mediasheet="${escape(suggestion.t)}" aria-label="Fiche de ${escape(suggestion.t)}">
        ${poster}
        <span class="cap ${deckCaption()}">
          <span class="t ${deckTitle()}" data-part="deck/title">${escape(suggestion.t)}</span>
          <span class="m ${deckMeta()}">${escape(suggestion.y)} · ${escape(suggestion.k)} · ${escape(String(suggestion.note))}${say("onTmdb")}</span>
          <span class="why ${deckReason()}">${richTextMarkup(suggestion.why)}</span>
        </span>
      </button>
      ${hints}
    </article>`;
}

/** The gesture labels the card that takes the top place has to inherit. */
export function deckHints(): string {
  return (
    `<span class="${deckHint({ side: "left" })}">${say("skip")}</span>` +
    `<span class="${deckHint({ side: "right" })}">${say("notInterested")}</span>`
  );
}
