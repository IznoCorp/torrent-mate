// A SEARCH RESULT's panel — what a long press on an `/add` row raises.
//
// A search result is not one of the operator's media yet, so it has a panel of
// its own rather than a follow's: what it offers is the act that WOULD make it
// one, and the sheet to judge it by. **This panel is the only place that
// carries the act** — the row wears no inline button, so it stays the size of a
// row and the decision is taken where the facts are.
//
// A NEW FILE BESIDE `add-screen.tsx`, NEVER A FUNCTION IN IT: that file stands
// at 395 of a 400-line hard ceiling and a single added line there is a red gate.
//
// NO ADDRESS, and the reasoning is `panel-suggestion.ts`'s: the panel is keyed
// on an INDEX into a list the search regenerates.
import { icons } from "../../lib/shell-doors";
import i18next from "i18next";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";



// THE FEATURE'S OWN DECLARATION, not a narrower copy: `addVerb` takes the whole
// result, so a slice declared here would be a second shape of one record and
// the compiler would be right to refuse it.
import type { SearchResult } from "./types";
import { identifying, isAdded } from "./add-visit";
import { searchResults } from "./search-queries";
import { addVerb } from "./add-label";

/**
 * Builds a search result's descriptor.
 *
 * Args:
 *     position: The result's index into the answered list.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The descriptor, or null while the search has not answered.
 */
function addPanel(position: string, cache: PanelCache): PanelDescriptor | null {
  const answered = searchResults?.();
  const result = answered?.results?.[Number(position)] as SearchResult | undefined;
  if (result === undefined) return null;
  const translate = i18next.t.bind(i18next);
  const identifyingFolder = identifying();
  const done = isAdded(result);
  return {
    title: result.title,
    meta: translate("panels.add.meta", { year: result.year, kind: result.kind }),
    blocs: [
      // DOIT-8's FIRST HALF, and the second is the confirmation the act raises:
      // a film the library already owns is announced as a REPLACEMENT before
      // anything is asked for. In « identify » mode there is nothing to
      // replace — the result is being ATTACHED to a folder already in hand —
      // so the sentence would be false rather than merely redundant.
      result.owned && !identifyingFolder
        ? {
            type: "note",
            text: [
              translate("panels.add.ownedBefore"),
              { e: translate("panels.add.ownedEmphasis") },
              translate("panels.add.ownedAfter"),
            ],
          }
        : null,
      {
        type: "actions",
        actions: [
          {
            // ONE DERIVATION: the add SCREEN draws the same word on its own
            // rows, so `addVerb` answers both (§13).
            text: addVerb(result),
            icone: icons.plus,
            ton: "primary",
            desactive: done,
            target: { add: position },
          },
          {
            text: translate("panels.add.seeSheet"),
            icone: icons.eye,
            target: { mediasheet: result.title },
          },
        ],
      },
    ],
  };
}

// NO `needs`, and it is measured rather than forgotten: the search is keyed on
// the QUERY being typed, so there is no key a boot could ask for. The screen
// that draws the results is mounted whenever this panel can be raised, and
// `window.__searchResults()` is the one derivation of « which search is
// current » — `installSearchLookup`'s own reason, applied to its second reader.
registerProducer("add", { produce: addPanel });
