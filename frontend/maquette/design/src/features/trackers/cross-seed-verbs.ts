// THE CROSS-SEED'S VERBS, declared to the tap registry: a tracker's switch, and
// what a torrent's panel does to one of its pairs.
//
// NOTHING IS DESTROYED WITHOUT CONSENT (NE-DOIT-PAS-6): a switch turned OFF, a
// pair cut, a title no longer shared each open a confirmation that NAMES what
// ends — the tracker, and every running obligation — and only the confirmation
// writes. Turning a switch back ON, and undoing an exclusion, destroy nothing
// and ask nothing.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { dialog, panel } from "../../lib/shell-doors";
import { read, send, sharedQueryClient } from "../../lib/query-client";
import type { DialogBlock } from "../../ui/dialog/contract";
import type { Schemas } from "../../lib/contract-schemas";
import { downloadsKey, obligationsKey, trackersKey } from "./queries";

// The file the trackers' settings are kept in, and the settings catalogue's key.
const TRACKER_FILE = "tracker";
const CATALOGUE_KEY = ["/api/config/schema"];

/** Every read a cross-seed write moves: the summary, the entries, their obligations, the settings. */
const MOVED = [trackersKey, downloadsKey, obligationsKey, CATALOGUE_KEY];

/** The trackers whose switch was changed in this visit: « pris en compte à la prochaine passe ». */
export const switchedThisVisit = new Set<string>();

/**
 * The words of the cross-seed's confirmations, in the interface's language.
 *
 * @param key The sentence.
 * @param values What it names.
 * @returns The sentence.
 */
function say(key: string, values: Record<string, string> = {}): string {
  return i18next.t(`verbs.crossSeed.${key}`, values);
}

/**
 * The setting one tracker's cross-seed switch is kept under — the one Réglages draws.
 *
 * @param tracker The tracker's configured name.
 * @returns The setting's identity, `<file>:<key>`.
 */
export function crossSeedSetting(tracker: string): string {
  return `${TRACKER_FILE}:tracker.providers.${tracker}.cross_seed`;
}

/** Asks every read a cross-seed write moves again, so every reader agrees in one render. */
async function refresh(): Promise<void> {
  await Promise.all(MOVED.map((queryKey) => sharedQueryClient?.invalidateQueries({ queryKey })));
  panel.redraw();
}

/**
 * The client's entries and their obligations, as held — or asked for when not.
 *
 * @returns Both reads' answers.
 */
async function held(): Promise<[Schemas["Downloads"], Schemas["Obligations"]]> {
  const client = sharedQueryClient;
  const ask = <Result>(key: string[]) =>
    client?.ensureQueryData({ queryKey: key, queryFn: async () => read<Result>(key[0]) }) as Promise<Result>;
  return Promise.all([ask<Schemas["Downloads"]>(downloadsKey), ask<Schemas["Obligations"]>(obligationsKey)]);
}

/**
 * The running obligations a set of cross-seed entries owes — what a stop would end.
 *
 * @param entries The cross-seeds' own entry hashes.
 * @param obligations Every obligation.
 * @returns Those neither met, broken nor released.
 */
export function runningOn(entries: readonly string[], obligations: Schemas["Obligation"][]): Schemas["Obligation"][] {
  return obligations.filter((obligation) => entries.includes(obligation.infoHash)
    && obligation.satisfiedAt === null && obligation.breachedAt === null && obligation.releasedAt === null);
}

/**
 * The paragraphs naming each running obligation a gesture would end « libérée » (M4).
 *
 * @param obligations The running obligations.
 * @returns One paragraph each.
 */
export function obligationParagraphs(obligations: Schemas["Obligation"][]): DialogBlock[] {
  return obligations.map((obligation) => ({
    type: "paragraph",
    runs: [
      { text: say("obligation", { tracker: obligation.sourceTracker, title: obligation.title ?? "" }), strong: true },
      { text: say("obligationBody") },
    ],
  }));
}

/**
 * Writes one tracker's cross-seed switch — the SAME write Réglages makes — and,
 * when asked, stops the pairs running there in that SAME call.
 *
 * @param tracker The tracker's configured name.
 * @param on Whether the switch is turned on.
 * @param stopRunning Whether the running pairs stop too.
 */
async function writeSwitch(tracker: string, on: boolean, stopRunning: boolean): Promise<void> {
  const query = stopRunning ? "?stopRunningCrossSeeds=true" : "";
  await send("PUT", `/api/config/files/${TRACKER_FILE}${query}`, { [crossSeedSetting(tracker)]: on });
  switchedThisVisit.add(tracker);
  await refresh();
}

/**
 * Opens the confirmation for turning one tracker's cross-seed off.
 *
 * @param tracker The tracker's configured name.
 */
export function openSwitchConfirm(tracker: string): void {
  void held().then(([downloads, obligations]) => {
    const running = downloads.downloads.flatMap((entry) => entry.crossSeed?.pairs ?? [])
      .filter((pair) => pair.tracker === tracker && pair.state === "active");
    const ending = runningOn(running.flatMap((pair) => pair.entryHash === null ? [] : [pair.entryHash]), obligations.items);
    // UNCHECKED BY DEFAULT (round 9 Q5): the switch cuts NEW cross-seeds only.
    let stopRunning = false;
    const body: DialogBlock[] = [
      { type: "paragraph", runs: [{ text: say("switchBody", { tracker }) }] },
      {
        type: "paragraph",
        runs: [{
          text: running.length === 0
            ? say("switchNoneRunning", { tracker })
            : i18next.t("verbs.crossSeed.switchRunning", { count: running.length, tracker }),
        }],
      },
      {
        type: "check",
        label: say("stopRunning", { tracker }),
        checked: stopRunning,
        toggle: (checked) => {
          stopRunning = checked;
        },
      },
      ...(ending.length === 0 ? [] : [{ type: "paragraph" as const, runs: [{ text: say("switchEnding") }] }]),
      ...obligationParagraphs(ending),
    ];
    dialog?.open({
      heading: say("switchHeading", { tracker }),
      body,
      actions: [
        { text: say("switchConfirm"), tone: "danger", run: () => void writeSwitch(tracker, false, stopRunning) },
        { text: say("cancel"), tone: "ghost", dismiss: true },
      ],
    });
  });
}

/* THE SWITCH ON A TRACKER'S PANEL: off asks first, on writes at once. */
registerVerb("cross-seed-switch", (tracker) => {
  const summary = sharedQueryClient?.getQueryData<Schemas["Tracker"][]>(trackersKey)?.find((one) => one.name === tracker);
  if (summary === undefined) return;
  if (summary.crossSeed.enabled) openSwitchConfirm(tracker);
  else void writeSwitch(tracker, true, false);
});
