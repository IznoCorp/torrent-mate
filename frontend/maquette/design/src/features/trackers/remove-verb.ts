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
import { read, send, sharedQueryClient } from "../../lib/query-client";
import type { DialogBlock } from "../../ui/dialog/contract";
import type { Schemas } from "../../lib/contract-schemas";

/** The two reads a removal moves: the client's entries, and their obligations. */
const REFRESHED = [["/api/acquisition/downloads"], ["/api/acquisition/obligations"]];

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
 * Removes one entry, its files with it, then says it is gone.
 *
 * @param entry The entry.
 */
async function removeEntry(entry: Schemas["Download"]): Promise<void> {
  await send("DELETE", `/api/acquisition/downloads/${encodeURIComponent(entry.infoHash)}`, { deleteFiles: true });
  // BOTH READS ASKED AGAIN TOGETHER, so the row leaves with the answer.
  await Promise.all(REFRESHED.map((queryKey) => sharedQueryClient?.invalidateQueries({ queryKey })));
  toast?.show({ message: say("done", { title: entry.title }) });
}

/**
 * Opens the confirmation for one entry.
 *
 * THE ENTRY IS READ WHEN THE CONFIRMATION OPENS — from the cache the tab drew,
 * or asked for when it holds nothing — so the confirmation names what the
 * client holds now.
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
    held<Schemas["Downloads"]>("/api/acquisition/downloads"),
    held<Schemas["Obligations"]>("/api/acquisition/obligations"),
  ]).then(([downloads, obligations]) => {
    const entry = downloads.downloads.find((one) => one.infoHash === infoHash && one.tracker === tracker);
    if (entry !== undefined) openConfirm(entry, obligations.items);
  });
}

/**
 * Opens the confirmation, the entry and its obligations in hand.
 *
 * @param entry The entry.
 * @param obligations Every obligation.
 */
function openConfirm(entry: Schemas["Download"], obligations: Schemas["Obligation"][]): void {
  const tracker = entry.tracker;
  // A RUNNING OBLIGATION IS NAMED: removing now closes it before it is met.
  const running = obligations.some(
    (obligation) => obligation.infoHash === entry.infoHash && obligation.sourceTracker === tracker
      && obligation.satisfiedAt === null && obligation.releasedAt === null,
  );
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
  if (running) body.push({ type: "warning", strong: say("obligation", { tracker }), text: say("obligationBody") });
  dialog?.open({
    heading: say("heading"),
    body,
    actions: [
      { text: say("confirm"), tone: "danger", run: () => void removeEntry(entry) },
      { text: say("cancel"), tone: "ghost", dismiss: true },
    ],
  });
}

/* THE ROW SAYS WHICH ENTRY: its hash, and the tracker it runs on. */
registerVerb("torrent-remove", (value) => {
  const [infoHash, tracker] = value.split(":");
  if (infoHash && tracker) openRemoveConfirm(infoHash, tracker);
});
