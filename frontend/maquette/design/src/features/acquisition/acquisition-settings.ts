// Each requester's own quality and pause on an acquisition (§ 17; round 10 Q6).
//
// PER ACQUISITION, PER REQUESTER, AND ROLE-GATED: an account sets its own
// quality floor under `acquisition.quality.own` and its own pause under
// `acquisition.pause.own`, on an acquisition it asked for. What is IN FORCE is
// the server's answer: the highest floor among the requesters whose role holds
// the right, and « paused » only once every such requester asked for it.
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";

import { send } from "../../lib/query-client";
import { panel, toast } from "../../lib/shell-doors";
import { registerVerb } from "../../lib/verbs";
import type { Schemas } from "../../lib/contract-schemas";
import type { Rights } from "../../lib/rights";
import { followsQuery } from "./queries";

// What separates a title from the value a verb carries: a title may carry a colon, never this.
const PART = "|";

/**
 * The pause act a follow's panel carries, and the note that says where the pause stands.
 *
 * @param follow The follow, with its settings.
 * @param rights What the account may do.
 * @returns The act (its verb gated by `act-rights`), and the note, or null when nothing is paused.
 */
export function pauseOffer(follow: Pick<Schemas["Follow"], "title" | "ownPaused" | "paused">, rights: Rights) {
  // A PAUSE OF ONE'S OWN EXISTS ONLY UNDER THE RIGHT: a setting left from a role
  // that held it, or seeded for one that never did, counts for nothing (round
  // 10 Q6) and is never said as « notée ».
  const own = follow.ownPaused === true && rights.holds("acquisition.pause.own");
  return {
    act: {
      text: i18next.t(own ? "panels.follow.resumeOwn" : "panels.follow.pauseOwn"),
      target: { "pause-own": [follow.title, String(!own)].join(PART) },
    },
    note: follow.paused
      ? i18next.t("panels.follow.pausedForAll")
      : own
        ? i18next.t("panels.follow.pauseWaitsForOthers")
        : null,
  };
}

/**
 * Declares « pause-own » to the tap registry.
 *
 * @param client The cache the follows are read from again once the pause is answered.
 */
export function installAcquisitionSettingVerbs(client: QueryClient): void {
  registerVerb("pause-own", (value) => {
    const cut = value.lastIndexOf(PART);
    const title = value.slice(0, cut);
    const paused = value.slice(cut + 1) === "true";
    void (async () => {
      try {
        await send("PUT", `/api/acquisition/followed/${encodeURIComponent(title)}/pause`, { paused });
        await client.refetchQueries({ queryKey: followsQuery().queryKey });
        panel?.redraw();
        toast?.show({ message: i18next.t(paused ? "verbs.acquisitionSettings.paused" : "verbs.acquisitionSettings.resumed") });
      } catch {
        toast?.show({ message: i18next.t("verbs.acquisitionSettings.refused") });
      }
    })();
  });
}
