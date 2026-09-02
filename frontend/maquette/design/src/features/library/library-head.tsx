// The head of the library page: the three lenses, the search field with its
// own native handler, the category pills and the list/grid switch.
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { useLibraryReference } from "./reference";
import { useLibraryCategories } from "./queries";
import { useUiState, writeUiState } from "../../lib/store-access";
import { filterPill, filterPillCount, filterZone, pillBar, pillScroll, searchClear, searchField, searchInput, segment, segmentCount, segmentTab, viewSwitch, viewSwitchButton, viewSwitchWrap, viewTabs } from "../../ui/variants";

// The three lenses, in the order the tab bar draws them.
//
// THE COUNT ON « Incomplets » IS NOT DERIVED FROM THE ROWS THE LENS DRAWS, and
// it cannot be here: the seed holds twelve incomplete series where this figure
// claims forty-seven, and forty-seven is neither their number nor the sum of
// anything about them (they are short 226 episodes between them). It is the
// library's own figure, hard-coded as the legacy hard-coded it, standing over a
// fixture that seeds a sample of the shows it counts.
//
// WHICH MAKES IT A DEMAND ON THE BACKEND, not a number to correct here. The
// count and the rows must come from ONE read, or the interface goes on printing
// a total no reader can reconcile with the list under it — and correcting the
// literal to twelve would only make the maquette agree with its own fixture
// while saying nothing true about a library of 1 861 titles.
export const INCOMPLETE_COUNT = 47;

export function LibraryHead(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons, render } = useLibraryReference();
  const { data: CATS = [] } = useLibraryCategories();
  const lenses = [
    { id: "cat", label: t("screens.library.lensMedia") },
    { id: "rec", label: t("screens.library.lensRecent") },
    { id: "inc", label: t("screens.library.lensIncomplete"), count: INCOMPLETE_COUNT },
  ];
  return (
    <>
      <div className={viewTabs()} data-region="library/tabs">
        <div className={segment()} data-part="segment" role="tablist">
          {lenses.map((lens) => (
            <button
              key={lens.id}
              className={segmentTab()}
            role="tab"
              aria-selected={state.libLens === lens.id}
              data-lens={lens.id}
            >
              {lens.label}
              {lens.count ? <span className={segmentCount()} data-part="segment/count">{lens.count}</span> : null}
            </button>
          ))}
        </div>
      </div>
      <div className={filterZone()} data-region="library/filters">
        <div className={searchField()}>
          <Icon paths={icons.search} />
          <input
            className={searchInput()}
            // UNCONTROLLED, and NOT keyed by the query. The legacy rebuilt this
            // node on every draw and then put the caret back by hand; React
            // keeps the node, so the dance is unnecessary — and keying it by
            // what one types would recreate the node on every keystroke, which
            // is the same defect wearing the other hat. The field is the one
            // place the operator's own text lives between two renders.
            type="search"
            id="libq"
            defaultValue={state.q as string}
            placeholder={t("screens.library.searchPlaceholder")}
            aria-label={t("screens.library.searchLabel")}
            // THE HANDLER MOVES WITH THE FIELD: `mountSearch` used to bind this
            // from outside, and binding a node React owns from outside is two
            // writers on one field — the same reason the panel took its own
            // `.fieldinput` handler. Native `input`, not React's synthetic
            // `onChange`, because that is the event the legacy bound and the
            // one a probe dispatches.
            ref={(element) => {
              if (!element) return;
              // AND WHAT CHANGES THE QUERY FROM OUTSIDE has to reach the field:
              // the clear cross, or a driven state. The legacy got this for
              // free by rebuilding the node; an uncontrolled input keeps what
              // was typed, so a cross that emptied the list would have left the
              // word sitting in the field. Assigning only when the two DIFFER
              // is what keeps this from touching the node mid-word — while one
              // types, they are equal.
              const query = state.q as string;
              if (element.value !== query) element.value = query;
              // The ATTRIBUTE too. `defaultValue` writes it at mount only, and
              // the legacy re-emitted it on every draw — so anything reading
              // the serialised markup (the fidelity oracle included) would see
              // an empty field over one that shows a word.
              if (element.getAttribute("value") !== query)
                element.setAttribute("value", query);
              const commit = () => {
                // ONLY THE QUERY. Resetting a page cursor and clearing an error
                // beside it is what the interface had to do while it owned
                // both; the query KEY carries the search now, so typing asks a
                // different question, which has its own pages and its own
                // error by construction.
                writeUiState({ q: element.value });
                render();
              };
              element.addEventListener("input", commit);
              return () => element.removeEventListener("input", commit);
            }}
          />
          {state.q ? (
            <button
              className={searchClear()}
              data-clearq="lib"
              aria-label={t("screens.library.clearLabel")}
            >
              <Icon paths={icons.x} />
            </button>
          ) : null}
        </div>
        <div className={pillBar()}>
          <div className={pillScroll()} data-part="pill/list">
            {state.libLens === "cat"
              ? CATS.map((category) => (
                  <button
                    key={category.id}
                    className={filterPill()}
                    data-part="pill"
                    aria-pressed={state.libCat === category.id}
                    data-cat={category.id}
                  >
                    {category.l}
                    <span className={filterPillCount()}>{category.c}</span>
                  </button>
                ))
              : null}
          </div>
          <div className={viewSwitchWrap()}>
            <div className={viewSwitch()} data-part="view/switch">
              <button
                className={viewSwitchButton()}
                aria-pressed={state.libMode === "list"}
                data-lmode="list"
                aria-label={t("screens.library.listLabel")}
              >
                <Icon paths={icons.list} />
              </button>
              <button
                className={viewSwitchButton()}
                aria-pressed={state.libMode === "grid"}
                data-lmode="grid"
                aria-label={t("screens.library.gridLabel")}
              >
                <Icon paths={icons.grid} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
