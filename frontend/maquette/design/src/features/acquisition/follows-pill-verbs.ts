// « Suivis »'s two pills: the panels they raise, and the choices made there.
//
// THE ONE PILL OF EVERY LIST (maquette-blocked DECIDED 1, § 1.9), fed the
// follows' kinds and the five sorts of his round 3 q1 = C.
//
// NO ADDRESS: a filter and a sort are choices among the page's dials, as
// « À traiter »'s and the library's sort are — the device remembers them.
import i18next from "i18next";
import { panel, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { registerVerb } from "../../lib/verbs";
import { registerProducer } from "../../ui/panel/contract";
import { choicesDescriptor, closeThenApply } from "../../ui/pill-select";
import { FOLLOW_FILTERS, FOLLOW_SORTS, followCounts, type FollowFilter, type FollowSort } from "./follow-order";
import {
  FOLLOW_FILTER_MEMORY, FOLLOW_SORT_MEMORY, followFilterInForce, followFilterWord, followSortInForce,
} from "./follows-filters";
import { followsQuery } from "./queries";
import type { Follow } from "./types";

registerProducer("follows-filter", {
  produce: (_subject, cache) => {
    const follows = cache.held<Follow[]>(followsQuery().queryKey);
    if (follows === undefined) return null;
    // A PAUSED FOLLOW IS OUTSIDE THE LIST and outside its counts, folded at its
    // end — the counts are the follows being looked for.
    const counts = followCounts(follows.filter((follow) => follow.status !== "disabled"));
    const current = followFilterInForce(store.read().state);
    return choicesDescriptor(
      i18next.t("screens.acquisition.followFilterTitle"),
      i18next.t("screens.acquisition.followFilterMeta"),
      FOLLOW_FILTERS.map((filter) => ({
        text: i18next.t(followFilterWord(filter)),
        hint: i18next.t("screens.acquisition.followFilterCount", { count: counts[filter] }),
        checked: current === filter,
        target: { pill: filter },
      })),
    );
  },
  needs: () => [followsQuery()],
});

registerProducer("follows-sort", {
  produce: () => {
    const current = followSortInForce(store.read().state);
    return choicesDescriptor(
      i18next.t("screens.acquisition.followSortTitle"),
      i18next.t("screens.acquisition.followSortMeta"),
      FOLLOW_SORTS.map((sort) => ({
        text: i18next.t(`screens.acquisition.followSort.${sort}`),
        checked: current === sort,
        target: { "follow-sort": sort },
      })),
    );
  },
});

/* THE PILLS raise their choices. */
registerVerb("follows-filter-pill", () => panel.produce("follows-filter"));
registerVerb("follows-sort-pill", () => panel.produce("follows-sort"));

/**
 * Applies a choice: kept in the store and in the device's memory, the list
 * drawn again from its top.
 *
 * @param patch The dial the choice sets.
 */
function apply(patch: { pill: FollowFilter } | { followSort: FollowSort }): void {
  if ("pill" in patch) FOLLOW_FILTER_MEMORY.remember(patch.pill);
  else FOLLOW_SORT_MEMORY.remember(patch.followSort);
  store.write(patch);
  const port = document.getElementById("port");
  if (port !== null) port.scrollTop = 0;
  redraw();
}

registerVerb("pill", (filter) => closeThenApply(() => apply({ pill: filter as FollowFilter })));
registerVerb("follow-sort", (sort) => closeThenApply(() => apply({ followSort: sort as FollowSort })));
