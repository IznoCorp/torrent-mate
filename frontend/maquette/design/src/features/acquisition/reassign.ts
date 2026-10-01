// « Réaffecter… » — one requester of an acquisition handed to another account
// (§ 17; round 8 Q13 = A: an act of the card's panel and the follow's panel).
//
// THE CHOOSER LISTS ONLY THE ACCOUNTS THAT SEE THE ACQUISITION (M9): those
// whose role holds `acquisition.see.others`, those already among its
// requesters, and Admin — never the whole roster, which would hand a card to an
// account with no way to find it again. Whether an account sees it is the
// model's own answer on that account's role, never a role compared by name.
//
// THE MOVE IS THE SERVER'S: `reassignRequester` answers the requesters after
// it, the lists are read again, and the card's line says the new names.
import i18next from "i18next";
import type { QueryClient } from "@tanstack/react-query";

import { read, send } from "../../lib/query-client";
import { panel, toast } from "../../lib/shell-doors";
import { registerVerb } from "../../lib/verbs";
import { registerProducer, type PanelCache, type PanelDescriptor } from "../../ui/panel/contract";
import type { Schemas } from "../../lib/contract-schemas";
import { rightsOf } from "../../lib/rights";
import { accountsQuery } from "../../lib/account";
import { heldAcquisition } from "./act-rights";
import { followsQuery } from "./queries";
import { queueKey } from "../../lib/queue";

// What separates the parts of a subject and of a verb's value: a title may
// carry a colon, never this.
const PART = "|";

/**
 * The accounts that SEE an acquisition (M9).
 *
 * @param roster Every account.
 * @param requesters Who asked for the acquisition.
 * @returns The accounts it could be handed to.
 */
export function eligibleAccounts(
  roster: Schemas["Roster"],
  requesters: readonly { id: string }[],
): Schemas["AccountSummary"][] {
  return roster.accounts.filter((one) =>
    requesters.some((requester) => requester.id === one.id)
    || rightsOf({ ...one, avatar: "", forbiddenWrites: [] }).holds("acquisition.see.others"));
}

/**
 * The chooser's descriptor.
 *
 * @param subject `kind|title` — a follow or a card, and the acquisition's title.
 * @param cache What the query cache holds.
 * @returns The descriptor, or null while the roster has not landed.
 */
function reassignPanel(subject: string, cache: PanelCache): PanelDescriptor | null {
  const roster = cache.held<Schemas["Roster"]>(accountsQuery.queryKey);
  if (roster === undefined) return null;
  const [kind, title] = subject.split(PART);
  const requesters = heldAcquisition(title).requesters ?? [];
  const from = requesters[0];
  const translate = i18next.t.bind(i18next);
  const choices = from === undefined ? [] : eligibleAccounts(roster, requesters).filter((one) => one.id !== from.id);
  return {
    address: "reassign:" + subject,
    title: translate("panels.reassign.title", { title }),
    blocs: [
      { type: "note", text: from ? translate("panels.reassign.note", { name: from.name }) : translate("panels.reassign.empty") },
      choices.length
        ? {
            type: "actions",
            actions: choices.map((one) => ({
              text: one.name,
              mention: one.role.name,
              target: { "reassign-to": [kind, title, from!.id, one.id].join(PART) },
            })),
          }
        : { type: "note", text: translate("panels.reassign.empty") },
    ],
  };
}

// THE ACQUISITION'S REQUESTERS ARE READ FROM THE LISTS, so the chooser waits
// for them as it waits for the roster: the queue at rest and the follows.
const queueAtRest = {
  queryKey: queueKey(""),
  queryFn: async () => read<Schemas["AcquisitionQueue"]>("/api/acquisition/to-handle"),
};

registerProducer("reassign", { produce: reassignPanel, needs: () => [accountsQuery, queueAtRest, followsQuery()] });

/**
 * The act that opens the chooser, for a panel to carry.
 *
 * @param kind A follow or a card.
 * @param title The acquisition.
 * @returns The action.
 */
export function reassignAction(kind: "follow" | "card", title: string) {
  return {
    text: i18next.t("panels.reassign.act"),
    target: { panel: ["reassign", [kind, title].join(PART)].join(":") },
  };
}

/**
 * Declares « reassign-to » to the tap registry.
 *
 * @param client The cache the lists are read from again once the move is answered.
 */
export function installReassignVerb(client: QueryClient): void {
  registerVerb("reassign-to", (value) => {
    const [kind, title, from, to] = value.split(PART);
    void (async () => {
      try {
        await send("POST", "/api/acquisition/requesters/reassign", { kind, title, from, to });
        const roster = client.getQueryData<Schemas["Roster"]>(accountsQuery.queryKey);
        const name = roster?.accounts.find((one) => one.id === to)?.name ?? to;
        panel?.close();
        toast?.show({ message: i18next.t("verbs.reassign.done", { name }) });
        await client.refetchQueries({ queryKey: ["/api/acquisition/to-handle"] });
        await client.refetchQueries({ queryKey: ["/api/acquisition/followed"] });
      } catch {
        toast?.show({ message: i18next.t("verbs.reassign.refused") });
      }
    })();
  });
}
