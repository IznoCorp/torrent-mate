// A torrent's cross-seed, tracker by tracker — the block its panel draws (S3).
//
// RE-HOMED FROM THE ROW TO THE PANEL (L16-bis § 1.5): the card is a media card,
// and what a tap on its body raises is where the torrent's detail lives. The
// block is drawn on an ORIGIN entry only; a cross-seed's own entry says whose
// copy it is instead (S4).
//
// ONE ROW PER OTHER ELIGIBLE TRACKER, in the operator's six words, each with the
// date its state was taken and — on a refusal — its reason IN FULL: the sentence
// for its code, the kind of trouble, the candidate on that tracker and the
// source, never the bare code (§ 19 point 1, NE-DOIT-PAS-4). THE ORDER (F64):
// the failures the badge counts first, then the ordinary refusals, then
// « actif », « stoppé », « tracker sans cross-seed », and « sans correspondance »
// / « pas encore cherché » last — within a state, the newest first.
//
// A SECOND ACT BESIDE THE SEARCH (L23 § 2.3): « Créer et publier un torrent »,
// on the pairs nothing already cross-seeds, its origin seeding and its tracker
// accepting uploads. A published pair reads « actif » like a found one, dated
// « publié le »; a refused one « erreur de cross-seed », the tracker's own
// reason said beside the code's sentence — no seventh word (round 11).
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";
import { Chip } from "../../ui/chip";
import { Switch } from "../../ui/switch";
import type { Schemas } from "../../lib/contract-schemas";
import { actionButton, sheetActions, factActions, factDetail, factList, factName, factRow, factRowBody } from "../../ui/variants";
import { dayOf } from "./format";
import { useDownloads, useTrackers } from "./queries";
import type { SwitchWrite } from "./cross-seed-verbs";
import {
  CROSS_SEED_TONE, familyWord, isComplete, isFailure, isSearchable, isSeeding, isSwitchedOff, isUploadRefused,
  isUploadable, reasonSentence, stateWord, type CrossSeedPair, type UploadGate,
} from "./cross-seed-state";

// The block this file adds to the panel's map, declared beside what draws it.
declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    crossSeed: {
      /**
       * The origin entry: its hash, its release name, the tracker it runs on, how
       * much of it is held, and whether the client is seeding it whole.
       */
      origin: { infoHash: string; name: string; tracker: string; progress: number; seeding: boolean };
      pairs: CrossSeedPair[];
      titleExcluded: boolean;
    };
    crossSeedSwitch: {
      /** The tracker's configured name. */
      tracker: string;
      /** Its cross-seed, as the summary read answers it. */
      summary: Schemas["TrackerCrossSeed"];
      /** What its switch's write did in this visit, or null when it was not written. */
      switched: SwitchWrite | null;
    };
  }
}

// The seconds in a minute: the engine's delay is said in minutes.
const SECONDS_PER_MINUTE = 60;

// THE READING ORDER OF THE STATES (F64): a refusal splits in two, counted first.
const RANK: Readonly<Record<CrossSeedPair["state"], number>> = {
  error: 1,
  active: 2,
  stopped: 3,
  trackerWithout: 4,
  noMatch: 5,
  notSearched: 5,
};

/**
 * Where a pair reads in its block: a counted failure before every other state.
 *
 * @param pair The pair.
 * @returns Its rank, smaller first.
 */
function rankOf(pair: CrossSeedPair): number {
  return isFailure(pair) ? 0 : RANK[pair.state];
}

/**
 * The pairs in their reading order.
 *
 * @param pairs The origin's pairs, as the server answered them.
 * @returns A new list, ordered.
 */
export function orderedPairs(pairs: readonly CrossSeedPair[]): CrossSeedPair[] {
  const dated = (pair: CrossSeedPair) => pair.stoppedAt ?? pair.at ?? 0;
  return [...pairs].sort((one, other) => rankOf(one) - rankOf(other) || dated(other) - dated(one));
}

/**
 * When a pair's state was taken, in words — or nothing when the server has no date.
 *
 * @param pair The pair.
 * @param say The panel's words.
 * @returns The sentence, or null.
 */
function dateOf(pair: CrossSeedPair, say: (key: string, values?: Record<string, string>) => string): string | null {
  if (pair.state === "stopped" && pair.stoppedAt !== null) {
    return say(pair.stopCause === "switch" ? "stoppedBySwitch" : "stoppedByCut", { date: dayOf(pair.stoppedAt) });
  }
  if (pair.at === null) return null;
  const uploaded = pair.via === "upload";
  if (pair.state === "active") return say(uploaded ? "published" : "injected", { date: dayOf(pair.at) });
  return say(uploaded ? "publishTried" : "tried", { date: dayOf(pair.at) });
}

