// What the scrape could not decide alone.
import { GET, POST, field, route, text } from "./shared";
import { mockState } from "../state";
import type { MockRoute } from "../router";
import type { components } from "../contract-types";

/** Where a decision has got to, as the contract's own enum names it. */
type DecisionState = components["schemas"]["DecisionState"];

// The engine keys its French labels by these same tokens (`DECISION_STATE`,
// classified `interface` — the labels are the interface's, the tokens are the
// contract's). The type above is what refuses a misspelling of one.
const RESOLVED: DecisionState = "resolved";
const DISMISSED: DecisionState = "dismissed";

/**
 * Moves one decision from the pending list to the settled one.
 *
 * @param folder The staging folder the decision is about.
 * @param state The state it settles into.
 * @returns The decision's new state, or null when no decision answers.
 */
function settle(folder: string, state: DecisionState): unknown {
  const held = mockState();
  const found = held.pendingDecisions.find((decision) => decision.folder === folder);
  if (found === undefined) return null;
  held.pendingDecisions = held.pendingDecisions.filter((decision) => decision !== found);
  // A settled decision is not a pending one with a field blanked: the contract
  // gives it its own shape, and the fields it keeps are named here so a reader
  // sees which of them survive the move.
  held.settledDecisions = [
    {
      folder: found.folder,
      kind: found.kind,
      title: found.title,
      reason: found.reason,
      when: found.when,
      year: found.year ?? undefined,
      state,
    },
    ...held.settledDecisions,
  ];
  return { state };
}

/** Every route this subject answers. */
export function decisionRoutes(): MockRoute[] {
  return [
    route("readDecisions", GET, "/api/decisions/", () => {
      const held = mockState();
      return { pending: held.pendingDecisions, settled: held.settledDecisions };
    }),
    route("resolveDecision", POST, "/api/decisions/{decisionId}/resolve", (request) =>
      settle(request.parameters.decisionId, RESOLVED),
    ),
    route("dismissDecision", POST, "/api/decisions/{decisionId}/dismiss", (request) =>
      settle(request.parameters.decisionId, DISMISSED),
    ),
    route("searchForDecision", POST, "/api/decisions/{decisionId}/search", (request) => {
      // A manual search over data that already exists: the candidates a
      // decision was offered, filtered by what was typed. Nothing is invented,
      // which is why an empty query answers the whole offered list.
      const found = mockState().pendingDecisions.find(
        (decision) => decision.folder === request.parameters.decisionId,
      );
      const offered = found?.candidates ?? [];
      const wanted = text(request.body, "query").toLowerCase();
      if (wanted === "") return offered;
      return offered.filter((candidate) =>
        candidate.title.toLowerCase().includes(wanted),
      );
    }),
  ];
}

// Read by nothing here, and kept out of the table on purpose: a decision's
// candidates are read from the decision itself, never from a request field.
void field;
