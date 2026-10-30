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
import { stripColumns, type StripCell } from "./card";
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
  cardProgress,
  cardRating,
  cardReason,
  cardStrip,
  cardSubtitle,
  cardTitle,
  cardTop,
  chip,
  posterFrame,
  statusDot,
  stripDot,
  stripLabel,
  stripStep,
  type ChipTone,
  type StatusTone,
} from "./variants";

/** What stands at a card's left: a poster that leads somewhere, or a folder. */
export type CardSide =
  | { poster: string; attributes: MarkupAttributes }
  | { folderIcon: string; folderLabel: string; attributes: MarkupAttributes };

/**
 * One mark a card says beside its state: a toned chip, a coloured dot whose word
 * is its label, or a plain figure. The caller's attributes name it for its readers.
 */
export type CardMark = { label: string; tone?: ChipTone; dot?: StatusTone; attributes?: MarkupAttributes };

/** One option at a card's foot. */
export type CardFoot = { label: string; solid?: boolean; attributes: MarkupAttributes };

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
  /** Figures said on the state line, after the chip — a size, a ratio. */
  details?: CardMark[];
  caption?: string;
  /** Figures said on the annotation line, after the caption. */
  notes?: CardMark[];
  /** A byte count under way, from 0 to 1, and its words for a screen reader. */
  progress?: { value: number; label: string };
  /** The marks a card wears on a line of their own, under its annotations. */
  marks?: CardMark[];
  /** The word a card that has just arrived wears, or nothing. */
  fresh?: string;
  /** Who asked for it — the card's last text line (§12). */
  requester?: string;
  strip?: StripCell[];
  /** The option a section offers at the card's foot — or several, in order. */
  foot?: CardFoot | CardFoot[];
  /** The class several feet are laid on ONE line with, the caller's own; without
   * it they stack. */
  footRow?: string;
  /** The row a card with ONE foot lays its requester line in, beside it. */
  originRow?: string;
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
 * One mark, as markup.
 *
 * @param mark The mark: a chip when it has a tone, a dot when it has one, a figure otherwise.
 * @returns The mark's markup.
 */
function markMarkup(mark: CardMark): string {
  const { "data-part": part, ...rest } = mark.attributes ?? {};
  const attributes = attributesMarkup(rest);
  if (mark.tone !== undefined) {
    return `<span class="${chip({ tone: mark.tone })}" data-part="${escapeMarkup(part ?? "chip")}" data-tone="${mark.tone}"${attributes}>${escapeMarkup(mark.label)}</span>`;
  }
  if (mark.dot !== undefined) {
    // THE DOT'S WORD IS ITS LABEL, said to a screen reader; the eye reads it in the legend.
    return `<span class="${statusDot({ tone: mark.dot })}" data-part="${escapeMarkup(part ?? "card/dot")}" data-tone="${mark.dot}" role="img" aria-label="${escapeMarkup(mark.label)}"${attributes}></span>`;
  }
  return `<span class="${cardCaption()}" data-part="${escapeMarkup(part ?? "card/figure")}"${attributes}>${escapeMarkup(mark.label)}</span>`;
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
    (content.rating != null ? `<span class="${cardRating()}">${escapeMarkup(content.rating)}</span>` : "") +
    (content.details ?? []).map(markMarkup).join("");
  const annotations =
    (content.caption ? `<span class="${cardCaption()}" data-part="card/caption">${escapeMarkup(content.caption)}</span>` : "") +
    (content.fresh ? `<span class="${cardFreshTag()}" data-part="card/fresh-tag">${escapeMarkup(content.fresh)}</span>` : "") +
    (content.notes ?? []).map(markMarkup).join("");
  const progress = content.progress
    ? `<progress class="${cardProgress()}" data-part="card/progress" value="${content.progress.value}" max="1" aria-label="${escapeMarkup(content.progress.label)}"></progress>`
    : "";
  const marks = content.marks?.length
    ? `<span class="${cardMeta()}" data-part="card/marks">${content.marks.map(markMarkup).join("")}</span>`
    : "";
  const strip = content.strip
    ? `<div class="${cardStrip({ cells: stripColumns(content.strip) })}" data-part="card/strip">${content.strip
        .map(
          (step) =>
            `<div class="${stripStep({ state: step.state })}" data-part="card/step" data-state="${step.state}"><span class="d ${stripDot({ state: step.state })}"></span>${step.label === undefined ? "" : `<span class="l ${stripLabel()}">${escapeMarkup(step.label)}</span>`}</div>`,
        )
        .join("")}</div>`
    : "";
  const options = content.foot === undefined ? [] : Array.isArray(content.foot) ? content.foot : [content.foot];
  const foot = options
    .map((one) => `<button class="${actionButton({ kind: "cardFoot", tone: one.solid ? "solid" : "plain" })}" data-part="card/foot"${one.solid ? ' data-solid=""' : ""}${attributesMarkup(one.attributes)}>${escapeMarkup(one.label)}</button>`)
    .join("");
  // ONE FOOT AND A REQUESTER: the line goes beside the foot, not under the reason.
  const shared = Boolean(content.originRow && options.length === 1 && content.requester);
  const requester = content.requester
    ? `<span class="${cardCaption()}" data-part="card/requester" title="${escapeMarkup(content.requester)}">${escapeMarkup(content.requester)}</span>`
    : "";
  const footLine = shared
    ? `<div class="${content.originRow}">${requester}${foot}</div>`
    : content.footRow && options.length > 1 ? `<div class="${content.footRow}">${foot}</div>` : foot;
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
        ${progress}
        ${annotations ? `<span class="${cardAnnotations()}">${annotations}</span>` : ""}
        ${marks}
        ${shared ? "" : requester}
      </button>
    </div>
    ${strip}
    ${footLine}
    </div>
  </div>`;
}
