// « À traiter »'s two pills: the panels they raise, and the choices made there.
//
// NO ADDRESS: a filter and a sort are choices among the page's dials, as the
// tracker selector's and the library's sort are — the device remembers them.
import i18next from "i18next";
import { todoCards } from "../../lib/arrival-slots";
import { queueKey, type AcquisitionQueue } from "../../lib/queue";
import { panel, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { TODO_FILTERS, TODO_SORTS, todoCounts, type TodoFilter, type TodoSort } from "./todo-order";
import { registerVerb } from "../../lib/verbs";
import { registerProducer, type PanelCache } from "../../ui/panel/contract";
import { choicesDescriptor, closeThenApply } from "../../ui/pill-select";
import { FILTER_MEMORY, SORT_MEMORY, TODO_SEARCH_KEY, todoFilterInForce, todoSortInForce } from "./todo-pills";

/**
 * The queue's answer the tab draws, from the cache.
 *
 * @param cache What the query cache holds.
 * @returns The answer, or undefined before it has landed.
 */
function heldQueue(cache: PanelCache): AcquisitionQueue | undefined {
  const scenario = String(store.read().state.scen ?? "") === "loaded" ? "loaded" : "";
  return cache.held<AcquisitionQueue>(queueKey(scenario));
}

registerProducer("todo-filter", {
  produce: (_subject, cache) => {
    const queue = heldQueue(cache);
    if (queue === undefined) return null;
    // EVERY CAUSE IS OFFERED, its count beside it — a cause with no card reads 0:
    // the panel says what exists. « Mis de côté » is outside the list (ruling 16).
    // THE SEARCH TYPED IS APPLIED, so a cause counts what the list would show once chosen.
    const state = store.read().state;
    const counts = todoCounts(todoCards(queue), String(state[TODO_SEARCH_KEY] ?? ""));
    const current = todoFilterInForce(state);
    return choicesDescriptor(
      i18next.t("screens.acquisition.todoFilterTitle"),
      i18next.t("screens.acquisition.todoFilterMeta"),
      TODO_FILTERS.map((filter) => ({
        text: i18next.t(`screens.acquisition.todoFilter.${filter}`),
        hint: i18next.t("screens.acquisition.todoFilterCount", { count: counts[filter] }),
        checked: current === filter,
        target: { "todo-filter": filter },
      })),
    );
  },
});

registerProducer("todo-sort", {
  produce: () => {
    const current = todoSortInForce(store.read().state);
    return choicesDescriptor(
      i18next.t("screens.acquisition.todoSortTitle"),
      i18next.t("screens.acquisition.todoSortMeta"),
      TODO_SORTS.map((sort) => ({
        text: i18next.t(`screens.acquisition.todoSort.${sort}`),
        checked: current === sort,
        target: { "todo-sort": sort },
      })),
    );
  },
});

/* THE PILLS raise their choices. */
registerVerb("todo-filter-pill", () => panel.produce("todo-filter"));
registerVerb("todo-sort-pill", () => panel.produce("todo-sort"));

/**
 * Applies a choice: kept in the store and in the device's memory, the list
 * drawn again from its top.
 *
 * @param patch The dial the choice sets.
 */
function apply(patch: { todoFilter: TodoFilter } | { todoSort: TodoSort }): void {
  if ("todoFilter" in patch) FILTER_MEMORY.remember(patch.todoFilter);
  else SORT_MEMORY.remember(patch.todoSort);
  store.write(patch);
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
}

registerVerb("todo-filter", (filter) => closeThenApply(() => apply({ todoFilter: filter as TodoFilter })));
registerVerb("todo-sort", (sort) => closeThenApply(() => apply({ todoSort: sort as TodoSort })));
