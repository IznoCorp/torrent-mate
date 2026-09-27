// « Abandonner » — a tunnel error the operator gives up on (ruling 7).
//
// ABANDONING QUARANTINES THE FOLDER: it is moved into the staging area's
// quarantine and the move journaled, never deleted. And nothing is destroyed
// without consent (NE-DOIT-PAS-6): the tap opens a confirmation that NAMES the
// medium, and only the confirmation calls the operation.
//
// ON A FOLLOW'S CARD THE FOLLOW GOES ON: the release is set aside and another
// is searched (§14.1), and the confirmation says so. A one-off arrival's card
// closes.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { dialog, toast } from "../../lib/shell-doors";
import { send, sharedQueryClient } from "../../lib/query-client";
import type { Schemas } from "../../lib/contract-schemas";

/** The reads a quarantined folder moves: the queue, the staging area and a follow's releases. */
const LEFT = [["/api/acquisition/to-handle"], ["/api/staging/media"], ["/api/acquisition/releases"]];

// The requester token of a card a follow asked for.
const ASKED_BY_FOLLOW = "follow";

/**
 * Whether the card a title names was asked for by a follow, in the queue as read.
 *
 * @param title The medium.
 * @returns True when a follow asked for it.
 */
function askedByFollow(title: string): boolean {
  const held = sharedQueryClient?.getQueriesData<Partial<Schemas["AcquisitionQueue"]>>({
    queryKey: ["/api/acquisition/to-handle"],
  }) ?? [];
  return held.some(([, queue]) => [...(queue?.arrivals ?? []), ...(queue?.blocked ?? [])]
    .some((card) => card.title === title && card.requester?.via === ASKED_BY_FOLLOW));
}

/**
 * Quarantines one folder, then says where it went.
 *
 * @param title The folder.
 */
async function quarantine(title: string): Promise<void> {
  const answer = (await send("POST", `/api/staging/media/${encodeURIComponent(title)}/discard`, {})) as
    | { quarantine_path?: string }
    | undefined;
  for (const queryKey of LEFT) await sharedQueryClient?.invalidateQueries({ queryKey });
  toast?.show({
    message: i18next.t("verbs.acquisition.abandon.done", { title: title, path: answer?.quarantine_path ?? "" }),
  });
}

/**
 * Opens the confirmation that names the medium; nothing is sent before it is confirmed.
 *
 * @param title The medium.
 */
export function openAbandonConfirm(title: string): void {
  const say = (key: string) => i18next.t(`verbs.acquisition.abandon.${key}`, { title });
  dialog?.open({
    heading: say("heading"),
    body: [{
      type: "paragraph",
      runs: [
        { text: say("bodyBefore") },
        { text: title, strong: true },
        { text: say("bodyAfter") },
        ...(askedByFollow(title) ? [{ text: say("bodyFollow") }] : []),
      ],
    }],
    actions: [
      { text: say("confirm"), tone: "danger", run: () => void quarantine(title) },
      { text: say("cancel"), tone: "ghost", dismiss: true },
    ],
  });
}

registerVerb("journey-abandon", (title) => openAbandonConfirm(title));
