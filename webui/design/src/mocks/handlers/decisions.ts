// What the scrape could not decide alone.
import { GET, POST, route, text } from "./shared";
import { mockState } from "../state";
import { refused, type MockRoute } from "../router";
import { scenario } from "../scenario";
import type { components } from "../../contract/types";

/** Where a decision has got to, as the contract's own enum names it. */
type DecisionState = components["schemas"]["DecisionState"];

/** How a candidate was reached, as the contract's own enum names it. */
type DecisionRoute = components["schemas"]["DecisionRoute"];

// The engine keys its French labels by these same tokens (`DECISION_STATE`,
// classified `interface` — the labels are the interface's, the tokens are the
// contract's). The type above is what refuses a misspelling of one.
const RESOLVED: DecisionState = "resolved";
const DISMISSED: DecisionState = "dismissed";

/** Who settled a decision, as the contract's own enum names it. */
type DecisionAuthor = components["schemas"]["DecisionAuthor"];

/** A decision settled through this screen is the operator's. */
const OPERATOR: DecisionAuthor = "operator";

/** How a candidate was reached when it came from the offered list. */
const PICKED: DecisionRoute = "pick";

/** The language the seeds' dates are written in, which a stamp written now matches. */
const SEED_WRITTEN_IN = "fr-FR";

/**
 * The moment a decision is settled, in the shape the seeds carry one.
 *
 * A DECISION SETTLED NOW READS NOW. It carried the pending decision's creation
 * — « 15 juillet » for a choice just made, older than the card's « arrivé ».
 * The day is the layer's frozen clock, the one every date-derived state reads;
 * the hour is the wall clock's, the one moment the layer has for « now ».
 *
 * @returns The day and the hour, as « 10 août, 14 h 05 ».
 */
export function settledNow(): string {
  const day = new Intl.DateTimeFormat(SEED_WRITTEN_IN, { day: "numeric", month: "long", timeZone: "UTC" })
    .format(new Date(scenario().now));
  const clock = new Date();
  const two = (value: number) => String(value).padStart(2, "0");
  return `${day}, ${two(clock.getHours())} h ${two(clock.getMinutes())}`;
}

/**
 * Moves one decision from the pending list to the settled one.
 *
 * THE ARBITRATION IS RECORDED, and it was not. `resolveDecision` carries the
 * provider and the identifier of the candidate that was picked, and writing
 * only the new STATE lost the whole subject of the screen: which candidate the
 * operator chose became unrecoverable from the next read.
 *
 * @param folder The staging folder the decision is about.
 * @param state The state it settles into.
 * @param chosen The candidate the operator picked, when there was one.
 * @returns The decision's new state, or null when no decision answers.
 */
function settle(
  folder: string,
  state: DecisionState,
  chosen?: { provider: string; providerId: number },
): unknown {
  const held = mockState();
  const found = held.pendingDecisions.find((decision) => decision.folder === folder);
  if (found === undefined) return null;
  held.pendingDecisions = held.pendingDecisions.filter((decision) => decision !== found);
  // A settled decision is not a pending one with a field blanked: the contract
  // gives it its own shape, and the fields it keeps are named here so a reader
  // sees which of them survive the move.
  // The choice names the candidate the decision was OFFERED, found in its own
  // candidate list: the title comes from the data rather than from the request,
  // which carries only an identity.
  const candidate =
    chosen === undefined
      ? undefined
      : found.candidates.find(
          (offered) =>
            offered.provider === chosen.provider && offered.id === chosen.providerId,
        );
  held.settledDecisions = [
    {
      // The mocks address a decision by its folder, so its id is the folder.
      id: found.folder,
      folder: found.folder,
      kind: found.kind,
      title: found.title,
      reason: found.reason,
      when: settledNow(),
      year: found.year ?? undefined,
      state,
      candidates: found.candidates,
      settledBy: OPERATOR,
      ...(candidate === undefined
        ? {}
        : {
            choice: {
              title: candidate.title,
              provider: candidate.provider,
              id: candidate.id,
              via: PICKED,
              // The candidate's own picture: the choice IS that candidate.
              poster: candidate.poster,
            },
          }),
    },
    ...held.settledDecisions,
  ];
  return { state };
}

/**
 * Settles the decision a folder waits on with the candidate chosen by its title.
 *
 * The queue's « continue » carries the candidate's TITLE, which is what the
 * screen's pick names; the decision records it by provider and id, from its
 * own candidate list.
 *
 * @param folder The staging folder.
 * @param chosenTitle The candidate's title, or an empty string.
 * @returns Whether a pending decision was settled.
 */
