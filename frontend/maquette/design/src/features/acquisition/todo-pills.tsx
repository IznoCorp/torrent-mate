// « À traiter »'s filter pill and sort pill (DECIDED 1 of maquette-blocked).
//
// THE ONE PILL OF EVERY LIST (`ui/pill-select.tsx`), fed the cause in force and
// the cards it keeps, and beside it the sort in force. Both are REMEMBERED on
// this device, as the operator asked (« retenue comme le filtre »): the store
// holds the choice once made, the device's memory what was chosen last.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { tabMemory } from "../../lib/tab-memory";
import { TODO_FILTERS, TODO_SORTS, type TodoFilter, type TodoSort } from "./todo-order";
import { useUiState } from "../../lib/store-access";
import { PillSelect } from "../../ui/pill-select";
import { filterZone, pillBar, pillScroll } from "../../ui/variants";

/** The device's memory of the filter and of the sort. */
export const FILTER_MEMORY = tabMemory("todo-filter", "all", new Set(TODO_FILTERS));
export const SORT_MEMORY = tabMemory("todo-sort", "urgency", new Set(TODO_SORTS));

/**
 * The filter in force: the one chosen in this document, else the one this
 * device remembers.
 *
 * @param state The interface's state.
 * @returns The filter.
 */
export function todoFilterInForce(state: Record<string, unknown>): TodoFilter {
  const chosen = state.todoFilter;
  return (typeof chosen === "string" && (TODO_FILTERS as readonly string[]).includes(chosen)
    ? chosen : FILTER_MEMORY.remembered()) as TodoFilter;
}

/**
 * The sort in force, read the way the filter is.
 *
 * @param state The interface's state.
 * @returns The sort.
 */
export function todoSortInForce(state: Record<string, unknown>): TodoSort {
  const chosen = state.todoSort;
  return (typeof chosen === "string" && (TODO_SORTS as readonly string[]).includes(chosen)
    ? chosen : SORT_MEMORY.remembered()) as TodoSort;
}

/**
 * The two pills.
 *
 * @param props.shown How many cards the filter keeps.
 * @returns The filter zone.
 */
export function TodoPills({ shown }: { shown: number }): ReactElement {
  const { t } = useTranslation();
  const state = useUiState();
  const filter = todoFilterInForce(state);
  const sort = todoSortInForce(state);
  return (
    <div className={filterZone()} data-part="todo/filters">
      <div className={pillBar()}>
        <div className={pillScroll()} data-part="pill/list">
          <PillSelect
            label={t(`screens.acquisition.todoFilter.${filter}`)}
            count={shown}
            pressed={filter !== "all"}
            attributes={{ "data-todo-filter-pill": "" }}
          />
          <PillSelect
            label={t(`screens.acquisition.todoSort.${sort}`)}
            pressed={sort !== "urgency"}
            attributes={{ "data-todo-sort-pill": "" }}
          />
        </div>
      </div>
    </div>
  );
}