/** What a pair's row reads of its origin and of its tracker's two switches. */
type PairContext = {
  pair: CrossSeedPair;
  origin: PanelBlockMap["crossSeed"]["origin"];
  titleExcluded: boolean;
  /** Whether the pair's own tracker carries its cross-seed switch on. */
  trackerEnabled: boolean;
  /** Whether the pair's own tracker carries its « accepte les uploads » switch on. */
  acceptsUploads: boolean;
};

/**
 * What « Créer et publier un torrent » reads of a pair's context.
 *
 * @param context The pair and what its row reads.
 * @returns The gate.
 */
function gateOf({ origin, titleExcluded, trackerEnabled, acceptsUploads }: PairContext): UploadGate {
  return { titleExcluded, originSeeding: origin.seeding, trackerEnabled, acceptsUploads };
}

/**
 * What a pair offers: to cut it while it runs (round 9 Q5, Q8), to search it or
 * to publish a torrent there where nothing cross-seeds (L23 § 2.3), and to lift
 * its exclusion once excluded (round 9 Q11) — nothing the engine would refuse
 * (§ 17 point 1). A title excluded whole is lifted whole, never pair by pair.
 *
 * @param context The pair, its origin, and its tracker's two switches.
 * @returns The pair's buttons, or nothing.
 */
function PairActs(context: PairContext): ReactElement | null {
  const { pair, origin, titleExcluded, trackerEnabled } = context;
  const { t } = useTranslation();
  const say = (key: string) => t(`screens.crossSeed.panel.${key}`);
  const subject = `${origin.infoHash}:${pair.tracker}`;
  if (pair.state === "active") {
    return (
      <span className={factDetail()}>
        <button className={actionButton({ kind: "panelAction", tone: "danger" })} data-part="torrents/cross-seed-cut"
          data-cross-seed-cut={subject}>
          {say("cut")}
        </button>
      </span>
    );
  }
  // « CHERCHER UN CROSS-SEED » (OPEN 3 = A): only where the engine would act — a
  // pair with no match, in error, not yet searched or stopped, not excluded, its
  // original complete. A search already asked reads « en file », never « occupé ».
  if (pair.searching) {
    return <span className={factDetail()} data-part="torrents/cross-seed-queued"><b>{say("queued")}</b></span>;
  }
  // AN UPLOAD ASKED reads « en file » too, never « occupé » (DOIT-4), until its outcome arrives.
  if (pair.uploading) {
    return <span className={factDetail()} data-part="torrents/cross-seed-upload-queued"><b>{say("uploadQueued")}</b></span>;
  }
  const searchable = isSearchable(pair, titleExcluded, isComplete(origin), trackerEnabled);
  const uploadable = isUploadable(pair, gateOf(context));
  if (searchable || uploadable) {
    return (
      <span className={factDetail()}><span className={factActions()}>
        {searchable ? (
          <button className={actionButton({ kind: "panelAction", tone: "primary" })} data-part="torrents/cross-seed-search"
            data-cross-seed-search={subject}>
            {say("search")}
          </button>
        ) : null}
        {uploadable ? (
          <button className={actionButton({ kind: "panelAction", tone: "plain" })} data-part="torrents/cross-seed-upload"
            data-cross-seed-upload={subject}>
            {say("upload")}
          </button>
        ) : null}
      </span></span>
    );
  }
  if (pair.excluded && !titleExcluded) {
    return (
      <span className={factDetail()}>
        <button className={actionButton({ kind: "panelAction", tone: "plain" })} data-part="torrents/cross-seed-exclude"
          data-undo="" data-cross-seed-include={subject}>
          {say("include")}
        </button>
      </span>
    );
  }
  return null;
}

/**
 * One pair's row.
 *
 * @param context The pair, its origin, and its tracker's two switches.
 * @returns The row.
 */
