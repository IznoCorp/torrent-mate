// The « Trackers » tab: one row per configured tracker.
//
// EACH ROW IS ITS OWN TRACKER'S, never an average: the ratio, the trend said in
// words and the Download / Upload volumes are the ones its own answer carries
// (§ 18, NE-DOIT-PAS-1). The rows keep the configuration's order — never
// re-sorted by ratio, which would move the row being read.
//
// A ROW OPENS ITS PANEL, as a torrent's card does (the operator's Q3: « de la
// cohérence partout »), and keeps ONE control of its own at its end: the
// activation switch, « facilement ». It files the SAME pending edit Réglages
// files for `tracker.providers.<name>.enabled`, written by the same save bar —
// one write, two doors. A tracker a failure switched off says why; switching it
// back on while the failure persists is REFUSED by the engine, and the refusal
// stays under the row, in the engine's words, never a toast that leaves.
import { useRights } from "../../lib/account";
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import i18next from "i18next";
import { Skeletons, SurfaceError } from "../../ui/state-surfaces";
import { Markup, emptyNoteMarkup } from "../../ui/markup";
import { Legend } from "../../ui/legend";
import { Switch } from "../../ui/switch";
import { useStoreContent } from "../../lib/store-access";
import { pendingEdits } from "../../lib/pending-edits-door";
import {
  chip, emptyNote, factDetail, factList, factName, factRow, factRowBody, factValue, surfaceError, type ChipTone,
} from "../../ui/variants";
import { written } from "../../lib/byte-size";
import { dayOf } from "./format";
import { legendOf, type Code } from "./torrent-card";
import { rosterLine } from "./cross-seed-state";
import { alertOf, useDownloads, useObligations, useSettingsCatalogue, useTrackers, type Alert, type Tracker } from "./queries";

// The status of a write the engine refuses: the value will not be taken.
const REFUSED = 422;

// A billion bytes: the « Go » the interface writes volumes in.
const GIGABYTE = 1_000_000_000;

/** One chip a row wears, the word its legend entry says, and the part its readers find it by. */
type RosterMark = { tone: ChipTone; label: string; word: string; part: string };

/**
 * The setting one tracker's activation is kept under — the one Réglages draws.
 *
 * @param tracker The tracker's configured name.
 * @returns The setting's identity, `<file>:<key>`.
 */
export function activationSetting(tracker: string): string {
  return `tracker:tracker.providers.${tracker}.enabled`;
}

/**
 * Why a tracker a failure switched off is off, and since when.
 *
 * @param tracker The tracker, as its own answer carries it.
 * @returns The sentence, or null unless a failure switched it off.
 */
export function failureSentence(tracker: Tracker): string | null {
  const off = tracker.disabled;
  if (off === null || off.by !== "failure") return null;
  return i18next.t("screens.trackers.failureSince", {
    reason: i18next.t(`screens.trackers.failureReasons.${off.reason ?? "other"}`),
    date: off.since === null ? "?" : dayOf(off.since),
  });
}

/**
 * The chips one row wears — the row and the legend read this one derivation.
 *
 * @param tracker The tracker, as its own answer carries it.
 * @param alert The page's one alert derivation.
 * @returns The chips, in the order they are read.
 */
export function rosterMarks(tracker: Tracker, alert: Alert): RosterMark[] {
  const say = (key: string, values: Record<string, unknown> = {}) => i18next.t(`screens.trackers.${key}`, values);
  const marks: RosterMark[] = [];
  if (tracker.disabled !== null) {
    const byFailure = tracker.disabled.by === "failure";
    marks.push({
      tone: byFailure ? "danger" : "neutral",
      label: say("disabledByOperator"),
      word: say(byFailure ? "legendFailure" : "legendOperator"),
      part: "trackers/disabled",
    });
  }
  if (alert.under.has(tracker.name)) {
    marks.push({
      tone: "warning",
      label: say("alertBelowThreshold", { threshold: written(tracker.alertThreshold ?? 0, 2) }),
      word: say("legendAlert"),
      part: "trackers/alert",
    });
  }
  const unseen = alert.unseen.get(tracker.name) ?? 0;
  if (unseen > 0) {
    marks.push({
      tone: "danger", label: say("brokenObligations", { count: unseen }), word: say("legendBroken"),
      part: "trackers/broken-obligations",
    });
  }
  return marks;
}

/**
 * One tracker's row: its summary, which opens its panel, and its switch.
 *
 * @param props.tracker The tracker, as its own answer carries it.
 * @param props.alert The page's one alert derivation.
 * @returns The row.
 */
