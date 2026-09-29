// « Trackers » — a page of the bottom bar: the ratio, tracker by tracker.
//
// Its body is the page's own oracle region, `trackers/body`, set by the page
// host from the navigation row. Two tabs, « Torrents » and « Trackers », are
// DIALS of the page — the address carries the one open — and each draws its
// own list below the strip.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { useUiState } from "../../lib/store-access";
import { segment, segmentTab, viewTabs } from "../../ui/variants";
import { trackersTab } from "./variants";
import { TorrentsTab } from "./torrents-tab";
import { TrackersTab } from "./trackers-tab";
import { PendingEditsBar } from "../../lib/save-bar-door";

/**
 * The « Trackers » page.
 *
 * @returns The page's body.
 */
export function TrackersPage(): ReactElement {
  const state = useUiState();
  const { t } = useTranslation();
  // THE ORDER IS THE OPERATOR'S: « Torrents » then « Trackers ».
  const tabs = [
    { id: "torrents", label: t("screens.trackers.tabTorrents") },
    { id: "trackers", label: t("screens.trackers.tabTrackers") },
  ];
  return (
    <div data-part="trackers">
      <div className={viewTabs()} data-part="trackers/tabs">
        <div className={segment()} data-part="segment" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`${segmentTab()} ${trackersTab()}`}
              role="tab"
              aria-selected={state.trackersTab === tab.id}
              data-part="trackers/tab"
              data-trackers-tab={tab.id}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      {state.trackersTab === "trackers" ? <TrackersTab /> : <TorrentsTab />}
      {/* A policy edited here is saved here: the settings' own bar. */}
      <PendingEditsBar />
    </div>
  );
}