export function settleChosen(folder: string, chosenTitle: string): boolean {
  const found = mockState().pendingDecisions.find((decision) => decision.folder === folder);
  const candidate = found?.candidates.find((offered) => offered.title === chosenTitle);
  if (found === undefined) return false;
  settle(folder, RESOLVED, candidate && { provider: candidate.provider, providerId: candidate.id });
  return true;
}

/** Why a folder sent to arbitration by hand is waiting, as the contract's token. */
const SENT_BY_HAND = "manual";

/** The status of an enqueue that finds nothing to send. */
const NOT_FOUND = 404;

/**
 * Sends a staged medium to arbitration: a pending decision, with candidates.
 *
 * IDEMPOTENT, the one refusal DOIT-4 allows: a folder already waiting answers
 * the decision it has. A medium the engine identified alone leaves the settled
 * list — its identification is what is being doubted — and waits again with
 * the candidates its own decision offered, the engine's pick among them marked
 * as kept.
 *
 * @param mediaId The staged medium, which the layer names by its folder.
 * @returns The enqueue's answer, or a refusal when nothing is staged under that name.
 */
function enqueue(mediaId: string): unknown {
  const held = mockState();
  const waiting = held.pendingDecisions.find((decision) => decision.folder === mediaId);
  const identified = held.settledDecisions.find(
    (decision) => decision.id === mediaId && decision.settledBy === "engine",
  );
  if (waiting === undefined && identified === undefined) {
    return refused(NOT_FOUND, "no staged medium the engine identified is filed under that folder");
  }
  const decision = waiting ?? {
    folder: identified!.folder,
    kind: identified!.kind,
    title: identified!.title,
    reason: SENT_BY_HAND,
    when: identified!.when,
    year: identified!.year ?? null,
    candidates: identified!.candidates,
    kept: identified!.choice,
  };
  if (waiting === undefined) {
    held.settledDecisions = held.settledDecisions.filter((settled) => settled !== identified);
    held.pendingDecisions = [decision, ...held.pendingDecisions];
  }
  return {
    ok: true,
    mediaKind: decision.kind === "movie" ? "movie" : "tvshow",
    title: decision.title,
    decisionId: decision.folder,
    candidatesCount: decision.candidates.length,
    candidatesSeeded: decision.candidates.length > 0,
  };
}

/**
 * Re-opens a decision the operator settled: it waits again, with candidates.
 *
 * « CORRIGER » ON THE OPERATOR'S OWN CHOICE (L24 OPEN 7 = A) — in Acquisition,
 * and on a shelved medium's sheet (OPEN 8 = A). The settled row leaves the
 * settled list and is pending again, with THE CANDIDATES IT OFFERED — never a
 * search's, which answered one card for « Parmi 3 candidats » — its earlier
 * choice marked as kept; the choice among them is the operator's again.
 *
 * @param decisionId The settled decision.
 * @returns The re-opened decision's address, or a refusal when none is settled under that id.
 */
function reopen(decisionId: string): unknown {
  const held = mockState();
  const settled = held.settledDecisions.find((decision) => decision.id === decisionId);
  if (settled === undefined) return refused(NOT_FOUND, "no settled decision carries that id");
  const candidates = settled.candidates;
  held.settledDecisions = held.settledDecisions.filter((decision) => decision !== settled);
  held.pendingDecisions = [
    {
      folder: settled.folder,
      kind: settled.kind,
      title: settled.title,
      reason: settled.reason,
      when: settled.when,
      year: settled.year ?? null,
      candidates,
      kept: settled.choice,
    },
    ...held.pendingDecisions.filter((decision) => decision.folder !== settled.folder),
  ];
  return { decisionId: settled.folder, folder: settled.folder, candidatesCount: candidates.length };
}

/** Every route this subject answers. */
export function decisionRoutes(): MockRoute[] {
  return [
    route("readDecisions", GET, "/decisions/", () => {
      const held = mockState();
      return { pending: held.pendingDecisions, settled: held.settledDecisions };
    }),
    route("resolveDecision", POST, "/decisions/{decisionId}/resolve", (request) => {
      const provider = text(request.body, "provider");
      const providerId = Number(text(request.body, "providerId"));
      return settle(
        request.parameters.decisionId,
        RESOLVED,
        provider === "" ? undefined : { provider, providerId },
      );
    }),
    route("dismissDecision", POST, "/decisions/{decisionId}/dismiss", (request) =>
      settle(request.parameters.decisionId, DISMISSED),
    ),
    route("enqueueForResolution", POST, "/staging/media/{mediaId}/enqueue", (request) =>
      enqueue(request.parameters.mediaId),
    ),
    route("reopenDecision", POST, "/decisions/{decisionId}/reopen", (request) =>
      reopen(request.parameters.decisionId),
    ),
    route("searchForDecision", POST, "/decisions/{decisionId}/search", (request) => {
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