function PairRow(context: PairContext): ReactElement {
  const { pair, origin, titleExcluded, trackerEnabled } = context;
  const { t } = useTranslation();
  const say = (key: string, values: Record<string, string> = {}) => t(`screens.crossSeed.panel.${key}`, values);
  const date = dateOf(pair, say);
  return (
    <li className={factRow()} data-part="torrents/cross-seed-row" data-tracker={pair.tracker} data-state={pair.state}
      data-failure={String(isFailure(pair))} data-excluded={String(pair.excluded)}>
      <div className={factRowBody()}>
        <span className={factName()}>{pair.tracker}</span>
        <span data-part="torrents/cross-seed-state" data-state={pair.state}>
          <Chip tone={CROSS_SEED_TONE[pair.state]} label={stateWord(pair.state)} />
        </span>
        {date === null ? null : <span className={factDetail()} data-part="torrents/cross-seed-date">{date}</span>}
        {pair.state === "error" && pair.reason !== null ? (
          <span className={factDetail()} data-part="torrents/cross-seed-reason" data-reason={pair.reason}>
            <b>{familyWord(pair.reason)}</b> — {reasonSentence(pair.reason)}
            <br />
            {pair.candidate === null || pair.via === "upload" ? null : (
              <>{say("candidate", { name: pair.candidate, tracker: pair.tracker })}<br /></>
            )}
            {pair.trackerReason === null ? null : (
              <><span data-part="torrents/cross-seed-tracker-reason">
                {say("trackerReason", { tracker: pair.tracker, reason: pair.trackerReason })}
              </span><br /></>
            )}
            {say("source", { name: origin.name, tracker: origin.tracker })}
          </span>
        ) : null}
        {pair.state === "notSearched" && pair.waitReason !== null ? (
          <span className={factDetail()} data-part="torrents/cross-seed-wait">
            {say("wait", { reason: t(`screens.crossSeed.waits.${pair.waitReason}`) })}
          </span>
        ) : isSwitchedOff(pair, titleExcluded, isComplete(origin), trackerEnabled) ? (
          <span className={factDetail()} data-part="torrents/cross-seed-wait">
            {say("wait", { reason: t("screens.crossSeed.waits.switchOff") })}
          </span>
        ) : null}
        {isUploadRefused(pair, gateOf(context)) ? (
          <span className={factDetail()} data-part="torrents/cross-seed-upload-off">{say("uploadOff", { tracker: pair.tracker })}</span>
        ) : null}
        {pair.excluded ? (
          <span className={factDetail()} data-part="torrents/cross-seed-excluded">{say("excluded")}</span>
        ) : null}
        <PairActs {...context} />
      </div>
    </li>
  );
}

/**
 * The block.
 *
 * @param props.block The origin, its pairs, and whether its title is excluded.
 * @returns The block.
 */
function CrossSeedBlock({ block: posed }: { block: { type: "crossSeed" } & PanelBlockMap["crossSeed"] }): ReactElement {
  const { t } = useTranslation();
  // THE BLOCK READS THE CACHE ITSELF: a panel draws what it read at open, and a
  // pair moved by an event, a search or a cut is drawn again in the render that
  // follows — never a stale « en file » (F59). The descriptor's pairs stand in
  // until the read is held.
  const downloads = useDownloads().data;
  const entry = downloads?.downloads.find((one) => one.infoHash === posed.origin.infoHash);
  const held = entry?.crossSeed;
  const quota = downloads?.crossSeedQuota;
  // THE PAIR'S OWN TRACKER SWITCH (§ 17 point 1): the same `/api/trackers` read
  // the page already holds (R-L17-k), never a second operation for this block.
  const trackers = useTrackers().data;
  const enabledOf = (tracker: string) => trackers?.find((one) => one.name === tracker)?.crossSeed.enabled ?? true;
  // « ACCEPTE LES UPLOADS » (round 11 OPEN 2 = B): unread, nothing is offered it might withdraw.
  const acceptsOf = (tracker: string) => trackers?.find((one) => one.name === tracker)?.crossSeed.acceptsUploads ?? false;
  const block = held && entry
    ? {
      ...posed, origin: { ...posed.origin, progress: entry.progress, seeding: isSeeding(entry) }, pairs: held.pairs,
      titleExcluded: held.titleExcluded,
    }
    : posed;
  const say = (key: string) => t(`screens.crossSeed.panel.${key}`);
  return (
    <section data-part="torrents/cross-seed" data-region="torrents/cross-seed" data-entry={block.origin.infoHash}
      data-title-excluded={String(block.titleExcluded)}>
      <p className={factDetail()}><b>{say("lead")}</b></p>
      {block.titleExcluded ? (
        <p className={factDetail()} data-part="torrents/cross-seed-title-excluded">{say("titleExcluded")}</p>
      ) : null}
      {block.pairs.length === 0 ? (
        <p className={factDetail()} data-part="torrents/cross-seed-none">{say("none")}</p>
      ) : (
        <ol className={factList()}>
          {orderedPairs(block.pairs).map((pair) => (
            <PairRow
              key={pair.tracker} pair={pair} origin={block.origin} titleExcluded={block.titleExcluded}
              trackerEnabled={enabledOf(pair.tracker)} acceptsUploads={acceptsOf(pair.tracker)}
            />
          ))}
        </ol>
      )}
      {/* THE ENGINE'S OWN BOUNDS, shown and never set here (F45: no 3-day window on a hand search). */}
      {quota === undefined ? null : (
        <p className={factDetail()} data-part="torrents/cross-seed-quota" data-used={quota.used} data-per-day={quota.perDay}>
          {t("screens.crossSeed.panel.quota", {
            used: quota.used, perDay: quota.perDay, delay: Math.round(quota.delaySeconds / SECONDS_PER_MINUTE),
          })}
        </p>
      )}
      {/* THE TITLE AS A WHOLE, on the origin, never on one tracker's line (round 9 Q11). */}
      <div className={sheetActions()}>
        <button className={actionButton({ kind: "panelAction", tone: block.titleExcluded ? "plain" : "danger" })}
          data-part="torrents/cross-seed-exclude" data-whole=""
          {...(block.titleExcluded
            ? { "data-undo": "", "data-cross-seed-include-title": block.origin.infoHash }
            : { "data-cross-seed-exclude-title": block.origin.infoHash })}>
          {say(block.titleExcluded ? "includeTitle" : "excludeTitle")}
        </button>
      </div>
    </section>
  );
}

