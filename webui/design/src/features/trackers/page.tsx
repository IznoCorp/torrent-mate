// « Trackers » — a page of the bottom bar: the ratio, tracker by tracker.
//
// Two tabs, « Torrents » and « Trackers », are DIALS of the page — the address
// carries the one open — and each draws its own list below the strip. THE BAR IS
// THE PAGE'S HEAD, as on every page that draws one: it sits above the page
// column (`body`, the oracle region `trackers/body`), never inside it, where the
// column's padding would stack on the bar's own.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { useUiState } from "../../lib/store-access";
import { Tabs } from "../../ui/tabs";
import { body } from "../../ui/variants";
import { TorrentsTab } from "./torrents-tab";
import { TrackersTab } from "./trackers-tab";
import { TrackerSelector } from "./tracker-selector";

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
    <>
      <Tabs tabs={tabs} selected={String(state.trackersTab)} attribute="data-trackers-tab" />
      {/* THE SELECTOR IS THE LIST'S HEAD, in the filter zone every list draws above itself. */}
      {state.trackersTab === "trackers" ? null : <TrackerSelector />}
      <div className={body()} data-part="trackers" data-region="trackers/body">
        {state.trackersTab === "trackers" ? <TrackersTab /> : <TorrentsTab />}
      </div>
    </>
  );
}
