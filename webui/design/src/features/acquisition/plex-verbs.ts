// « Confirmer » and « Corriger » — the two verbs on a Plex match (demand E).
//
// They act on THE MATCH ITSELF: the operator judges the match Plex made without
// being sent through the candidates screen to confirm it. « Confirmer » answers
// at once and takes the card off « À traiter ». « Corriger » SENDS NOTHING: it
// opens the candidates screen on the identity held, and the correction is sent
// by the pick, carrying the identity picked — leaving the screen without one
// leaves the match to confirm, the card where it was.
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";
import { refusalWords } from "../../lib/refusal";
import { sendVerb } from "./verb-outcome";
import { registerVerb } from "../../lib/verbs";
import { queueNow } from "../../lib/queue";
import { toast } from "../../lib/shell-doors";
import type { Schemas } from "../../lib/contract-schemas";

/** The queue the card is drawn from, asked again once the match is answered. */
const QUEUE = ["/api/v1/acquisition/to-handle"];

/** An identity a match is answered with. */
type Identity = Schemas["PlexMatch"];

// The cache the surfaces read, held from the install for the answers a pick sends.
let heldClient: QueryClient | null = null;

/**
 * The match a medium waits on, when its Plex match is to be confirmed.
 *
 * READ FROM THE QUEUE, never from the address: the candidates screen answers a
 * Plex match only while the queue still holds one for that medium.
 *
 * @param title The medium.
 * @returns The identity Plex matched it to, or null.
 */
export function heldMatch(title: string): Identity | null {
  return queueNow().settled.find((card) => card.title === title)?.plexMatch ?? null;
}

/**
 * Answers one medium's Plex match, and says it — or says it is held, refused, or failed.
 *
 * @param outcome Whether the match is the medium.
 * @param title The medium.
 * @param identity The identity picked, which a correction carries.
 */
export async function answerMatch(outcome: "confirm" | "correct", title: string, identity?: Identity): Promise<void> {
  const sent = await sendVerb("POST", `/api/v1/acquisition/journeys/${encodeURIComponent(title)}/plex-match`,
    identity === undefined ? { outcome } : { outcome, identity });
  // HELD: the outbox keeps the answer, the match is not answered yet, and the queue is not read over it.
  if (sent.kind === "held") return void toast?.show({ message: i18next.t("verbs.acquisition.held") });
  if (sent.kind === "refused") {
    return void toast?.show({ message: refusalWords(sent.failure, "verbs.acquisition.refused") });
  }
  if (sent.kind === "failed") return void toast?.show({ message: i18next.t("verbs.acquisition.failed") });
  await heldClient?.invalidateQueries({ queryKey: QUEUE });
  toast?.show({
    message: outcome === "correct"
      ? i18next.t("verbs.acquisition.plexCorrected", { title, choice: identity?.title ?? title })
      : i18next.t("verbs.acquisition.plexConfirmed", { title }),
  });
}

/**
 * Declares the two verbs to the tap registry.
 *
 * @param client The cache the surfaces read.
 */
export function installPlexVerbs(client: QueryClient): void {
  heldClient = client;
  registerVerb("plex-confirm", (title) => {
    void answerMatch("confirm", title);
  });
  // The screen opens on the identity held; nothing is sent until a pick.
  // « CORRIGER » MATCHES IT TO WHAT WE HOLD (RULINGS 24): the identity held is
  // the correction, so no candidates screen is asked for.
  registerVerb("plex-correct", (title) => {
    const card = queueNow().settled.find((one) => one.title === title);
    void answerMatch("correct", title, { title, ids: card?.ids ?? {} } as Identity);
  });
}