/**
 * A tracker's cross-seed switch, in its panel (S2): its state in words and the
 * control that flips it — the SAME setting Réglages draws, one write, two doors.
 * THE ENGINE OFF IS A SEPARATE FACT, said above and never hiding the tracker's
 * own switch (M6). Its « accepte les uploads » switch below it, the same way
 * (L23, round 11 OPEN 2 = B).
 *
 * @param props.block The tracker, its summary, and whether its switch moved in this visit.
 * @returns The block.
 */
function CrossSeedSwitchBlock({ block: posed }: { block: { type: "crossSeedSwitch" } & PanelBlockMap["crossSeedSwitch"] }): ReactElement {
  const { t } = useTranslation();
  // THE SUMMARY READ ITSELF, so the switch moves in the render the write's answer lands in.
  const summary = useTrackers().data?.find((one) => one.name === posed.tracker)?.crossSeed;
  const block = summary ? { ...posed, summary } : posed;
  const say = (key: string, values: Record<string, string> = {}) => t(`screens.crossSeed.switch.${key}`, values);
  const on = block.summary.enabled;
  const accepts = block.summary.acceptsUploads;
  // THE DETAIL SAYS WHAT IS TRUE: the engine off, the tracker on searches nothing
  // (M6, as the roster's line says it); the running ones cut, they no longer continue.
  const detail = on
    ? (block.summary.engineEnabled ? "onDetail" : "onEngineOffDetail")
    : (block.switched === "offStopped" ? "offStoppedDetail" : "offDetail");
  return (
    <section data-part="tracker/cross-seed" data-tracker={block.tracker}>
      {block.summary.engineEnabled ? null : (
        <p className={factDetail()} data-part="tracker/cross-seed-engine-off"><b>{say("engineOff")}</b></p>
      )}
      <ol className={factList()}>
        <li className={factRow({ withControl: true })}>
          <div className={factRowBody()}>
            <span className={factName()} data-part="tracker/cross-seed-state" data-on={String(on)}>
              {say(on ? "on" : "off")}
            </span>
            <span className={factDetail()} data-part="tracker/cross-seed-detail">{say(detail)}</span>
          </div>
          <Switch checked={on} label={say("label", { tracker: block.tracker })}
            data-part="tracker/cross-seed-switch" data-cross-seed-switch={block.tracker} />
        </li>
        {/* « ACCEPTE LES UPLOADS », DISTINCT FROM THE CROSS-SEED (round 11 OPEN 2 = B): the
            same setting Réglages draws, one write, two doors. Off, it cuts nothing published. */}
        <li className={factRow({ withControl: true })} data-part="tracker/uploads" data-on={String(accepts)}>
          <div className={factRowBody()}>
            <span className={factName()} data-part="tracker/uploads-state">{say(accepts ? "uploadsOn" : "uploadsOff")}</span>
            <span className={factDetail()} data-part="tracker/uploads-detail">
              {say(accepts ? "uploadsOnDetail" : "uploadsOffDetail")}
            </span>
          </div>
          <Switch checked={accepts} label={say("uploadsLabel", { tracker: block.tracker })}
            data-part="tracker/uploads-switch" data-uploads-switch={block.tracker} />
        </li>
      </ol>
      {block.switched !== null ? (
        <p className={factDetail()} data-part="tracker/cross-seed-next-pass">{say("nextPass")}</p>
      ) : null}
    </section>
  );
}

// Declared to the registry as this module evaluates: the torrent's panel and the tracker's import it.
registerBlock("crossSeed", (block) => <CrossSeedBlock block={block} />);
registerBlock("crossSeedSwitch", (block) => <CrossSeedSwitchBlock block={block} />);