function TrackerRow({ tracker, alert }: { tracker: Tracker; alert: Alert }): ReactElement {
  const { t } = useTranslation();
  const identity = activationSetting(tracker.name);
  // THE SWITCH DRAWS THE PENDING VALUE when an edit waits, the served one otherwise.
  const pending = pendingEdits()?.pending(identity);
  const on = pending === undefined ? tracker.enabled : pending.value === true;
  const refusal = pendingEdits()?.refusal(identity);
  const control = useRights().holds("trackers.control");
  const marks = rosterMarks(tracker, alert);
  return (
    <li className={factRow({ withControl: true })} data-part="trackers/entry" data-tracker={tracker.name}
      data-enabled={String(tracker.enabled)}>
      {/* THE NAME AND THE RATIO ON ONE LINE of the body's grid, as a fact row is designed. */}
      <button className={factRowBody({ withTarget: true })} data-part="trackers/body" data-tracker-open={tracker.name}>
        <span className={factName()} data-part="trackers/name">{tracker.name}</span>
        <span className={factValue()} data-part="trackers/ratio">
          {tracker.ratio === null ? t("screens.trackers.ratioUnknown") : t("screens.trackers.ratio", { ratio: written(tracker.ratio, 2) })}
        </span>
        {tracker.enabled ? (
          <>
            <span className={factDetail()} data-part="trackers/trend">
              {t("screens.trackers.trend", { trend: t(`screens.trackers.trends.${tracker.trend}`) })}
            </span>
            <span className={factDetail()} data-part="trackers/volumes">
              {t("screens.trackers.volumes", {
                downloaded: written(tracker.downloadedBytes / GIGABYTE, 1),
                uploaded: written(tracker.uploadedBytes / GIGABYTE, 1),
              })}
            </span>
          </>
        ) : null}
        {failureSentence(tracker) === null ? null : (
          <span className={factDetail()} data-part="trackers/failure">{failureSentence(tracker)}</span>
        )}
        {/* ITS CROSS-SEED AT REST, on its own line of the body's grid, never beside the ratio (S1). */}
        <span className={factDetail()} data-part="trackers/cross-seed"
          data-engine={String(tracker.crossSeed.engineEnabled)} data-own={String(tracker.crossSeed.enabled)}
          data-active={tracker.crossSeed.active} data-failed={tracker.crossSeed.failed}>
          {rosterLine(tracker.crossSeed)}
        </span>
        {marks.length > 0 ? (
          <span className={factDetail()}>
            {marks.map((mark) => (
              <span key={mark.part} className={chip({ tone: mark.tone })} data-part={mark.part} data-tone={mark.tone}
                data-reason={mark.part === "trackers/disabled" ? tracker.disabled?.reason ?? "" : undefined}>
                {mark.label}
              </span>
            ))}
          </span>
        ) : null}
      </button>
      {/* THE SWITCH IS A WRITE (`trackers.control`): the entry still says its state. */}
      {control ? <Switch checked={on} label={t("screens.trackers.switchLabel", { tracker: tracker.name })}
        data-part="trackers/switch" data-tracker-switch={tracker.name} /> : null}
      {refusal === undefined ? null : (
        // A REFUSAL (422) IS THE ENGINE'S ANSWER; any other failure left the edit pending.
        <p className={surfaceError({ tone: "danger" })} role="status" data-part="trackers/refusal"
          data-status={refusal.status}>
          <b>{t(refusal.status === REFUSED ? "screens.trackers.refusedLead" : "screens.trackers.writeFailedLead")}</b>
          {refusal.detail}
        </p>
      )}
    </li>
  );
}

/**
 * The « Trackers » tab.
 *
 * @returns The roster under its legend, or the sentence saying none is
 *     configured; while the read is in flight, its skeletons, and when it
 *     failed, the failure.
 */
export function TrackersTab(): ReactElement {
  const { t } = useTranslation();
  // A PENDING EDIT FILED BY THE SWITCH is a store bump, never a new answer: the
  // tab listens to it, so the switch moves under the finger.
  useStoreContent((content) => content.version);
  const read = useTrackers();
  const trackers = read.data;
  const { data: downloads } = useDownloads();
  const { data: obligations } = useObligations();
  // THE SAME CATALOGUE Réglages reads, so the switch can file its edit — and the
  // panel's policy rows read it too.
  useSettingsCatalogue();
  // THE READ IN FLIGHT, OR FAILED, IS SAID — never an empty tab standing for either.
  if (read.isError) {
    return <SurfaceError subject={t("screens.trackers.errorSubject")} onRetry={() => void read.refetch()} />;
  }
  if (!trackers) return <Skeletons count={3} shape="card" />;
  const alert = alertOf(trackers, downloads?.downloads ?? [], obligations?.items ?? []);
  if (trackers.length === 0) {
    return (
      <Markup
        className={emptyNote()} data-part="empty-state"
        html={emptyNoteMarkup(t("screens.trackers.empty"), t("screens.trackers.emptyBody"))}
      />
    );
  }
  // THE LEGEND READS THE CHIPS THE ROWS DRAW, only those present.
  const codes: Code[] = trackers.flatMap((tracker) =>
    rosterMarks(tracker, alert).map((mark): Code => ({ kind: "chip", tone: mark.tone, word: mark.word })));
  return (
    <>
      <Legend entries={legendOf(codes)} />
      <ol className={factList()} data-part="trackers/roster">
        {trackers.map((tracker) => <TrackerRow key={tracker.name} tracker={tracker} alert={alert} />)}
      </ol>
    </>
  );
}
