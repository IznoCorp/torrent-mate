// « Supprimer » — a folder set aside, deleted from the disk (ruling 16).
//
// A REAL DELETION, NOT THE QUARANTINE « Abandonner » MAKES: the staging folder
// is removed and the deletion journaled. And nothing is destroyed without
// consent (NE-DOIT-PAS-6): the tap opens a confirmation of the Médiathèque's
// care that NAMES the folder — it has no provider identity — and says whether
// this copy is the only one; only the confirmation calls the operation.
//
// THE CASE IS SAID, NEVER GUESSED: until the confirmation reads it from the
// download client, the folder is treated as the only copy.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { dialog, toast } from "../../lib/shell-doors";
import { send, sharedQueryClient } from "../../lib/query-client";

/** The two reads a deleted folder leaves: the queue, and the staging area. */
const LEFT = [["/api/acquisition/to-handle"], ["/api/staging/media"]];

/**
 * Deletes one folder, then says it is gone.
 *
 * @param title The folder.
 */
async function deleteFolder(title: string): Promise<void> {
  await send("DELETE", `/api/staging/media/${encodeURIComponent(title)}`);
  for (const queryKey of LEFT) await sharedQueryClient?.invalidateQueries({ queryKey });
  toast?.show({ message: i18next.t("verbs.acquisition.deleteStaged.done", { title }) });
}

/**
 * Opens the confirmation that names the folder and its case; nothing is sent before it is confirmed.
 *
 * @param title The folder.
 */
export function openDeleteConfirm(title: string): void {
  const say = (key: string) => i18next.t(`verbs.acquisition.deleteStaged.${key}`, { title });
  dialog?.open({
    heading: say("heading"),
    body: [
      {
        type: "paragraph",
        runs: [{ text: say("bodyBefore") }, { text: title, strong: true }, { text: say("bodyAfter") }, { text: say("caseUnknown") }],
      },
    ],
    actions: [
      { text: say("confirm"), tone: "danger", run: () => void deleteFolder(title) },
      { text: say("cancel"), tone: "ghost", dismiss: true },
    ],
  });
}

registerVerb("staging-delete", (title) => openDeleteConfirm(title));
