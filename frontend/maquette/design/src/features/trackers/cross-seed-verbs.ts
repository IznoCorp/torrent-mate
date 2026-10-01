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
import { dialog, panel, toast } from "../../lib/shell-doors";
import { quietWhenCancelled, read, send, sharedQueryClient } from "../../lib/query-client";
import type { DialogBlock } from "../../ui/dialog/contract";
import type { Schemas } from "../../lib/contract-schemas";
import { downloadsKey, obligationsKey, trackersKey } from "./queries";

// The file the trackers' settings are kept in, and the settings catalogue's key.
const TRACKER_FILE = "tracker";
const CATALOGUE_KEY = ["/api/config/schema"];

/** Every read a cross-seed write moves: the summary, the entries, their obligations, the settings. */
const MOVED = [trackersKey, downloadsKey, obligationsKey, CATALOGUE_KEY];

/** What a switch's write did: turned on, off, or off with the running ones cut. */
export type SwitchWrite = "on" | "off" | "offStopped";

/** The trackers whose switch was changed in this visit, and how: « pris en compte à la prochaine passe ». */
export const switchedThisVisit = new Map<string, SwitchWrite>();

// The status message each write earns, as the cut, the search and the exclusion each have one.
const SWITCH_DONE: Readonly<Record<SwitchWrite, string>> = {
  on: "switchOnDone",
  off: "switchOffDone",
  offStopped: "switchOffStoppedDone",
};

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
 * A read the cache's reset cancels rejects: each caller lets it pass in silence.
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
  const write: SwitchWrite = on ? "on" : stopRunning ? "offStopped" : "off";
  switchedThisVisit.set(tracker, write);
  await refresh();
  toast?.show({ message: say(SWITCH_DONE[write], { tracker }) });
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
  }, quietWhenCancelled);
}

/* THE SWITCH ON A TRACKER'S PANEL: off asks first, on writes at once. */
registerVerb("cross-seed-switch", (tracker) => {
  const summary = sharedQueryClient?.getQueryData<Schemas["Tracker"][]>(trackersKey)?.find((one) => one.name === tracker);
  if (summary === undefined) return;
  if (summary.crossSeed.enabled) openSwitchConfirm(tracker);
  else void writeSwitch(tracker, true, false);
});

/**
 * An origin entry and its pairs, as held.
 *
 * @param downloads The client's entries.
 * @param infoHash The origin's hash.
 * @returns The origin, or undefined when the client no longer holds it.
 */
function originOf(downloads: Schemas["Downloads"], infoHash: string): Schemas["Download"] | undefined {
  return downloads.downloads.find((entry) => entry.infoHash === infoHash && entry.crossSeed !== null);
}

/**
 * Opens the confirmation for cutting one pair: its entry leaves the client
 * WITHOUT its files, its obligation closes « libérée », and the pair is
 * excluded from the engine's next passes — all in one call (round 9 Q5, Q8, Q11).
 *
 * @param infoHash The origin's hash.
 * @param tracker The pair's tracker.
 */
export function openCutConfirm(infoHash: string, tracker: string): void {
  void held().then(([downloads, obligations]) => {
    const origin = originOf(downloads, infoHash);
    const pair = origin?.crossSeed?.pairs.find((one) => one.tracker === tracker);
    if (origin === undefined || pair === undefined) return;
    const ending = runningOn(pair.entryHash === null ? [] : [pair.entryHash], obligations.items);
    dialog?.open({
      heading: say("cutHeading", { tracker }),
      body: [
        { type: "paragraph", runs: [{ text: say("cutBody", { title: origin.title, tracker, origin: origin.tracker }) }] },
        { type: "paragraph", runs: [{ text: say("cutMemory", { tracker }) }] },
        ...obligationParagraphs(ending),
      ],
      actions: [
        {
          text: say("cutConfirm"),
          tone: "danger",
          run: () => void send("POST", `/api/torrents/${encodeURIComponent(infoHash)}/cross-seed/${encodeURIComponent(tracker)}/cut`)
            .then(refresh).then(() => toast?.show({ message: say("cutDone", { tracker }) })),
        },
        { text: say("cancel"), tone: "ghost", dismiss: true },
      ],
    });
  }, quietWhenCancelled);
}

/**
 * Opens the confirmation for « Ne plus partager ce titre »: every running pair
 * cut the way one is, the whole title excluded on every tracker, the origin
 * untouched (round 9 Q11, M4).
 *
 * @param infoHash The origin's hash.
 */
