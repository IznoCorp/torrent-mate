import { useEngineDrawing } from "../../lib/engine-drawing";
import { useTranslation } from "react-i18next";
import type { ReactElement } from "react";
import { Icon } from "../../ui/icon";
import { useAcquisitionQueue } from "../../lib/queue";
import { useUiState } from "../../lib/store-access";
import { moreButton, segment, segmentCount, segmentTab, viewTabs } from "../../ui/variants";
import { fingerMore, fingerTab } from "./variants";

// The tab bar, and the « more » control that opens the watch-and-obligations
// sheet. Shared by the four surfaces below.
export function AcquisitionTabs(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  const { icons } = useEngineDrawing();
  // THE BADGE COUNTS WHAT IS WAITING, from the same read the deck draws — two
  // counts of one queue is the standing way to make the operator see two
  // truths (§13).
  const scenario = state.scen === "loaded" ? "loaded" : "";
  const { data: queue } = useAcquisitionQueue(scenario);
  // THE ORDER IS THE OPERATOR'S: « Suivis · En cours · À traiter · Découvrir ».
  // The tab opened by default is derived, wherever it stands in the row.
  const tabs = [
    { id: "follows", label: t("screens.acquisition.tabFollows") },
    {
      id: "now",
      label: t("screens.acquisition.tabNow"),
      count: (queue?.takeable ?? []).length + (queue?.blocked ?? []).length,
    },
    { id: "todo", label: t("screens.acquisition.tabTodo") },
    { id: "discover", label: t("screens.acquisition.tabDiscover") },
  ];
  return (
    <div className={viewTabs()} data-region="acquisition/tabs">
      <div className={segment()} data-part="segment" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`${segmentTab()} ${fingerTab()}`}
            role="tab"
            aria-selected={state.acqTab === tab.id}
            data-acqtab={tab.id}
          >
            {tab.label}
            {tab.count ? <span className={segmentCount()} data-part="segment/count">{tab.count}</span> : null}
          </button>
        ))}
      </div>
      <button
        className={`${moreButton()} ${fingerMore()}`}
        aria-label={t("screens.acquisition.moreLabel")}
        data-more
      >
        <Icon paths={icons.more} />
      </button>
    </div>
  );
}
