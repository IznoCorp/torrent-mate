// « Supprimer » — a folder set aside, deleted from the disk (ruling 16).
//
// A REAL DELETION, NOT THE QUARANTINE « Abandonner » MAKES: the staging folder
// is removed and the deletion journaled. And nothing is destroyed without
// consent (NE-DOIT-PAS-6): the tap opens a confirmation of the Médiathèque's
// care that NAMES the folder — it has no provider identity — and says whether
// this copy is the only one; only the confirmation calls the operation.
//
// THE CASE IS READ WHEN THE CONFIRMATION OPENS, never from the day it arrived:
// the torrent may have left the download client since. A read that fails says
// « unknown », and unknown is treated as the only copy — never as a copy the
// torrent still keeps.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { dialog, toast } from "../../lib/shell-doors";
import { read, send, sharedQueryClient } from "../../lib/query-client";

/** The words each case the read answers is said in; any other answer is unknown. */
const CASE_WORDS: Record<string, string> = { keeps_files: "caseKeepsFiles", only_copy: "caseOnlyCopy" };
const UNKNOWN_WORDS = "caseUnknown";

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
 * Reads the folder's case, then opens the confirmation that names the folder and says it.
 *
 * Nothing is sent before it is confirmed.
 *
 * @param title The folder.
 */
export function openDeleteConfirm(title: string): void {
  void read<{ case: string }>(`/api/staging/media/${encodeURIComponent(title)}/copies`)
    .then((answer) => CASE_WORDS[answer.case] ?? UNKNOWN_WORDS, () => UNKNOWN_WORDS)
    .then((words) => openConfirm(title, words));
}

/**
 * Opens the confirmation, the case already read.
 *
 * @param title The folder.
 * @param words The key of the sentence saying its case.
 */
function openConfirm(title: string, words: string): void {
  const say = (key: string) => i18next.t(`verbs.acquisition.deleteStaged.${key}`, { title });
  dialog?.open({
    heading: say("heading"),
    body: [
      {
        type: "paragraph",
        runs: [{ text: say("bodyBefore") }, { text: title, strong: true }, { text: say("bodyAfter") }, { text: say(words) }],
      },
    ],
    actions: [
      { text: say("confirm"), tone: "danger", run: () => void deleteFolder(title) },
      { text: say("cancel"), tone: "ghost", dismiss: true },
    ],
  });
}

registerVerb("staging-delete", (title) => openDeleteConfirm(title));
