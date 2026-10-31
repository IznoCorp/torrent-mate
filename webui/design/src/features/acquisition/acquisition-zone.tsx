// The filter and sort zone every tab of Acquisition draws, in ONE place.
//
// THE OPERATOR (B-706): « toute la zone de trie et de filtre devrait être
// présente sur tout les onglets (à l'exception du switch d'affichage […]) » and
// « une impression de stabilité quand on passe d'un onglet à l'autre ». So the
// three tabs draw the same component, at the same place — a sibling of the
// body, right under the tab bar — and what differs is only what is fed to it:
// the tab's own search state, its two pills, and whether it can show the
// display switch.
//
// A TAB THAT CANNOT SHOW THE SWITCH KEEPS ITS SLOT: the switch is the tallest
// thing of the row, so leaving it out would shorten the zone and lift the list.
// The slot is drawn invisible, divider included, with the switch's own classes, so the row keeps
// its height and the pills their places.
import { useEngineDrawing } from "../../lib/engine-drawing";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { redraw } from "../../lib/shell-doors";
import { useUiState, writeUiState } from "../../lib/store-access";
import { PillSelect, type PillSelectProps } from "../../ui/pill-select";
import { filterZone, pillBar, pillScroll, searchClear, searchField, searchInput, viewSwitch, viewSwitchButton, viewSwitchWrap } from "../../ui/variants";

/** What a tab feeds the zone. */
export type AcquisitionZoneProps = {
  /** The store key the search typed is kept under, one per tab. */
  searchKey: string;
  /** The search field's id. */
  searchId: string;
  /** The search field's accessible name. */
  searchLabel: string;
  /** The filter pill: the choice in force, the cards it keeps, its tap's verb. */
  filter: PillSelectProps;
  /** The sort pill. */
  sort: PillSelectProps;
  /** Whether the tab can show its list in several modes — the display switch. */
  modes: boolean;
};

// The three modes of the display switch, in the order it draws them.
const MODES = [
  { mode: "list", icon: "list", label: "modeList" },
  { mode: "group", icon: "group", label: "modeGroup" },
  { mode: "grid", icon: "grid", label: "modeGrid" },
] as const;

/**
 * The zone: the search field, the filter pill, the sort pill, and the display
 * switch where the tab can show it.
 *
 * @param props What the tab feeds it.
 * @returns The zone.
 */
export function AcquisitionZone({ searchKey, searchId, searchLabel, filter, sort, modes }: AcquisitionZoneProps): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  const search = String(state[searchKey] ?? "");
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
          // A TITLE STARTS WITH A CAPITAL (B-694): the keyboard's first capital, `sentences`, and
          // no correction — a title is a proper noun, often foreign, that autocorrect would mangle (B-690).
          autoCapitalize="sentences"
          autoCorrect="off"
          id={searchId}
          defaultValue={search}
          placeholder={t("screens.acquisition.filterPlaceholder")}
          aria-label={searchLabel}
          ref={(element) => {
            if (!element) return;
            // What changes the search from OUTSIDE — the clear cross — has to
            // reach the field, and only when the two differ, so nothing
            // touches the node mid-word. The ATTRIBUTE follows too: the
            // legacy re-emitted it on every draw.
            if (element.value !== search) element.value = search;
            if (element.getAttribute("value") !== search) element.setAttribute("value", search);
            const commit = () => {
              writeUiState({ [searchKey]: element.value });
              redraw();
            };
            element.addEventListener("input", commit);
            return () => element.removeEventListener("input", commit);
          }}
        />
        {search ? (
          <button
            className={searchClear()}
            // « Suivis »' key is the verb's default, so its attribute stays empty.
            data-clear-filter={searchKey === "filter" ? "" : searchKey}
            aria-label={t("screens.acquisition.clearLabel")}
          >
            <Icon paths={icons.x} />
          </button>
        ) : null}
      </div>
      <div className={pillBar()}>
        <div className={pillScroll()} data-part="pill/list">
          <PillSelect {...filter} />
          <PillSelect {...sort} />
        </div>
        {/* THE WRAPPER CARRIES THE DIVIDER (a pseudo-element), so the slot is hidden whole, not its switch alone. */}
        <div className={`${viewSwitchWrap()}${modes ? "" : " invisible"}`}>
          {modes ? (
            <div className={viewSwitch()} data-part="view/switch">
              {MODES.map(({ mode, icon, label }) => (
                <button
                  key={mode}
                  className={viewSwitchButton()}
                  aria-pressed={state.followMode === mode}
                  data-active={state.followMode === mode}
                  data-fmode={mode}
                  aria-label={t(`screens.acquisition.${label}`)}
                >
                  <Icon paths={icons[icon]} />
                </button>
              ))}
            </div>
          ) : (
            // THE SLOT KEPT (see the head of this file): the switch's own classes
            // and icons, under the invisible wrapper, out of the accessibility tree.
            <div className={viewSwitch()} data-part="view/switch-slot" aria-hidden="true">
              {MODES.map(({ mode, icon }) => (
                <span key={mode} className={viewSwitchButton()}>
                  <Icon paths={icons[icon]} />
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
