// A suggestion said in the interface's own words (K3-G7).
//
// THE SERVER SENDS NO SENTENCE: a card's kind is a token, its year a number or nothing, and its
// reason a code with the values its words name. The words are fr.json's, and the three shapes a
// suggestion is drawn in and its panel all read them here.
import i18next from "i18next";
import type { Schemas } from "../../lib/contract-schemas";

type Suggestion = Schemas["Suggestion"];
type Reason = Schemas["SuggestionReason"];

/** One piece of a reason's sentence: plain text, or what the interface emphasises. */
export type ReasonPiece = string | { emphasis: string };

// WHERE A VALUE GOES IN A SENTENCE. The sentence is read with these in its slots and cut at them, so
// a value lands where the words put it and is never searched for afterwards.
const FIGURE_SLOT = "\u0001";
const TITLES_SLOT = "\u0002";
const SLOTS = /([\u0001\u0002])/;

/**
 * The word a suggestion's kind is said with.
 *
 * @param kind The served token.
 * @returns The word.
 */
export function kindWord(kind: Suggestion["kind"]): string {
  return i18next.t(`discover.kind.${kind}`);
}

/**
 * A card's facts: its year and its kind, or its kind alone when no year is known.
 *
 * @param suggestion The card.
 * @returns The line.
 */
export function factsLine(suggestion: Pick<Suggestion, "year" | "kind">): string {
  const kind = kindWord(suggestion.kind);
  return suggestion.year === null ? kind : `${suggestion.year} · ${kind}`;
}

/**
 * The titles a reason names, joined as the language joins a list.
 *
 * @param titles The titles, in the order served.
 * @param firstEmphasised Whether the first one is what the sentence emphasises.
 * @returns The pieces.
 */
function titlePieces(titles: readonly string[], firstEmphasised: boolean): ReasonPiece[] {
  let named = 0;
  return new Intl.ListFormat(i18next.language, { type: "conjunction" }).formatToParts(titles).map((part) => {
    if (part.type !== "element") return part.value;
    named += 1;
    return firstEmphasised && named === 1 ? { emphasis: part.value } : part.value;
  });
}

/**
 * Why a title is suggested, as the pieces of one sentence.
 *
 * WHAT IS EMPHASISED IS THE COUNT when the titles were counted, else the first title named.
 *
 * @param why The served code and its values.
 * @returns The sentence's pieces, in order.
 */
export function reasonPieces(why: Reason): ReasonPiece[] {
  const counted = why.count !== null;
  const named = why.titles.length > 0;
  const shape = counted ? (named ? "countedNamed" : "counted") : named ? "named" : "unnamed";
  const sentence = i18next.t(`discover.reason.${why.code}.${shape}`, {
    ...(why.count === null ? {} : { count: why.count }),
    figure: FIGURE_SLOT,
    titles: TITLES_SLOT,
  });
  return sentence.split(SLOTS).flatMap((piece): ReasonPiece[] => {
    if (piece === FIGURE_SLOT) return [{ emphasis: String(why.count) }];
    if (piece === TITLES_SLOT) return titlePieces(why.titles, !counted);
    return piece === "" ? [] : [piece];
  });
}

/**
 * The same sentence as a panel's rich text takes it, which marks emphasis as `e`.
 *
 * @param why The served code and its values.
 * @returns The segments.
 */
export function reasonSegments(why: Reason): (string | { e: string })[] {
  return reasonPieces(why).map((piece) => (typeof piece === "string" ? piece : { e: piece.emphasis }));
}
