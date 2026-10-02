// The filters of « Suivis »: the search field with its own native handler,
// the filter pill and the sort pill, and the three display modes.
//
// THE ONE PILL OF EVERY LIST (`ui/pill-select.tsx`, maquette-blocked DECIDED 1,
// § 1.9): the row of « Tout », « Séries », « Films » pills became ONE filter
// pill whose panel offers them with their counts, and beside it a sort pill of
// the same component. Both are REMEMBERED on this device, as « À traiter »'s
// are: the store holds the choice once made, the device's memory what was
// chosen last.
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { redraw } from "../../lib/shell-doors";
import { tabMemory } from "../../lib/tab-memory";
import { useUiState, writeUiState } from "../../lib/store-access";
import { PillSelect } from "../../ui/pill-select";
import { filterZone, pillBar, pillScroll, searchClear, searchField, searchInput, viewSwitch, viewSwitchButton, viewSwitchWrap } from "../../ui/variants";
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
 * @returns The search field, the two pills and the view switch.
 */
export function FollowsFilters({ shown }: { shown: number }): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  const filter = followFilterInForce(state);
  const sort = followSortInForce(state);
  return (
    <div className={filterZone()} data-region="acquisition/filters">
      <div className={searchField()}>
        <Icon paths={icons.search} />
        <input
          className={searchInput()}
          // UNCONTROLLED, with its own native handler — the arrangement
          // `#libq` has, for the same reason: `mountSearch` bound this field
          // from outside, and it runs inside `render()`, BEFORE React has put
          // the field in the document. Typing did nothing until some other
          // control forced a second render.
          type="search"
          id="follq"
          defaultValue={state.filter as string}
          placeholder={t("screens.acquisition.filterPlaceholder")}
          aria-label={t("screens.acquisition.filterLabel")}
          ref={(element) => {
            if (!element) return;
            // What changes the filter from OUTSIDE — the clear cross — has to
            // reach the field, and only when the two differ, so nothing
            // touches the node mid-word. The ATTRIBUTE follows too: the
            // legacy re-emitted it on every draw.
            const filter = state.filter as string;
            if (element.value !== filter) element.value = filter;
            if (element.getAttribute("value") !== filter)
              element.setAttribute("value", filter);
            const commit = () => {
              writeUiState({ filter: element.value });
              redraw();
            };
            element.addEventListener("input", commit);
            return () => element.removeEventListener("input", commit);
          }}
        />
        {state.filter ? (
          <button
            className={searchClear()}
            data-clear-filter
            aria-label={t("screens.acquisition.clearLabel")}
          >
            <Icon paths={icons.x} />
          </button>
        ) : null}
      </div>
      <div className={pillBar()}>
        <div className={pillScroll()} data-part="pill/list">
          <PillSelect
            label={t(followFilterWord(filter))}
            count={shown}
            pressed={filter !== FOLLOW_FILTERS[0]}
            attributes={{ "data-follows-filter-pill": "" }}
          />
          <PillSelect
            label={t(`screens.acquisition.followSort.${sort}`)}
            pressed={sort !== "urgency"}
            attributes={{ "data-follows-sort-pill": "" }}
          />
        </div>
        <div className={viewSwitchWrap()}>
          <div className={viewSwitch()} data-part="view/switch">
            <button
              className={viewSwitchButton()}
              aria-pressed={state.followMode === "list"}
              data-fmode="list"
              aria-label={t("screens.acquisition.modeList")}
            >
              <Icon paths={icons.list} />
            </button>
            <button
              className={viewSwitchButton()}
              aria-pressed={state.followMode === "group"}
              data-fmode="group"
              aria-label={t("screens.acquisition.modeGroup")}
            >
              <Icon paths={icons.group} />
            </button>
            <button
              className={viewSwitchButton()}
              aria-pressed={state.followMode === "grid"}
              data-fmode="grid"
              aria-label={t("screens.acquisition.modeGrid")}
            >
              <Icon paths={icons.grid} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
