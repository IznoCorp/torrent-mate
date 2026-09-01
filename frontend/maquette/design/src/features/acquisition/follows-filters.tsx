// The filters of « Suivis »: the search field with its own native handler,
// the four pills, and the three display modes.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { useAcquisitionReference } from "./reference";
import { useUiState, writeUiState } from "../../lib/store-access";
import { filterPill, filterPillCount, filterZone, pillBar, pillScroll, searchClear, searchField, searchInput, viewSwitch, viewSwitchButton, viewSwitchWrap } from "../../ui/variants";

/** One pill of the filter bar: what it selects, what it says, how many it holds. */
export type FollowPill = { id: string; label: string; count: number };

export function FollowsFilters({ pills }: { pills: FollowPill[] }): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons, render } = useAcquisitionReference();
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
              render();
            };
            element.addEventListener("input", commit);
            return () => element.removeEventListener("input", commit);
          }}
        />
        {state.filter ? (
          <button
            className={searchClear()}
            data-clearq="foll"
            aria-label={t("screens.acquisition.clearLabel")}
          >
            <Icon paths={icons.x} />
          </button>
        ) : null}
      </div>
      <div className={pillBar()}>
        <div className={pillScroll()} data-part="pill/list">
          {pills.map((pill) => (
            <button
              key={pill.id}
              className={filterPill()}
              data-part="pill"
              aria-pressed={state.pill === pill.id}
              data-pill={pill.id}
            >
              {pill.label}
              <span className={filterPillCount()}>{pill.count}</span>
            </button>
          ))}
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
