// « En cours »'s two pills: the panels they raise, and the choices made there.
//
// NO ADDRESS: a filter and a sort are choices among the page's dials, as
// « Suivis »' and « À traiter »'s are — the device remembers them.
import i18next from "i18next";
import { inFlightCards } from "../../lib/arrival-slots";
import { queueKey, type AcquisitionQueue } from "../../lib/queue";
import { panel, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { registerVerb } from "../../lib/verbs";
import { registerProducer, type PanelCache } from "../../ui/panel/contract";
import { choicesDescriptor, closeThenApply } from "../../ui/pill-select";
import {
  NOW_FILTER_MEMORY, NOW_SEARCH_KEY, NOW_SORT_MEMORY, nowFilterInForce, nowSortInForce,
} from "./now-filters";
import { NOW_FILTERS, NOW_SORTS, nowCounts, type NowFilter, type NowSort } from "./now-order";

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

registerProducer("now-filter", {
  produce: (_subject, cache) => {
    const queue = heldQueue(cache);
    if (queue === undefined) return null;
    // THE PILL'S BASIS: the cards on their way, the search applied — so a choice
    // counts what the list shows once chosen.
    const state = store.read().state;
    const counts = nowCounts(inFlightCards(queue), String(state[NOW_SEARCH_KEY] ?? ""));
    const current = nowFilterInForce(state);
    return choicesDescriptor(
      i18next.t("screens.acquisition.nowFilterTitle"),
      i18next.t("screens.acquisition.nowFilterMeta"),
      NOW_FILTERS.map((filter) => ({
        text: i18next.t(`screens.acquisition.nowFilter.${filter}`),
        hint: i18next.t("screens.acquisition.nowFilterCount", { count: counts[filter] }),
        checked: current === filter,
        target: { "now-filter": filter },
      })),
    );
  },
});

registerProducer("now-sort", {
  produce: () => {
    const current = nowSortInForce(store.read().state);
    return choicesDescriptor(
      i18next.t("screens.acquisition.nowSortTitle"),
      i18next.t("screens.acquisition.nowSortMeta"),
      NOW_SORTS.map((sort) => ({
        text: i18next.t(`screens.acquisition.nowSort.${sort}`),
        checked: current === sort,
        target: { "now-sort": sort },
      })),
    );
  },
});

/* THE PILLS raise their choices. */
registerVerb("now-filter-pill", () => panel.produce("now-filter"));
registerVerb("now-sort-pill", () => panel.produce("now-sort"));

/**
 * Applies a choice: kept in the store and in the device's memory, the list
 * drawn again from its top.
 *
 * @param patch The dial the choice sets.
 */
function apply(patch: { nowFilter: NowFilter } | { nowSort: NowSort }): void {
  if ("nowFilter" in patch) NOW_FILTER_MEMORY.remember(patch.nowFilter);
  else NOW_SORT_MEMORY.remember(patch.nowSort);
  store.write(patch);
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
}

registerVerb("now-filter", (filter) => closeThenApply(() => apply({ nowFilter: filter as NowFilter })));
registerVerb("now-sort", (sort) => closeThenApply(() => apply({ nowSort: sort as NowSort })));
