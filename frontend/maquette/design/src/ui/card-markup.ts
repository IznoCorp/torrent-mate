// The card, drawn as markup — the spelling of `ui/card.tsx`'s parts for the
// lists still composed as strings.
//
// IT KNOWS NO DOMAIN (invariant 10): a title, the lines under it, the picture or
// the folder at its left, a strip of steps, a foot, and the attributes its
// caller's delegation reads. Which panel a body addresses, what a poster opens
// and which chip a state earns are the caller's to say.
//
// MARKUP, NOT AN ELEMENT, for the tile's reason (`ui/tile.ts`): the lists that
// hold these cards compose them as strings, the swipe row wraps one, and the
// windowed list compares each row's string to decide whether to redraw it.
//
// THE PARTS' OWN FACTORIES, class for class, so the two spellings of one card
// cannot drift apart: what `ui/card.tsx` draws as an element this draws as text.
import type { StripState } from "./card";
import { escapeMarkup } from "./markup";
import { attributesMarkup, type MarkupAttributes } from "./tile";
import {
  actionButton,
  card,
  cardAnnotations,
  cardBody,
  cardCaption,
  cardContent,
  cardFolder,
  cardFolderLabel,
  cardFraction,
  cardFreshTag,
  cardMeta,
  cardOverview,
  cardRating,
  cardReason,
  cardStrip,
  cardSubtitle,
  cardTitle,
  cardTop,
  chip,
  posterFrame,
  stripDot,
  stripLabel,
  stripStep,
  type ChipTone,
} from "./variants";

/** What stands at a card's left: a poster that leads somewhere, or a folder. */
export type CardSide =
  | { poster: string; attributes: MarkupAttributes }
  | { folderIcon: string; folderLabel: string; attributes: MarkupAttributes };

/** Everything one card shows, each line already in the caller's words. */
export type CardMarkupContent = {
  title: string;
  side: CardSide;
  body: MarkupAttributes;
  attributes?: MarkupAttributes;
  subtitle?: string;
  /** The reason, as markup: it may carry emphasis the caller has escaped. */
  reason?: string;
  overview?: string;
  fraction?: string;
  chip?: { tone: string; label: string } | null;
  rating?: string;
  caption?: string;
  /** The word a card that has just arrived wears, or nothing. */
  fresh?: string;
  strip?: { state: StripState; label: string }[];
  foot?: { label: string; solid?: boolean; attributes: MarkupAttributes };
};

/**
 * An icon, as markup, at the stroke the drawing asks for.
 *
 * @param paths The icon's paths.
 * @param strokeWidth The stroke's width.
 * @returns The icon's markup.
 */
function iconMarkup(paths: string, strokeWidth: number): string {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

/**
 * The card's left: its poster, or its folder.
 *
 * @param side The poster's picture and control, or the folder's icon, word and control.
 * @returns The side's markup.
 */
function sideMarkup(side: CardSide): string {
  if ("poster" in side) {
    return `<button class="poster ${posterFrame()}" data-part="card/poster"${attributesMarkup(side.attributes)}>${side.poster}</button>`;
  }
  return `<button class="${cardFolder()}" data-part="card/folder"${attributesMarkup(side.attributes)}>${iconMarkup(side.folderIcon, 1.6)}<span class="${cardFolderLabel()}">${escapeMarkup(side.folderLabel)}</span></button>`;
}

/**
 * One card.
 *
 * TWO LINES OF STATE, because they answer two questions: the first says what the
 * medium is — how much of it is owned, what state it is in, how it is rated —
 * and the second annotates that state. Mixed on one line they competed for the
 * same row and the state stopped reading at a glance.
 *
 * @param content What the card shows and the attributes its controls carry.
 * @returns The card's markup.
 */
export function cardMarkup(content: CardMarkupContent): string {
  const state =
    (content.fraction ? `<span class="${cardFraction()}">${escapeMarkup(content.fraction)}</span>` : "") +
    (content.chip
      ? `<span class="${chip({ tone: content.chip.tone as ChipTone })}" data-part="chip" data-tone="${escapeMarkup(content.chip.tone)}">${escapeMarkup(content.chip.label)}</span>`
      : "") +
    (content.rating != null ? `<span class="${cardRating()}">${escapeMarkup(content.rating)}</span>` : "");
  const annotations =
    (content.caption ? `<span class="${cardCaption()}" data-part="card/caption">${escapeMarkup(content.caption)}</span>` : "") +
    (content.fresh ? `<span class="${cardFreshTag()}" data-part="card/fresh-tag">${escapeMarkup(content.fresh)}</span>` : "");
  const strip = content.strip
    ? `<div class="${cardStrip()}">${content.strip
        .map(
          (step) =>
            `<div class="${stripStep({ state: step.state })}"><span class="d ${stripDot({ state: step.state })}"></span><span class="l ${stripLabel()}">${escapeMarkup(step.label)}</span></div>`,
        )
        .join("")}</div>`
    : "";
  const foot = content.foot
    ? `<button class="${actionButton({ kind: "cardFoot", tone: content.foot.solid ? "solid" : "plain" })}" data-part="card/foot"${content.foot.solid ? ' data-solid=""' : ""}${attributesMarkup(content.foot.attributes)}>${escapeMarkup(content.foot.label)}</button>`
    : "";
  return `<div class="${card()}${content.fresh ? " fresh" : ""}" data-part="card"${attributesMarkup(content.attributes ?? {})}>
    ${sideMarkup(content.side)}
    <div class="${cardContent()}">
    <div class="${cardTop()}" data-part="card/top">
      <button class="${cardBody()}" data-part="card/body"${attributesMarkup(content.body)}>
        <span class="${cardTitle()}" data-part="card/title" title="${escapeMarkup(content.title)}">${escapeMarkup(content.title)}</span>
        ${content.subtitle ? `<span class="${cardSubtitle()}" data-part="card/subtitle">${escapeMarkup(content.subtitle)}</span>` : ""}
        ${content.reason ? `<span class="${cardReason()}" data-part="card/reason">${content.reason}</span>` : ""}
        ${content.overview ? `<span class="${cardOverview()}" data-part="card/overview">${escapeMarkup(content.overview)}</span>` : ""}
        ${state ? `<span class="${cardMeta()}" data-part="card/meta">${state}</span>` : ""}
        ${annotations ? `<span class="${cardAnnotations()}">${annotations}</span>` : ""}
      </button>
    </div>
    ${strip}
    ${foot}
    </div>
  </div>`;
}
