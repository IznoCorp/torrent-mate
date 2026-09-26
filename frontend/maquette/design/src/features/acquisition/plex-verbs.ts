// « Confirmer » and « Corriger » — the two verbs on a Plex match (demand E).
//
// They act on THE MATCH ITSELF: the operator judges the match Plex made without
// being sent through the candidates screen. Either answer takes the card off
// « À traiter »; a correction then goes through the candidates screen, where the
// right identity is named.
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";
import { send } from "../../lib/query-client";
import { registerVerb } from "../../lib/verbs";
import { screens, toast } from "../../lib/shell-doors";

/** The queue the card is drawn from, asked again once the match is answered. */
const QUEUE = ["/api/acquisition/to-handle"];

/**
 * Answers one medium's Plex match.
 *
 * @param client The cache the surfaces read.
 * @param outcome Whether the match is the medium.
 * @param title The medium.
 */
async function answerMatch(client: QueryClient, outcome: "confirm" | "correct", title: string): Promise<void> {
  await send("POST", `/api/acquisition/journeys/${encodeURIComponent(title)}/plex-match`, { outcome });
  await client.invalidateQueries({ queryKey: QUEUE });
  if (outcome === "correct") screens.resolution(title);
  else toast?.show({ message: i18next.t("verbs.acquisition.plexConfirmed", { title }) });
}

/**
 * Declares the two verbs to the tap registry.
 *
 * @param client The cache the surfaces read.
 */
export function installPlexVerbs(client: QueryClient): void {
  registerVerb("plex-confirm", (title) => {
    void answerMatch(client, "confirm", title);
  });
  registerVerb("plex-correct", (title) => {
    void answerMatch(client, "correct", title);
  });
}
