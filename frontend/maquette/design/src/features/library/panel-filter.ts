// The Médiathèque's filter panel — what a tap on the filter pill raises.
//
// THE ONE PILL OF EVERY LIST (`ui/pill-select.tsx`, maquette-blocked DECIDED 1,
// § 1.9): the row of category pills became one pill, and its panel offers
// every category in the order they are served, each with what it counts on the
// lens in force (`categoryCount`, the pill's own derivation).
//
// THE CATEGORY STAYS WHERE IT WAS KEPT: the store and the address (`cat`), the
// choice answered by the category verb.
import i18next from "i18next";
import { read } from "../../lib/query-client";
import { store } from "../../lib/store-access";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { choicesDescriptor } from "../../ui/pill-select";
import { categoryCount } from "./category-filter";
import { libraryIncompleteQuery, type LibraryPage } from "./queries";
import type { IncompleteShow, LibraryCategory } from "./types";

const CATEGORIES_KEY = ["/api/v1/library/categories"];

/**
 * Builds the filter panel's descriptor.
 *
 * @param _subject Unused: the panel has one subject, the page's category.
 * @param cache What the query cache holds.
 * @returns The descriptor, or null while the categories have not landed.
 */
function filterPanel(_subject: string, cache: PanelCache): PanelDescriptor | null {
  const categories = cache.held<LibraryCategory[]>(CATEGORIES_KEY);
  if (categories === undefined) return null;
  const { libLens, libCat, q, sortKey, sortReversed } = store.read().state;
  const incomplete = cache.held<IncompleteShow[]>(libraryIncompleteQuery.queryKey) ?? [];
  // « Récents »' rows: the listing that lens draws, under the key it reads.
  const recent = (cache.held<{ pages: LibraryPage[] }>(
    ["/api/v1/library/items", String(q ?? ""), "", String(sortKey ?? ""), Boolean(sortReversed)],
  )?.pages ?? []).flatMap((page) => page.items);
  return choicesDescriptor(
    i18next.t("screens.library.filterTitle"),
    i18next.t("screens.library.filterMeta"),
    categories.map((category) => ({
      text: category.label,
      hint: i18next.t("screens.library.filterCount", {
        count: categoryCount(category, String(libLens), incomplete, recent, String(q ?? "")),
      }),
      checked: libCat === category.id,
      target: { cat: category.id },
    })),
  );
}

registerProducer("library-filter", {
  produce: filterPanel,
  needs: [
    { queryKey: CATEGORIES_KEY, queryFn: async () => read<LibraryCategory[]>(CATEGORIES_KEY[0]) },
    libraryIncompleteQuery,
  ],
});