export function openTitleConfirm(infoHash: string): void {
  void held().then(([downloads, obligations]) => {
    const origin = originOf(downloads, infoHash);
    if (origin === undefined) return;
    const running = (origin.crossSeed?.pairs ?? []).filter((pair) => pair.state === "active");
    const ending = runningOn(running.flatMap((pair) => pair.entryHash === null ? [] : [pair.entryHash]), obligations.items);
    dialog?.open({
      heading: say("titleHeading", { title: origin.title }),
      body: [
        { type: "paragraph", runs: [{ text: say("titleBody") }] },
        ...(running.length === 0 ? [] : [{
          type: "paragraph" as const,
          runs: [{ text: say("titleRunning", { trackers: running.map((pair) => pair.tracker).join(", ") }) }],
        }]),
        ...obligationParagraphs(ending),
        { type: "paragraph", runs: [{ text: say("titleOrigin", { origin: origin.tracker }) }] },
      ],
      actions: [
        {
          text: say("titleConfirm"),
          tone: "danger",
          run: () => void send("PUT", `/api/torrents/${encodeURIComponent(infoHash)}/cross-seed/exclusions`, { tracker: null })
            .then(refresh).then(() => toast?.show({ message: say("titleDone", { title: origin.title }) })),
        },
        { text: say("cancel"), tone: "ghost", dismiss: true },
      ],
    });
  }, quietWhenCancelled);
}

/**
 * Lifts an exclusion — undoing is never destructive, so nothing is asked first.
 *
 * @param infoHash The origin's hash.
 * @param tracker The pair's tracker, or null for the whole title.
 * @param message What is said once it is lifted.
 */
function include(infoHash: string, tracker: string | null, message: string): void {
  void send("DELETE", `/api/torrents/${encodeURIComponent(infoHash)}/cross-seed/exclusions`, { tracker })
    .then(refresh).then(() => toast?.show({ message }));
}

/* A PAIR'S CUT, from the torrent's panel: `<origin hash>:<tracker>`. */
registerVerb("cross-seed-cut", (value) => {
  const [infoHash, tracker] = value.split(":");
  if (infoHash && tracker) openCutConfirm(infoHash, tracker);
});

/* THE TITLE, as a whole, from the origin's panel. */
registerVerb("cross-seed-exclude-title", (infoHash) => openTitleConfirm(infoHash));

/* THE UNDOS, at once. */
registerVerb("cross-seed-include", (value) => {
  const [infoHash, tracker] = value.split(":");
  if (infoHash && tracker) include(infoHash, tracker, say("includeDone", { tracker }));
});
registerVerb("cross-seed-include-title", (infoHash) => {
  const title = sharedQueryClient?.getQueryData<Schemas["Downloads"]>(downloadsKey)?.downloads
    .find((entry) => entry.infoHash === infoHash)?.title ?? "";
  include(infoHash, null, say("includeTitleDone", { title }));
});

/** The searches asked and not yet answered: a second tap asks nothing (DOIT-4). */
const asking = new Set<string>();

/**
 * Asks ONE search — a pair, or every pair of an origin the engine would act on
 * — and says it is queued, never « occupé ». The pair reads « en file » until
 * the search's outcome arrives on the stream (F59).
 *
 * @param infoHash The origin's hash.
 * @param tracker The pair's tracker, or null for every pair.
 */
function search(infoHash: string, tracker: string | null): void {
  const subject = `${infoHash}:${tracker ?? ""}`;
  if (asking.has(subject)) return;
  asking.add(subject);
  void send<{ queued: boolean; trackers: string[]; startsAt: number | null }>(
    "POST", `/api/torrents/${encodeURIComponent(infoHash)}/cross-seed/search`, { tracker },
  )
    .then((answer) => {
      const waiting = typeof answer === "object" && answer !== null && answer.startsAt !== null;
      toast?.show({ message: say(waiting ? "searchWaiting" : "searchQueued") });
    })
    // THE ONE REFUSAL (a duplicate) is said, never swallowed.
    .catch(() => toast?.show({ message: say("searchDuplicate") }))
    .then(refresh)
    .finally(() => asking.delete(subject));
}

/* « CHERCHER UN CROSS-SEED » on a pair, from the torrent's panel: `<origin hash>:<tracker>`. */
registerVerb("cross-seed-search", (value) => {
  const [infoHash, tracker] = value.split(":");
  if (infoHash && tracker) search(infoHash, tracker);
});

/* THE CARD'S LEFT DRAWER: every pair of the origin the engine would act on, in its one search. */
registerVerb("cross-seed-search-all", (infoHash) => search(infoHash, null));
