// A tracker's panel — what a tap on a roster row raises.
//
// THE PANEL'S GENERIC BLOCKS ONLY: the tracker's facts, its policy, its broken
// obligations, its torrents. The policy rows are the SAME settings Réglages
// draws, and a tap raises that setting's own panel — one write, whichever door.
// The activation switch is NOT here: it stays on the row, where a finger reaches
// it without opening anything.
//
// NO ADDRESS: the roster's landing names the tracker, and the page opens this
// panel for it.
import { accountQuery, heldRights } from "../../lib/account";
import i18next from "i18next";
import type { Schemas } from "../../lib/contract-schemas";
import { icons, panel } from "../../lib/shell-doors";
import { read, sharedQueryClient } from "../../lib/query-client";
import { registerProducer, type Action, type FactLine, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import { written } from "../../lib/byte-size";
import { dayOf } from "./format";
import { momentOf } from "../../lib/clock";
import { trackersKey, type Setting, type Tracker } from "./queries";
import { failureSentence } from "./trackers-tab";
import { switchedThisVisit } from "./cross-seed-verbs";
import "./panel-cross-seed";

// THE POLICY IS THE TRACKER'S ECONOMY BLOCK, in the tracker's configuration
// file: the floor, the seed time and the alert threshold, in that order.
const POLICY_FILE = "tracker";
const POLICY_FIELDS = [
  { field: "min_ratio", label: "screens.trackers.minRatio" },
  { field: "min_seed_time", label: "screens.trackers.minSeedTime" },
  { field: "alert_threshold", label: "screens.trackers.alertThreshold" },
] as const;

// The address of the settings catalogue — the one Réglages reads.
const CATALOGUE_KEY = ["/api/v1/config/schema"];

// A billion bytes: the « Go » the interface writes volumes in.
const GIGABYTE = 1_000_000_000;

/** Whether a read of the catalogue is being waited on for this panel. */
let watching = false;

/**
 * Asks for the catalogue, and has the open panel drawn again once it answers —
 * or once it fails, which the panel then says.
 */
function watchCatalogue(): void {
  if (watching) return;
  watching = true;
  void sharedQueryClient
    ?.fetchQuery({ queryKey: CATALOGUE_KEY, queryFn: async () => read<Schemas["SettingsTopic"][]>(CATALOGUE_KEY[0]) })
    .catch(() => undefined)
    .finally(() => {
      watching = false;
      panel.redraw();
    });
}

/**
 * What the policy's note says: its guidance, that none is set, that its read is
 * under way, or that it failed — a wait and a failure are never « no policy ».
 *
 * @param catalogue The catalogue, when it is held.
 * @param rows How many policy settings the configuration holds.
 * @returns The note.
 */
function policyNote(catalogue: unknown, rows: number): string {
  if (catalogue !== undefined) return rows === 0 ? say("policyUnset") : say("floorGuidance");
  if (sharedQueryClient?.getQueryState(CATALOGUE_KEY)?.status === "error") {
    return i18next.t("surfaces.error.lead", { subject: say("policyErrorSubject") });
  }
  watchCatalogue();
  return say("policyLoading");
}

/**
 * A sentence of the panel, in the interface's language.
 *
 * @param key The sentence's key under the Trackers page's words.
 * @param values What it names.
 * @returns The sentence.
 */
function say(key: string, values: Record<string, unknown> = {}): string {
  return i18next.t(`screens.trackers.${key}`, values);
}

/**
 * What the tracker's state says on its panel: on, off, or off and why.
 *
 * @param tracker The tracker, as its own answer carries it.
 * @returns The state in words.
 */
function stateOf(tracker: Tracker): string {
  if (tracker.disabled === null) return say("panel.active");
  const failure = failureSentence(tracker);
  return failure === null
    ? say("disabledByOperator")
    : say("panel.stateWithReason", { state: say("disabledByOperator"), reason: failure });
}

/**
 * The tracker's policy, as actions raising each setting's own panel.
 *
 * @param tracker The tracker's name.
 * @param settings The settings catalogue, flattened.
 * @returns One action per policy setting the configuration holds.
 */
function policyActions(tracker: string, settings: Setting[]): Action[] {
  return POLICY_FIELDS.flatMap(({ field, label }) => {
    const key = `tracker.providers.${tracker}.economy.${field}`;
    const setting = settings.find((candidate) => candidate.file === POLICY_FILE && candidate.key === key);
    return setting === undefined
      ? []
      : [{
          text: say("panel.policyRow", { label: i18next.t(label), value: String(setting.displayedValue ?? "") }),
          target: { setting: `${POLICY_FILE}:${key}` },
        }];
  });
}

/**
 * Builds a tracker's descriptor.
 *
 * @param name The tracker's configured name.
 * @param cache What the query cache holds.
 * @returns The descriptor, or null while the roster has not landed or does not hold it.
 */
function trackerPanel(name: string, cache: PanelCache): PanelDescriptor | null {
  const tracker = cache.held<Tracker[]>(trackersKey)?.find((one) => one.name === name);
  if (tracker === undefined) return null;
  const catalogue = cache.held<Schemas["SettingsTopic"][]>(CATALOGUE_KEY);
  const settings = (catalogue ?? []).flatMap((topic) => topic.settings);
  const facts: FactLine[] = [
    { c: say("panel.state"), v: stateOf(tracker) },
    // WHETHER IT ANSWERS, and since when it does not (maquette-blocked § 1.3):
    // « Voir le tracker » on a block waiting on it lands here, saying the cause.
    {
      c: say("panel.reachability"),
      v: tracker.reachable || tracker.unreachableSince === null
        ? say("panel.reachable")
        : say("panel.unreachableSince", { time: momentOf(tracker.unreachableSince) }),
    },
    { c: say("panel.ratio"), v: tracker.ratio === null ? say("ratioUnknown") : written(tracker.ratio, 2) },
    { c: say("panel.trend"), v: say(`trends.${tracker.trend}`) },
    {
      c: say("panel.volumes"),
      v: say("volumes", {
        downloaded: written(tracker.downloadedBytes / GIGABYTE, 1),
        uploaded: written(tracker.uploadedBytes / GIGABYTE, 1),
      }),
    },
  ];
  const policy = policyActions(tracker.name, settings);
  const broken = tracker.brokenObligations;
  return {
    title: tracker.name,
    meta: tracker.ratio === null ? say("ratioUnknown") : say("ratio", { ratio: written(tracker.ratio, 2) }),
    blocs: [
      { type: "faits", lignes: facts },
      // ITS CROSS-SEED SWITCH, a row of its own beside the policy (S2) — never the activation's.
      { type: "crossSeedSwitch", tracker: tracker.name, summary: tracker.crossSeed, switched: switchedThisVisit.get(tracker.name) ?? null },
      { type: "note", text: policyNote(catalogue, policy.length) },
      policy.length === 0 ? null : { type: "actions", actions: policy },
      broken.length === 0 ? null : { type: "note", text: say("panel.brokenLead") },
      broken.length === 0 ? null : {
        type: "faits",
        lignes: broken.map((row) => ({
          c: row.title,
          v: row.seen ? say("panel.brokenSeen") : say("panel.brokenUnseen", { date: dayOf(row.brokenAt) }),
        })),
      },
      // « VU » ON EACH ONE NOT SEEN: seen is not gone, the row stays, marked seen.
      // « VU » IS A WRITE (`trackers.control`), absent without it.
      broken.some((row) => !row.seen) && heldRights().holds("trackers.control") ? {
        type: "actions",
        secondary: true,
        actions: broken.filter((row) => !row.seen).map((row) => ({
          text: say("panel.seenAction", { title: row.title }),
          icone: icons.eye,
          target: { "obligation-seen": `${tracker.name}:${row.infoHash}` },
        })),
      } : null,
      {
        type: "actions",
        actions: [{ text: say("seeTorrents"), icone: icons.right, target: { "trackers-see": tracker.name } }],
      },
    ],
  };
}

registerProducer("tracker", {
  produce: trackerPanel,
  needs: () => [
    accountQuery,
    { queryKey: trackersKey, queryFn: async () => read<Tracker[]>(trackersKey[0]) },
    { queryKey: CATALOGUE_KEY, queryFn: async () => read<Schemas["SettingsTopic"][]>(CATALOGUE_KEY[0]) },
  ],
});
