// The filters of « Suivis »: the zone every tab draws (`acquisition-zone.tsx`),
// fed the follows' filter and sort, and with the three display modes.
//
// THE ONE PILL OF EVERY LIST (`ui/pill-select.tsx`, maquette-blocked DECIDED 1,
// § 1.9): the row of « Tout », « Séries », « Films » pills became ONE filter
// pill whose panel offers them with their counts, and beside it a sort pill of
// the same component. Both are REMEMBERED on this device, as « À traiter »'s
// are: the store holds the choice once made, the device's memory what was
// chosen last.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { tabMemory } from "../../lib/tab-memory";
import { useUiState } from "../../lib/store-access";
import { AcquisitionZone } from "./acquisition-zone";
import { FOLLOW_FILTERS, FOLLOW_SORTS, type FollowFilter, type FollowSort } from "./follow-order";

/** The device's memory of the filter and of the sort. */
export const FOLLOW_FILTER_MEMORY = tabMemory("follows-filter", FOLLOW_FILTERS[0], new Set(FOLLOW_FILTERS));
export const FOLLOW_SORT_MEMORY = tabMemory("follows-sort", "urgency", new Set(FOLLOW_SORTS));

// The words each filter is said with, in the order of `FOLLOW_FILTERS`.
const FILTER_WORDS = ["pillAll", "pillSeries", "pillMovies"];

/**
 * The key of the words a filter is said with.
 *
 * @param filter The filter.
 * @returns Its i18n key.
 */
export function followFilterWord(filter: FollowFilter): string {
  return `screens.acquisition.${FILTER_WORDS[FOLLOW_FILTERS.indexOf(filter)]}`;
}

/**
 * The filter in force: the one chosen in this document, else the one this
 * device remembers.
 *
 * @param state The interface's state.
 * @returns The filter.
 */
export function followFilterInForce(state: Record<string, unknown>): FollowFilter {
  const chosen = state.pill;
  return (typeof chosen === "string" && (FOLLOW_FILTERS as readonly string[]).includes(chosen)
    ? chosen : FOLLOW_FILTER_MEMORY.remembered()) as FollowFilter;
}

/**
 * The sort in force, read the way the filter is.
 *
 * @param state The interface's state.
 * @returns The sort.
 */
export function followSortInForce(state: Record<string, unknown>): FollowSort {
  const chosen = state.followSort;
  return (typeof chosen === "string" && (FOLLOW_SORTS as readonly string[]).includes(chosen)
    ? chosen : FOLLOW_SORT_MEMORY.remembered()) as FollowSort;
}

/**
 * The filter zone.
 *
 * @param props.shown How many follows the filter keeps.
 * @returns The zone, display switch included.
 */
export function FollowsFilters({ shown }: { shown: number }): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const filter = followFilterInForce(state);
  const sort = followSortInForce(state);
  return (
    <AcquisitionZone
      searchKey="filter"
      searchId="follq"
      searchLabel={t("screens.acquisition.filterLabel")}
      filter={{
        label: t(followFilterWord(filter)),
        count: shown,
        pressed: filter !== FOLLOW_FILTERS[0],
        attributes: { "data-follows-filter-pill": "" },
      }}
      sort={{
        label: t(`screens.acquisition.followSort.${sort}`),
        pressed: sort !== "urgency",
        attributes: { "data-follows-sort-pill": "" },
      }}
      modes
    />
  );
}
