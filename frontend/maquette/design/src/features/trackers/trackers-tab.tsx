// The « Trackers » tab: one entry per configured tracker.
//
// EACH ENTRY IS ITS OWN TRACKER'S, never an average: the ratio, the trend said
// in words and the Download / Upload volumes are the ones its own answer
// carries (§ 18, NE-DOIT-PAS-1). The entries keep the configuration's order —
// never re-sorted by ratio, which would move the row being read.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { Markup, emptyNoteMarkup } from "../../ui/markup";
import { emptyNote, factDetail, factList, factName, factRow, factRowBody, factValue } from "../../ui/variants";
import { useTrackers, type Tracker } from "./queries";

// A billion bytes: the « Go » the interface writes volumes in.
const GIGABYTE = 1_000_000_000;

/**
 * A number as the interface writes it, with fixed decimals.
 *
 * @param value The number.
 * @param decimals How many decimals it carries.
 * @returns The number, written in the interface's language.
 */
function written(value: number, decimals: number): string {
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * One tracker's collapsed entry.
 *
 * @param props.tracker The tracker, as its own answer carries it.
 * @returns The entry.
 */
function TrackerEntry({ tracker }: { tracker: Tracker }): ReactElement {
  const { t } = useTranslation();
  return (
    <li className={factRow()} data-part="trackers/entry" data-tracker={tracker.name}>
      <div className={factRowBody()}>
        <span className={factName()}>{tracker.name}</span>
        <span className={factDetail()} data-part="trackers/trend">
          {t("screens.trackers.trend", { trend: t(`screens.trackers.trends.${tracker.trend}`) })}
        </span>
        <span className={factDetail()} data-part="trackers/volumes">
          {t("screens.trackers.volumes", {
            downloaded: written(tracker.downloadedBytes / GIGABYTE, 1),
            uploaded: written(tracker.uploadedBytes / GIGABYTE, 1),
          })}
        </span>
      </div>
      <span className={factValue()} data-part="trackers/ratio">
        {tracker.ratio === null ? t("screens.trackers.ratioUnknown") : t("screens.trackers.ratio", { ratio: written(tracker.ratio, 2) })}
      </span>
    </li>
  );
}

/**
 * The « Trackers » tab.
 *
 * @returns The roster, or the sentence saying none is configured.
 */
export function TrackersTab(): ReactElement | null {
  const { t } = useTranslation();
  const { data: trackers } = useTrackers();
  if (!trackers) return null;
  if (trackers.length === 0) {
    return (
      <Markup
        className={emptyNote()} data-part="empty-state"
        html={emptyNoteMarkup(t("screens.trackers.empty"), t("screens.trackers.emptyBody"))}
      />
    );
  }
  return (
    <ol className={factList()} data-part="trackers/roster">
      {trackers.map((tracker) => <TrackerEntry key={tracker.name} tracker={tracker} />)}
    </ol>
  );
}
