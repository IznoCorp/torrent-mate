// « Corriger » — the act of a settled decision's block (L24 S5, DOIT-7).
//
// ONE ACT FOR BOTH AUTHORS (OPEN 7 = A). On an identification the engine made
// alone it CREATES the decision — `enqueueForResolution` — and on the
// operator's own choice it RE-OPENS that decision by its id —
// `reopenDecision`, on a shelved medium's sheet too (OPEN 8 = A). Either way
// the candidates screen opens on a decision that waits WITH its candidates, or
// on the pre-filled manual search when the providers offered none (§ 3): the
// call comes BEFORE the screen, never a screen opened on nothing.
//
// A refused call says its reason and opens nothing.
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";
import { HELD, isRequestFailure, send } from "../../lib/query-client";
import { registerVerb } from "../../lib/verbs";
import { screens, toast } from "../../lib/shell-doors";
import type { Decisions } from "./decision-queries";

/**
 * Sends one settled decision back to arbitration, then opens it.
 *
 * @param client The cache the surfaces read.
 * @param decisionId The settled decision the block names.
 */
async function correct(client: QueryClient, decisionId: string): Promise<void> {
  const decision = client
    .getQueryData<Decisions>(["/api/decisions/"])
    ?.settled.find((settled) => settled.id === decisionId);
  if (decision === undefined) return;
  const address = decision.settledBy === "engine"
    ? `/api/staging/media/${encodeURIComponent(decision.folder)}/enqueue`
    : `/api/decisions/${encodeURIComponent(decision.id)}/reopen`;
  try {
    const answered = await send("POST", address);
    if (answered === HELD) {
      toast?.show({ message: i18next.t("verbs.decision.correctHeld") });
      return;
    }
    // THE PENDING DECISION IS IN THE CACHE BEFORE THE SCREEN READS IT, so the
    // screen opens on its candidates rather than on « no medium identified ».
    await client.refetchQueries({ queryKey: ["/api/decisions/"] });
    screens.resolution(decision.folder);
  } catch (error) {
    toast?.show({
      message: i18next.t("verbs.decision.correctRefused", {
        reason: isRequestFailure(error) ? error.detail : String(error),
      }),
    });
  }
}

/**
 * Declares « Corriger » to the tap registry.
 *
 * @param client The cache the surfaces read.
 */
export function installCorrectVerb(client: QueryClient): void {
  registerVerb("decision-correct", (decisionId) => {
    void correct(client, decisionId);
  });
}
