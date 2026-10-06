// « Mettre fin » — one of the account's other sessions is ended from Profil.
//
// IT IS A REGISTERED VERB (`session-end`, the session's id), like every destructive gesture of the
// interface, so the harness's consent rule (R412) taps it the way a hand does: the tap opens a
// confirmation that NAMES the device and sends nothing, and only the confirmation calls the
// operation. Ending a session cannot be undone.
//
// WHERE EACH END STANDS lives here, by session id, because the verb answers outside the React tree
// that draws the rows: the section reads it through `useEndings`.
import { useSyncExternalStore } from "react";
import i18next from "i18next";

import { HELD, send, sharedQueryClient } from "../../lib/query-client";
import { refusalWords } from "../../lib/refusal";
import { dialog } from "../../lib/shell-doors";
import { registerVerb } from "../../lib/verbs";
import type { components } from "../../contract/types";

type OwnSession = components["schemas"]["OwnSession"];

/** The query key of the account's sessions. */
export const SESSIONS_KEY = ["/api/v1/auth/sessions"];

/** The words under Profil's « Appareils connectés ». */
export const WORDS = "screens.accountPage.sessions";

/** Where one session's end stands: asked of the server, held offline, or refused with words. */
export type Ending = { kind: "ending" } | { kind: "held" } | { kind: "refused"; words: string };

let endings: Readonly<Record<number, Ending>> = {};
const listeners = new Set<() => void>();

/**
 * Records where one session's end stands, and tells the rows.
 *
 * @param id The session's id.
 * @param ending Where its end stands, or null once it needs no word.
 */
function settle(id: number, ending: Ending | null): void {
  const { [id]: _gone, ...rest } = endings;
  endings = ending === null ? rest : { ...rest, [id]: ending };
  for (const listener of listeners) listener();
}

/**
 * Forgets every end: Profil is left, and the next visit starts from the server's list.
 */
export function forgetEndings(): void {
  endings = {};
  for (const listener of listeners) listener();
}

/**
 * Where each session's end stands, by session id.
 *
 * @returns The ends asked, held or refused; a session absent from it is at rest.
 */
export function useEndings(): Readonly<Record<number, Ending>> {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => void listeners.delete(listener);
    },
    () => endings,
  );
}

/**
 * Ends one session on the server, the outcome recorded for its row.
 *
 * @param id The session's id.
 */
async function end(id: number): Promise<void> {
  settle(id, { kind: "ending" });
  try {
    const answer = await send("DELETE", `/api/v1/auth/sessions/${id}`);
    // HELD: the network is down and the outbox keeps the end — it is not done, and is not shown as done.
    if (answer === HELD) return settle(id, { kind: "held" });
    settle(id, null);
    await sharedQueryClient?.invalidateQueries({ queryKey: SESSIONS_KEY });
  } catch (refused) {
    settle(id, { kind: "refused", words: refusalWords(refused, `${WORDS}.refused`) });
    await sharedQueryClient?.invalidateQueries({ queryKey: SESSIONS_KEY });
  }
}

/**
 * Opens the confirmation that names the session's device.
 *
 * THE SESSION IS READ FROM THE LIST THE SECTION DREW: a session the list no longer holds opens
 * nothing, and the current one is never offered an end (the server refuses it too).
 *
 * @param id The session's id.
 */
export function openEndConfirm(id: number): void {
  const listed = sharedQueryClient?.getQueryData<{ sessions: OwnSession[] }>(SESSIONS_KEY);
  const session = listed?.sessions.find((one) => one.id === id);
  if (session === undefined || session.current) return;
  const t = i18next.t.bind(i18next);
  dialog?.open({
    heading: t(`${WORDS}.confirm.heading`),
    body: [{
      type: "paragraph",
      runs: [
        { text: t(`${WORDS}.confirm.bodyBefore`) },
        { text: session.device ?? t(`${WORDS}.unknownDevice`), strong: true },
        { text: t(`${WORDS}.confirm.bodyAfter`) },
      ],
    }],
    actions: [
      { text: t(`${WORDS}.confirm.confirm`), tone: "danger", run: () => void end(id) },
      { text: t(`${WORDS}.confirm.cancel`), tone: "ghost", dismiss: true },
    ],
  });
}

registerVerb("session-end", (value) => {
  const id = Number(value);
  if (Number.isInteger(id)) openEndConfirm(id);
});
