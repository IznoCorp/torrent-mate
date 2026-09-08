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
// THE SHARED EMITTERS ARE THE ENGINE'S AND ARE CALLED VERBATIM. `cardHTML` and
// `tileHTML` draw every row and tile in this application; a copy here would be
// a second definition of one shape, and the rows they emit carry the `data-*`
// the delegation reads.
import i18next from "i18next";

declare global {
  interface Window {
    /**
     * The high-definition poster map and the rich-text emitter, as the dying
     * engine publishes them.
     *
     * READ HERE AND NOT THROUGH THE REFERENCE, which carries neither: adding
     * them to it would be adding to the engine, and D5 allows that only to stop
     * a defect that loses the operator's data. Both die with it.
     */
    POSTERS_HD: Record<string, string>;
    richText: (value: unknown) => string;
  }
}

/** One suggestion, as the reserve answers it. */
export type Suggestion = {
  t: string;
  y: string;
  k: string;
  note: number | string;
  why: unknown;
};

const drawing = () => window.__referentiel;
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
  const reference = drawing();
  const dismiss = say("notInterested");
  return `<div class="sugwrap" data-part="suggestion/wrap" data-dismissable="${position}">
      <div class="sugback">
        <span>${reference.svgIcon(reference.icons.x)}${dismiss}</span>
        <span>${dismiss}${reference.svgIcon(reference.icons.x)}</span>
      </div>
      ${reference.cardHTML({
        t: suggestion.t,
        k: suggestion.k === "Film" ? "movie" : "show",
        s: `${suggestion.y} · ${suggestion.k}`,
        note: suggestion.note,
        r: suggestion.why,
        panel: `sug:${position}`,
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
  return drawing().tileHTML(
    { t: suggestion.t, k: suggestion.k === "Film" ? "movie" : "show" },
    `${suggestion.y} · ${suggestion.k}`,
    {
      panel: `sug:${position}`,
      dismiss: position,
      badge: { tone: "note", txt: String(suggestion.note) },
    },
  );
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
  const reference = drawing();
  const escape = reference.escapeHtml;
  const poster = window.POSTERS_HD[suggestion.t]
    ? `<img src="${window.POSTERS_HD[suggestion.t]}" alt="" loading="lazy">`
    : reference.posterBox(suggestion.t, suggestion.k === "Film" ? "movie" : "show");
  // THE GESTURE LABELS BELONG TO THE TOP CARD ALONE — it is the only one a
  // finger can reach, and `advanceDeck` moves them with the place rather than
  // with the card.
  const hints =
    depth === 0
      ? `<span class="dhint l">${say("skip")}</span>` +
        `<span class="dhint r">${say("notInterested")}</span>`
      : "";
  return `<article class="dcard" data-part="deck/card" data-deck="${position}" data-depth="${depth}" data-panel="sug:${position}">
      <button class="p" data-mediasheet="${escape(suggestion.t)}" aria-label="Fiche de ${escape(suggestion.t)}">
        ${poster}
        <span class="cap">
          <span class="t" data-part="deck/title">${escape(suggestion.t)}</span>
          <span class="m">${escape(suggestion.y)} · ${escape(suggestion.k)} · ${escape(String(suggestion.note))}${say("onTmdb")}</span>
          <span class="why">${window.richText(suggestion.why)}</span>
        </span>
      </button>
      ${hints}
    </article>`;
}

/** The gesture labels the card that takes the top place has to inherit. */
export function deckHints(): string {
  return (
    `<span class="dhint l">${say("skip")}</span>` +
    `<span class="dhint r">${say("notInterested")}</span>`
  );
}
