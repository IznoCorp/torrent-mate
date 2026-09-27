// « Ce n'est pas un média » — a folder the operator says is not a medium
// (ruling 5).
//
// THE DESTINATIONS ARE THE CONFIGURATION'S, never this module's: the choice
// offers what the layer answers for the sort's non-media staging directories,
// and the folder is filed where the sort files that category. Its card leaves
// the acquisitions, and he does not see it again.
//
// THE UNDO IS THE INVERSE OPERATION. The reclassification is sent at once and
// its « Annuler » asks the layer to put the folder back — every resolve has its
// inverse (`backend-demands-architecture.md` § 9, demand C) — rather than
// holding the send, which is the shape an act with no inverse needs.
import i18next from "i18next";
import { CancelledError } from "@tanstack/react-query";
import { read, send, sharedQueryClient } from "../../lib/query-client";
import { registerVerb } from "../../lib/verbs";
import { bridge, icons, panel, toast } from "../../lib/shell-doors";
import { registerProducer, type PanelDescriptor } from "../../ui/panel/contract";
import type { Schemas } from "../../lib/contract-schemas";

type Destination = Schemas["StagingDestination"];

/** Where the destinations are read, and cached. */
const DESTINATION_READ = ["/api/staging/destinations"];

/** The two reads a reclassified folder leaves: the queue, and the staging area. */
const LEFT = [["/api/acquisition/to-handle"], ["/api/staging/media"]];

// Between the folder and the destination in a choice's target: a folder name
// is the operator's disk, a destination a configured directory name.
const SEPARATOR = "|";

/**
 * Asks both reads a reclassification moves again.
 */
async function readAgain(): Promise<void> {
  for (const queryKey of LEFT) await sharedQueryClient?.invalidateQueries({ queryKey });
}

/**
 * Builds the choice: one action per destination the configuration declares.
 *
 * @param folder The folder.
 * @returns The descriptor, or null while the destinations are not read yet.
 */
function choicePanel(folder?: string): PanelDescriptor | null {
  const offered = sharedQueryClient?.getQueryData<Destination[]>(DESTINATION_READ);
  if (!folder || offered === undefined) return null;
  return {
    title: i18next.t("panels.notMedia.title"),
    meta: i18next.t("panels.notMedia.meta", { folder }),
    blocs: [
      {
        type: "actions",
        actions: offered.map((destination) => ({
          text: destination.name,
          icone: icons.folder,
          target: { reclassify: `${folder}${SEPARATOR}${destination.name}` },
        })),
      },
    ],
  };
}

/**
 * Files one folder under a destination, then offers to put it back.
 *
 * @param folder The folder.
 * @param destination The destination's name.
 */
async function reclassify(folder: string, destination: string): Promise<void> {
  const path = `/api/staging/media/${encodeURIComponent(folder)}/reclassify`;
  const answer = (await send("POST", path, { destination })) as { destination?: string } | undefined;
  await readAgain();
  toast?.show({
    message: i18next.t("verbs.acquisition.reclassified", { title: folder, destination: answer?.destination ?? destination }),
    undo: () => void send("DELETE", path).then(readAgain),
  });
}

registerProducer("not-media", { produce: choicePanel });

/**
 * Reads the destinations, then offers them for one folder.
 *
 * A read CANCELLED — the cache cleared under it — opens nothing and says
 * nothing; any other failure is left to surface.
 *
 * @param folder The folder.
 */
export function openNotMediaChoice(folder: string): void {
  void sharedQueryClient
    ?.fetchQuery({ queryKey: DESTINATION_READ, queryFn: () => read<Destination[]>(DESTINATION_READ[0]) })
    .then(() => panel.produce("not-media", folder), (failure: unknown) => {
      if (!(failure instanceof CancelledError)) throw failure;
    });
}

// The exit on the candidates screen.
registerVerb("not-media", (folder) => openNotMediaChoice(folder));

// A destination chosen: ONE SETTLEMENT for the two entries the journey stacked
// — the choice and the candidates screen — so the operator is back on
// « À traiter »; the choice is closed without unwinding (`close(true)`), as the
// identification's own settlement does.
registerVerb("reclassify", (target) => {
  const at = target.lastIndexOf(SEPARATOR);
  const entries = (panel.isOpen() ? 1 : 0) + 1;
  panel.close(true);
  bridge.rewind(entries);
  void reclassify(target.slice(0, at), target.slice(at + SEPARATOR.length));
});
