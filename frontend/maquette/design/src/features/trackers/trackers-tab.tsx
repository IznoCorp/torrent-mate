// The « Trackers » tab: one entry per configured tracker.
//
// EACH ENTRY IS ITS OWN TRACKER'S, never an average: the ratio, the trend said
// in words and the Download / Upload volumes are the ones its own answer
// carries (§ 18, NE-DOIT-PAS-1). The entries keep the configuration's order —
// never re-sorted by ratio, which would move the row being read.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { Disclosure } from "../../ui/disclosure";
import { FactRows } from "../../ui/fact-rows";
import { Markup, emptyNoteMarkup } from "../../ui/markup";
import { useUiState } from "../../lib/store-access";
import {
  chip, crossReference, emptyNote, factDetail, factList, factName, factRow, factRowBody, factValue, guidance,
} from "../../ui/variants";
import { written } from "./format";
import {
  alertOf, useDownloads, useObligations, useSettingsCatalogue, useTrackers, type Alert, type Setting, type Tracker,
} from "./queries";

// THE POLICY IS THE TRACKER'S ECONOMY BLOCK, in the tracker's configuration
// file: the floor, the seed time and the alert threshold, in that order.
const POLICY_FILE = "tracker";
const POLICY_FIELDS = [
  { field: "min_ratio", label: "screens.trackers.minRatio" },
  { field: "min_seed_time", label: "screens.trackers.minSeedTime" },
  { field: "alert_threshold", label: "screens.trackers.alertThreshold" },
] as const;

// A billion bytes: the « Go » the interface writes volumes in.
const GIGABYTE = 1_000_000_000;

/**
 * One tracker's policy: each field is the SAME setting the settings page draws,
 * and a tap raises that setting's own panel — one write, whichever door.
 *
 * @param props.tracker The tracker's name.
 * @param props.settings The settings catalogue.
 * @returns The policy, or the sentence saying none is set.
 */
function TrackerPolicy({ tracker, settings }: { tracker: string; settings: Setting[] }): ReactElement {
  const { t } = useTranslation();
  const rows = POLICY_FIELDS.flatMap(({ field, label }) => {
    const key = `tracker.providers.${tracker}.economy.${field}`;
    const setting = settings.find((candidate) => candidate.file === POLICY_FILE && candidate.key === key);
    return setting === undefined
      ? []
      : [{ label: t(label), value: String(setting.displayedValue ?? ""), target: { setting: `${POLICY_FILE}:${key}` } }];
  });
  return (
    <div data-part="trackers/policy">
      {rows.length === 0 ? (
        <p className={guidance()} data-part="trackers/policy-unset">{t("screens.trackers.policyUnset")}</p>
      ) : (
        <>
          <ol className={factList()}>
            <FactRows rows={rows} />
          </ol>
          <p className={guidance()} data-part="trackers/policy-guidance">{t("screens.trackers.floorGuidance")}</p>
        </>
      )}
      <button className={crossReference()} data-part="trackers/see-torrents" data-trackers-filter={tracker}>
        {t("screens.trackers.seeTorrents")}
      </button>
    </div>
  );
}

/**
 * One tracker's entry: its summary, folding away its policy.
 *
 * @param props.tracker The tracker, as its own answer carries it.
 * @param props.settings The settings catalogue.
 * @param props.open Whether the address opened it.
 * @returns The entry.
 */
function TrackerEntry(
  { tracker, settings, open, alert }: { tracker: Tracker; settings: Setting[]; open: boolean; alert: Alert },
): ReactElement {
  return (
    <li data-part="trackers/entry" data-tracker={tracker.name}>
      <Disclosure open={open} summary={<TrackerSummary tracker={tracker} alert={alert} />}>
        <TrackerPolicy tracker={tracker.name} settings={settings} />
      </Disclosure>
    </li>
  );
}

/**
 * What a closed entry says: the tracker, its trend, its volumes, its ratio —
 * and, when it is in alert, why: under its own threshold, or its identifier
 * refused.
 *
 * @param props.tracker The tracker, as its own answer carries it.
 * @param props.alert The page's one alert derivation.
 * @returns The entry's summary.
 */
function TrackerSummary({ tracker, alert }: { tracker: Tracker; alert: Alert }): ReactElement {
  const { t } = useTranslation();
  return (
    <span className={factRow()}>
      <span className={factRowBody()}>
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
        {alert.under.has(tracker.name) ? (
          <span className={chip({ tone: "warning" })} data-part="trackers/alert">
            {t("screens.trackers.alertBelowThreshold", { threshold: written(tracker.alertThreshold ?? 0, 2) })}
          </span>
        ) : null}
        {alert.refused.has(tracker.name) ? (
          <span className={chip({ tone: "danger" })} data-part="trackers/identifier-refused">
            {t("screens.trackers.identifierRefused")}
          </span>
        ) : null}
      </span>
      <span className={factValue()} data-part="trackers/ratio">
        {tracker.ratio === null ? t("screens.trackers.ratioUnknown") : t("screens.trackers.ratio", { ratio: written(tracker.ratio, 2) })}
      </span>
    </span>
  );
}

/**
 * The « Trackers » tab.
 *
 * @returns The roster, or the sentence saying none is configured.
 */
export function TrackersTab(): ReactElement | null {
  const { t } = useTranslation();
  const state = useUiState();
  const { data: trackers } = useTrackers();
  const { data: downloads } = useDownloads();
  const { data: obligations } = useObligations();
  const settings = useSettingsCatalogue() ?? [];
  if (!trackers) return null;
  const alert = alertOf(trackers, downloads?.downloads ?? [], obligations?.items ?? []);
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
      {trackers.map((tracker) => (
        <TrackerEntry
          key={tracker.name} tracker={tracker} settings={settings} alert={alert}
          open={state.trackersFilter === tracker.name}
        />
      ))}
    </ol>
  );
}
