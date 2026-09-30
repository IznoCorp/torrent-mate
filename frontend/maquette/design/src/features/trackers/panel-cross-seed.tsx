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
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { registerBlock, type PanelBlockMap } from "../../ui/panel/contract";
import { Chip } from "../../ui/chip";
import { Switch } from "../../ui/switch";
import type { Schemas } from "../../lib/contract-schemas";
import { actionButton, sheetActions, factDetail, factList, factName, factRow, factRowBody } from "../../ui/variants";
import { dayOf } from "./format";
import {
  CROSS_SEED_TONE, familyWord, isFailure, reasonSentence, stateWord, type CrossSeedPair,
} from "./cross-seed-state";

// The block this file adds to the panel's map, declared beside what draws it.
declare module "../../ui/panel/contract" {
  interface PanelBlockMap {
    crossSeed: {
      /** The origin entry: its hash, its release name and the tracker it runs on. */
      origin: { infoHash: string; name: string; tracker: string };
      pairs: CrossSeedPair[];
      titleExcluded: boolean;
    };
    crossSeedSwitch: {
      /** The tracker's configured name. */
      tracker: string;
      /** Its cross-seed, as the summary read answers it. */
      summary: Schemas["TrackerCrossSeed"];
      /** Whether its switch was changed in this visit. */
      switched: boolean;
    };
  }
}

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
  if (pair.state === "active") return say("injected", { date: dayOf(pair.at) });
  return say("tried", { date: dayOf(pair.at) });
}

/**
 * What a pair offers: to cut it while it runs (round 9 Q5, Q8), and to lift its
 * exclusion once excluded (round 9 Q11) — nothing the engine would refuse (§ 17
 * point 1). A title excluded whole is lifted whole, never pair by pair.
 *
 * @param props.pair The pair.
 * @param props.origin The origin entry.
 * @param props.titleExcluded Whether the whole title is excluded.
 * @returns The pair's buttons, or nothing.
 */
function PairActs({ pair, origin, titleExcluded }: {
  pair: CrossSeedPair; origin: PanelBlockMap["crossSeed"]["origin"]; titleExcluded: boolean;
}): ReactElement | null {
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
 * @param props.pair The pair.
 * @param props.origin The origin entry.
 * @returns The row.
 */
function PairRow({ pair, origin, titleExcluded }: {
  pair: CrossSeedPair; origin: PanelBlockMap["crossSeed"]["origin"]; titleExcluded: boolean;
}): ReactElement {
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
            {pair.candidate === null ? null : (
              <>{say("candidate", { name: pair.candidate, tracker: pair.tracker })}<br /></>
            )}
            {say("source", { name: origin.name, tracker: origin.tracker })}
          </span>
        ) : null}
        {pair.state === "notSearched" && pair.waitReason !== null ? (
          <span className={factDetail()} data-part="torrents/cross-seed-wait">
            {say("wait", { reason: t(`screens.crossSeed.waits.${pair.waitReason}`) })}
          </span>
        ) : null}
        {pair.excluded ? (
          <span className={factDetail()} data-part="torrents/cross-seed-excluded">{say("excluded")}</span>
        ) : null}
        <PairActs pair={pair} origin={origin} titleExcluded={titleExcluded} />
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
function CrossSeedBlock({ block }: { block: { type: "crossSeed" } & PanelBlockMap["crossSeed"] }): ReactElement {
  const { t } = useTranslation();
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
            <PairRow key={pair.tracker} pair={pair} origin={block.origin} titleExcluded={block.titleExcluded} />
          ))}
        </ol>
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
 * own switch (M6).
 *
 * @param props.block The tracker, its summary, and whether its switch moved in this visit.
 * @returns The block.
 */
function CrossSeedSwitchBlock({ block }: { block: { type: "crossSeedSwitch" } & PanelBlockMap["crossSeedSwitch"] }): ReactElement {
  const { t } = useTranslation();
  const say = (key: string, values: Record<string, string> = {}) => t(`screens.crossSeed.switch.${key}`, values);
  const on = block.summary.enabled;
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
            <span className={factDetail()}>{say(on ? "onDetail" : "offDetail")}</span>
          </div>
          <Switch checked={on} label={say("label", { tracker: block.tracker })}
            data-part="tracker/cross-seed-switch" data-cross-seed-switch={block.tracker} />
        </li>
      </ol>
      {block.switched ? (
        <p className={factDetail()} data-part="tracker/cross-seed-next-pass">{say("nextPass")}</p>
      ) : null}
    </section>
  );
}

// Declared to the registry as this module evaluates: the torrent's panel and the tracker's import it.
registerBlock("crossSeed", (block) => <CrossSeedBlock block={block} />);
registerBlock("crossSeedSwitch", (block) => <CrossSeedSwitchBlock block={block} />);
