// A suggestion's panel — what a long press on a Découvrir card raises.
//
// It lives with Acquisitions because that is what makes it change: what is
// proposed, why, and what one may do about it.
//
// NO ADDRESS, and the reasoning is `ui/panel/contract.ts`'s own: this panel is
// keyed on an INDEX into the deck's order, and a panel keyed on a position in a
// list the engine regenerates would, after that list moved, reopen about
// something the operator never asked for. Addressing it by TITLE is available
// and refused — the same title can appear in the suggestions and in the add
// results, so which panel opens becomes a behaviour decision. Preserved rather
// than revisited.
import { icons } from "../../lib/shell-doors";
import type { Schemas } from "../../lib/contract-schemas";
import i18next from "i18next";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { suggestionsQuery } from "./queries";
import { factsLine, reasonSegments } from "./suggestion-words";


/** One suggestion, as the deck draws it. */
type Suggestion = Schemas["Suggestion"];

/**
 * Builds a suggestion's descriptor.
 *
 * Args:
 *     position: The suggestion's index into the reserve.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The descriptor, or null while the reserve has not landed or does not
 *     reach that far.
 */
function suggestionPanel(position: string, cache: PanelCache): PanelDescriptor | null {
  const reserve = cache.held<Schemas["SuggestionPage"]>(suggestionsQuery.queryKey)?.suggestions;
  const suggestion = reserve?.[Number(position)];
  if (suggestion === undefined) return null;
  const translate = i18next.t.bind(i18next);
  const isFilm = suggestion.kind === "movie";
  return {
    title: suggestion.title,
    meta: translate("panels.suggestion.metaRating", { facts: factsLine(suggestion), rating: suggestion.rating }),
    blocs: [
      { type: "note", text: reasonSegments(suggestion.why) },
      {
        type: "actions",
        actions: [
          {
            // THE VERB FOLLOWS THE KIND: a film is ADDED and a series is
            // FOLLOWED, which is §5 read from the interface's side — the one
            // has an end and the other does not.
            text: translate(isFilm
              ? "panels.suggestion.addFilm"
              : "panels.suggestion.followSeries"),
            icone: icons.plus,
            ton: "primary",
            target: { follow: suggestion.title, sugid: suggestion.id },
          },
          {
            text: translate("panels.suggestion.seeSheet"),
            icone: icons.eye,
            target: { mediasheet: suggestion.title },
          },
        ],
      },
      {
        type: "actions",
        secondary: true,
        actions: [
          {
            text: translate("panels.suggestion.notInterested"),
            icone: icons.x,
            ton: "danger",
            target: { dropsug: suggestion.id },
          },
        ],
      },
      isFilm
        ? { type: "note", text: translate("panels.suggestion.filmLeavesNote") }
        : null,
    ],
  };
}

registerProducer("suggestion", {
  produce: suggestionPanel,
  needs: [suggestionsQuery],
});
