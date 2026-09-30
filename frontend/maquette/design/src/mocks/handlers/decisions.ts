// What the scrape could not decide alone.
import { GET, POST, route, text } from "./shared";
import { mockState } from "../state";
import { refused, type MockRoute } from "../router";
import MEDIA_SHEETS from "../seeds/media-sheets.json";
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
      when: found.when,
      year: found.year ?? undefined,
      state,
      candidatesCount: found.candidates.length,
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

/** One candidate a decision offers, as the contract names it. */
type DecisionCandidate = components["schemas"]["DecisionCandidate"];

/** A media sheet of the seed, as far as a candidate reads it. */
type SeededSheet = { year?: string; overview?: string; ids?: Record<string, string | number> };

/** Why a folder sent to arbitration by hand is waiting, as the contract's token. */
const SENT_BY_HAND = "manual";

/** The status of an enqueue that finds nothing to send. */
const NOT_FOUND = 404;

/** The score a provider search gives a title found under its own name. */
const OWN_NAME_SCORE = 1;

/**
 * The candidates a provider search finds for one title, read off the seeded sheets.
 *
 * A SHEET IS A MEDIUM THE PROVIDERS KNOW, so the sheets filed under the title —
 * « Furious » and « Furious (2026) » — are what a search on that name answers.
 * One identity is offered once, whichever key it was filed under.
 *
 * @param title The title searched.
 * @returns The candidates, none when no sheet carries that title.
 */
function candidatesFor(title: string): DecisionCandidate[] {
  const found = new Map<string, DecisionCandidate>();
  for (const [name, sheet] of Object.entries(MEDIA_SHEETS as unknown as Record<string, SeededSheet>)) {
    if (name !== title && !name.startsWith(`${title} (`)) continue;
    const provider = sheet.ids?.tvdb ? "tvdb" : "tmdb";
    const id = Number(sheet.ids?.[provider]);
    if (!Number.isFinite(id) || found.has(`${provider}:${id}`)) continue;
    found.set(`${provider}:${id}`, {
      title: name,
      year: Number(sheet.year),
      provider,
      id,
      score: OWN_NAME_SCORE,
      withoutPoster: true,
      overview: sheet.overview ?? "",
      poster: null,
    });
  }
  return [...found.values()];
}

/**
 * Sends a staged medium to arbitration: a pending decision, with candidates.
 *
 * IDEMPOTENT, the one refusal DOIT-4 allows: a folder already waiting answers
 * the decision it has. A medium the engine identified alone leaves the settled
 * list — its identification is what is being doubted — and waits again with
 * the candidates a search on its title finds, or none, when the screen opens
 * on the pre-filled manual search.
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
    candidates: candidatesFor(identified!.title),
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

/** Every route this subject answers. */
export function decisionRoutes(): MockRoute[] {
  return [
    route("readDecisions", GET, "/api/decisions/", () => {
      const held = mockState();
      return { pending: held.pendingDecisions, settled: held.settledDecisions };
    }),
    route("resolveDecision", POST, "/api/decisions/{decisionId}/resolve", (request) => {
      const provider = text(request.body, "provider");
      const providerId = Number(text(request.body, "providerId"));
      return settle(
        request.parameters.decisionId,
        RESOLVED,
        provider === "" ? undefined : { provider, providerId },
      );
    }),
    route("dismissDecision", POST, "/api/decisions/{decisionId}/dismiss", (request) =>
      settle(request.parameters.decisionId, DISMISSED),
    ),
    route("enqueueForResolution", POST, "/api/staging/media/{mediaId}/enqueue", (request) =>
      enqueue(request.parameters.mediaId),
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
