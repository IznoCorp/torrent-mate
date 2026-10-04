// « Retirer de qBittorrent » — one entry leaves the download client (ruling 18).
//
// THE OPERATOR'S GESTURE IS ON A TORRENT'S ENTRY, never on an obligation: the
// entry leaves the client, its files deleted by default, and a running
// obligation it owed is closed by the server as released. Nothing is destroyed
// without consent (NE-DOIT-PAS-6): the tap opens a confirmation that NAMES the
// torrent and its tracker, and only the confirmation calls the operation.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { dialog, toast } from "../../lib/shell-doors";
import { HELD, quietWhenCancelled, read, send, sharedQueryClient } from "../../lib/query-client";
import type { DialogBlock } from "../../ui/dialog/contract";
import type { Schemas } from "../../lib/contract-schemas";
import { downloadsKey, obligationsKey } from "./queries";

/** The two reads a removal moves: the client's entries, and their obligations. */
const REFRESHED = [downloadsKey, obligationsKey];

/**
 * The words of the confirmation, in the interface's language.
 *
 * @param key The sentence.
 * @param values What it names.
 * @returns The sentence.
 */
function say(key: string, values: Record<string, string> = {}): string {
  return i18next.t(`verbs.trackers.remove.${key}`, values);
}

/**
 * Removes one entry, its files with it or not, then says it is gone.
 *
 * @param entry The entry.
 * @param deleteFiles Whether its files leave the disk with it.
 */
async function removeEntry(entry: Schemas["Download"], deleteFiles: boolean): Promise<void> {
  const answered = await send("DELETE", `/api/v1/acquisition/downloads/${encodeURIComponent(entry.infoHash)}`, { deleteFiles });
  // HELD IS NOT DONE: the outbox keeps the removal and says so; the entry has
  // not left qBittorrent, and asking the reads again offline would replace the
  // tab with a failure. Nothing more is said until it departs.
  if (answered === HELD) return;
  // BOTH READS ASKED AGAIN TOGETHER, so the row leaves with the answer.
  await Promise.all(REFRESHED.map((queryKey) => sharedQueryClient?.invalidateQueries({ queryKey })));
  toast?.show({ message: say("done", { title: entry.title }) });
}

/**
 * Opens the confirmation for one entry.
 *
 * THE ENTRY IS READ WHEN THE CONFIRMATION OPENS — from the cache the tab drew,
 * or asked for when it holds nothing — so the confirmation names what the
 * client holds now. A read the cache's reset cancels opens nothing.
 *
 * @param infoHash The entry's hash.
 * @param tracker The tracker the entry runs on.
 */
export function openRemoveConfirm(infoHash: string, tracker: string): void {
  const client = sharedQueryClient;
  if (client === undefined) return;
  const held = <Result>(address: string) =>
    client.ensureQueryData({ queryKey: [address], queryFn: async () => read<Result>(address) });
  void Promise.all([
    held<Schemas["Downloads"]>("/api/v1/acquisition/downloads"),
    held<Schemas["Obligations"]>("/api/v1/acquisition/obligations"),
  ]).then(([downloads, obligations]) => {
    const entry = downloads.downloads.find((one) => one.infoHash === infoHash && one.tracker === tracker);
    if (entry !== undefined) openConfirm(entry, downloads.downloads, obligations.items);
  }, quietWhenCancelled);
}

/**
 * Whether an entry owes a running obligation on its own tracker.
 *
 * @param entry The entry.
 * @param obligations Every obligation.
 * @returns True while one is neither met, broken nor released — a BROKEN
 *     obligation is not running, and is never announced as one.
 */
function hasRunningObligation(entry: Schemas["Download"], obligations: Schemas["Obligation"][]): boolean {
  return obligations.some(
    (obligation) => obligation.infoHash === entry.infoHash && obligation.sourceTracker === entry.tracker
      && obligation.satisfiedAt === null && obligation.breachedAt === null && obligation.releasedAt === null,
  );
}

/**
 * Opens the confirmation, the entry, its siblings and its obligations in hand.
 *
 * @param entry The entry.
 * @param downloads Every entry of the client: those holding its files leave with it.
 * @param obligations Every obligation.
 */
function openConfirm(
  entry: Schemas["Download"], downloads: Schemas["Download"][], obligations: Schemas["Obligation"][],
): void {
  const tracker = entry.tracker;
  // THE SAME FILES UNDER ANOTHER ENTRY leave with this one: the removal ends
  // every share of them, and the confirmation says which.
  const sameFiles = downloads.filter((one) => one.name === entry.name && one !== entry);
  const body: DialogBlock[] = [
    {
      type: "paragraph",
      runs: [
        { text: entry.title, strong: true },
        { text: say("bodyOn") },
        { text: tracker, strong: true },
        { text: say("bodyFiles") },
      ],
    },
  ];
  if (sameFiles.length > 0) {
    const trackers = [...new Set(sameFiles.map((one) => one.tracker))].join(", ");
    body.push({ type: "paragraph", runs: [{ text: say("shared", { trackers }) }] });
  }
  // A RUNNING OBLIGATION IS NAMED, on every tracker the removal ends a share on:
  // removing now closes it before it is met. A PARAGRAPH, not the warning box:
  // the box's bold line fails contrast in the light theme, a debt this
  // confirmation must not add to.
  for (const bound of [entry, ...sameFiles].filter((one) => hasRunningObligation(one, obligations))) {
    body.push({
      type: "paragraph",
      runs: [{ text: say("obligation", { tracker: bound.tracker }), strong: true }, { text: say("obligationBody") }],
    });
  }
  // THE FILES GO BY DEFAULT, and the box is where the operator keeps them.
  let deleteFiles = true;
  body.push({
    type: "check",
    label: say("deleteFiles"),
    checked: deleteFiles,
    toggle: (checked) => {
      deleteFiles = checked;
    },
  });
  dialog?.open({
    heading: say("heading"),
    body,
    actions: [
      { text: say("confirm"), tone: "danger", run: () => void removeEntry(entry, deleteFiles) },
      { text: say("cancel"), tone: "ghost", dismiss: true },
    ],
  });
}

/* THE ROW SAYS WHICH ENTRY: its hash, and the tracker it runs on. */
registerVerb("torrent-remove", (value) => {
  const [infoHash, tracker] = value.split(":");
  if (infoHash && tracker) openRemoveConfirm(infoHash, tracker);
});
