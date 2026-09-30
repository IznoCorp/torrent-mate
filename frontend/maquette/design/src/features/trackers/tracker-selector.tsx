// The tracker selector — ONE pill atop the « Torrents » list, in the filter zone
// every list draws above itself.
//
// THE PILL SAYS THE FILTER: « Tous les trackers » when the list is whole, the
// tracker's name — pressed — when it is not, and the number of entries shown.
// A tap opens the bottom panel with the choices, because the list of trackers
// is long (the operator: « la liste de tracker peut être longue ») and pills
// scrolling sideways hide what is off-screen.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { useUiState } from "../../lib/store-access";
import { useDownloads } from "./queries";
import { filterPill, filterPillCount, filterZone, pillBar, pillScroll } from "../../ui/variants";

/**
 * The selector.
 *
 * @returns The filter zone holding the pill; its count once the entries are read.
 */
export function TrackerSelector(): ReactElement {
  const { t } = useTranslation();
  const state = useUiState();
  const tracker = typeof state.trackersFilter === "string" ? state.trackersFilter : "";
  const entries = useDownloads().data?.downloads;
  const count = entries?.filter((entry) => tracker === "" || entry.tracker === tracker).length;
  return (
    <div className={filterZone()} data-part="torrents/filters">
      <div className={pillBar()}>
        <div className={pillScroll()} data-part="pill/list">
          <button
            className={filterPill()}
            data-part="torrents/selector"
            aria-pressed={tracker !== ""}
            aria-haspopup="dialog"
            data-trackers-selector=""
          >
            {tracker === "" ? t("screens.torrents.selectorAll") : tracker}
            {count === undefined ? null : (
              <span className={filterPillCount()} data-part="torrents/selector-count">{count}</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
