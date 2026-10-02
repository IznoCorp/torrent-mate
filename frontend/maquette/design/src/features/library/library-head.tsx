// The head of the library page: the three lenses, the search field with its
// own native handler, the filter pill and the sort pill, and the list/grid
// switch.
//
// THE ONE PILL OF EVERY LIST (`ui/pill-select.tsx`, maquette-blocked DECIDED 1,
// § 1.9): the row of category pills became ONE filter pill whose panel lists
// the categories with their counts, and the count line's sort control became
// the sort pill beside it, its six ways unchanged. Both stay remembered as they
// were — the category in the store and the address, the sort in the store.
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { redraw } from "../../lib/shell-doors";
import { useLibraryCategories, useLibraryIncomplete, useLibraryListing } from "./queries";
import type { LibraryCategory } from "./types";
import { useUiState, writeUiState } from "../../lib/store-access";
import { filterZone, pillBar, pillScroll, searchClear, searchField, searchInput, viewSwitch, viewSwitchButton, viewSwitchWrap } from "../../ui/variants";
import { Tabs } from "../../ui/tabs";
import { PillSelect } from "../../ui/pill-select";
import { categoryCount } from "./category-filter";
import { SORT_KEYS, sortWays } from "./sorting";

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

/**
 * The filter pill: the category in force, and what it counts on the lens.
 *
 * @param props.category The category in force, once the categories are read.
 * @param props.count What it counts on the lens.
 * @returns The pill.
 */
function FilterPill({ category, count }: { category: LibraryCategory | undefined; count: number | undefined }): ReactElement {
  return (
    <PillSelect
      label={category?.label ?? ""}
      count={count}
      pressed={category !== undefined && category.includes !== null}
      attributes={{ "data-library-filter-pill": "" }}
    />
  );
}

/**
 * The filter pill on « Récents »: it counts the rows the lens holds in its
 * category, never the library. It reads the lens' own listing (the same key,
 * so the same cached answer the list draws), and it is a component of its own
 * so the read exists only while « Récents » is drawn.
 *
 * @param props.category The category in force.
 * @returns The pill.
 */
function RecentFilterPill({ category }: { category: LibraryCategory | undefined }): ReactElement {
  const state = useUiState();
  const recent = useLibraryListing(
    String(state.q ?? ""),
    "",
    String(state.sortKey ?? ""),
    Boolean(state.sortReversed),
  );
  const rows = (recent.data?.pages ?? []).flatMap((page) => page.items);
  return <FilterPill category={category} count={category && categoryCount(category, "rec", [], rows)} />;
}

export function LibraryHead(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  const { data: CATS = [] } = useLibraryCategories();
  // The page's own read of « Incomplets », shared by the query cache: the same
  // answer the lens draws, never a second one.
  const { data: INCOMPLETE = [] } = useLibraryIncomplete();
  const lenses = [
    { id: "cat", label: t("screens.library.lensMedia") },
    { id: "rec", label: t("screens.library.lensRecent") },
    { id: "inc", label: t("screens.library.lensIncomplete"), count: INCOMPLETE_COUNT },
  ];
  const category = CATS.find((entry) => entry.id === state.libCat);
  return (
    <>
      <Tabs tabs={lenses} selected={String(state.libLens)} attribute="data-lens" data-region="library/tabs" />
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
                // THE SELECTION STAYS. Searching narrows what is on screen,
                // and a tick it hides is still counted by the bar and named by
                // the delete dialog; the selection is keyed by title, so it
                // cannot land on another medium.
                // ONLY THE QUERY. Resetting a page cursor and clearing an error
                // beside it is what the interface had to do while it owned
                // both; the query KEY carries the search now, so typing asks a
                // different question, which has its own pages and its own
                // error by construction.
                writeUiState({ q: element.value });
                redraw();
              };
              element.addEventListener("input", commit);
              return () => element.removeEventListener("input", commit);
            }}
          />
          {state.q ? (
            <button
              className={searchClear()}
              data-clear-search
              aria-label={t("screens.library.clearLabel")}
            >
              <Icon paths={icons.x} />
            </button>
          ) : null}
        </div>
        <div className={pillBar()}>
          <div className={pillScroll()} data-part="pill/list">
            {state.libLens === "rec" ? (
              <RecentFilterPill category={category} />
            ) : (
              <FilterPill category={category} count={category && categoryCount(category, String(state.libLens), INCOMPLETE, [])} />
            )}
            {/* THE SORT WHERE IT SORTED: « Médias », as the count line's control
                did — the six ways of `sorting.ts`, the one in force said. */}
            {state.libLens === "cat" ? (
              <PillSelect
                label={sortWays()[String(state.sortKey)]?.[state.sortReversed ? "inverse" : "normal"] ?? ""}
                pressed={state.sortKey !== SORT_KEYS[0] || Boolean(state.sortReversed)}
                attributes={{ "data-sort": "" }}
              />
            ) : null}
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
