// « En cours »'s zone: the search field, the filter pill and the sort pill, the
// ones « Suivis » and « À traiter » draw (`acquisition-zone.tsx`), fed what an
// acquisition on its way can be told apart by — its kind and how far it has gone.
//
// BOTH PILLS ARE REMEMBERED on this device, as the two other tabs' are: the
// store holds the choice once made, the device's memory what was chosen last.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { tabMemory } from "../../lib/tab-memory";
import { useUiState } from "../../lib/store-access";
import { AcquisitionZone } from "./acquisition-zone";
import { NOW_FILTERS, NOW_SORTS, type NowFilter, type NowSort } from "./now-order";

/** The store key « En cours »'s search is kept under. */
export const NOW_SEARCH_KEY = "nowSearch";

/** The device's memory of the filter and of the sort. */
export const NOW_FILTER_MEMORY = tabMemory("now-filter", NOW_FILTERS[0], new Set(NOW_FILTERS));
export const NOW_SORT_MEMORY = tabMemory("now-sort", NOW_SORTS[0], new Set(NOW_SORTS));

/**
 * The filter in force: the one chosen in this document, else the one this
 * device remembers.
 *
 * @param state The interface's state.
 * @returns The filter.
 */
export function nowFilterInForce(state: Record<string, unknown>): NowFilter {
  const chosen = state.nowFilter;
  return (typeof chosen === "string" && (NOW_FILTERS as readonly string[]).includes(chosen)
    ? chosen : NOW_FILTER_MEMORY.remembered()) as NowFilter;
}

/**
 * The sort in force, read the way the filter is.
 *
 * @param state The interface's state.
 * @returns The sort.
 */
export function nowSortInForce(state: Record<string, unknown>): NowSort {
  const chosen = state.nowSort;
  return (typeof chosen === "string" && (NOW_SORTS as readonly string[]).includes(chosen)
    ? chosen : NOW_SORT_MEMORY.remembered()) as NowSort;
}

/**
 * The zone of « En cours ».
 *
 * @param props.shown How many cards the filter keeps, or nothing while the list is not drawn.
 * @returns The zone.
 */
export function NowFilters({ shown }: { shown?: number }): ReactElement {
  const { t } = useTranslation();
  const state = useUiState();
  const filter = nowFilterInForce(state);
  const sort = nowSortInForce(state);
  return (
    <AcquisitionZone
      searchKey={NOW_SEARCH_KEY}
      searchId="nowq"
      searchLabel={t("screens.acquisition.nowSearchLabel")}
      filter={{
        label: t(`screens.acquisition.nowFilter.${filter}`),
        count: shown,
        pressed: filter !== NOW_FILTERS[0],
        attributes: { "data-now-filter-pill": "" },
      }}
      sort={{
        label: t(`screens.acquisition.nowSort.${sort}`),
        pressed: sort !== NOW_SORTS[0],
        attributes: { "data-now-sort-pill": "" },
      }}
      modes={false}
    />
  );
}
