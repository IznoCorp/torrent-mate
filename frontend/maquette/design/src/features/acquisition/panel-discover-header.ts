// Découvrir's header message — what it says, and the panel that says it whole.
//
// « n séries et m films à découvrir » (the operator's Q8): both figures counted
// from the suggestions ALREADY READ — the list Découvrir draws, split by kind,
// what was rejected left out — so no figure is copy, and no new read is made.
// The header draws it on one line beside the view switch; a tap opens this
// panel with the sentence whole.
import i18next from "i18next";
import type { Schemas } from "../../lib/contract-schemas";
import { store } from "../../lib/store-access";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { suggestionsQuery } from "./queries";

// THE KIND A FILM IS SERVED AS; every other kind is a series.
// french-ok: a data VALUE — the kind the suggestions serve
const FILM = "Film";

/**
 * The header's sentence, from the suggestions read.
 *
 * @param reserve The suggestions read, or undefined while none has landed.
 * @param rejected The positions rejected, left out of what is to discover.
 * @returns « n séries et m films à découvrir », or undefined while nothing is read.
 */
export function headerSentence(reserve: Schemas["Suggestion"][] | undefined, rejected: ReadonlySet<number>): string | undefined {
  if (reserve === undefined) return undefined;
  const left = reserve.filter((_, position) => !rejected.has(position));
  const films = left.filter((suggestion) => suggestion.kind === FILM).length;
  const say = (key: string, values: Record<string, unknown>) => i18next.t(`screens.acquisition.${key}`, values);
  return say("headerCount", {
    series: say("headerSeries", { count: left.length - films }),
    films: say("headerFilms", { count: films }),
  });
}

/**
 * Builds the header's panel.
 *
 * @param _subject Unused: the panel has one subject, Découvrir's reserve.
 * @param cache What the query cache holds.
 * @returns The descriptor, or null while nothing is read.
 */
function headerPanel(_subject: string, cache: PanelCache): PanelDescriptor | null {
  const sentence = headerSentence(
    cache.held<Schemas["Suggestion"][]>(suggestionsQuery.queryKey),
    store.read().state.sugGone as Set<number>,
  );
  if (sentence === undefined) return null;
  return {
    title: i18next.t("screens.acquisition.headerTitle"),
    blocs: [{ type: "note", text: sentence }],
  };
}

registerProducer("discover-header", { produce: headerPanel, needs: () => [suggestionsQuery] });
