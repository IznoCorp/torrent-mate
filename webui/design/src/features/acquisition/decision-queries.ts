// The decisions the scrape could not make alone — the candidates screen's read.
//
// ACQUISITION'S, because an arrival is an acquisition card and the screen that
// names it opens from that card. The read goes
// through the query cache — invariant 4 — and is never issued from a
// `useEffect` — invariant 5.
//
// THE KEY IS THE ADDRESS, deliberately: two surfaces reading one resource share
// its invalidations.
import { useQuery, type QueryClient } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import type { PendingDecision, SettledDecision } from "./types";

/** What the decisions read answers with, once it wears the engine's names. */
export type Decisions = {
  pending: PendingDecision[];
  settled: SettledDecision[];
};

/**
 * The decisions the scrape could not make alone, on both sides of resolution.
 *
 * @returns The query, its decisions already in the engine's names.
 */
export function useDecisions() {
  return useQuery(DECISIONS_QUERY);
}

/** The decisions read as a query definition, for a panel that needs it before it draws. */
export const DECISIONS_QUERY = {
  queryKey: ["/api/v1/decisions/"],
  queryFn: async () => {
    const answer = await read<{ pending: PendingDecision[]; settled: SettledDecision[] }>("/api/v1/decisions/");
    return {
      pending: answer.pending,
      settled: answer.settled,
    } satisfies Decisions;
  },
};

/**
 * Publishes the pending decisions for a synchronous reader.
 *
 * WHY A SEAM AND NOT AN IMPORT. The engine (`engine/legacy.js@c0a5062ac`) answered « does this folder
 * have a pending decision » from inside a click handler, which cannot await — and
 * it was the same question the resolution screen asks. §13 of the constitution:
 * two surfaces answering one question read the SAME code, or they will
 * diverge and the operator will see two truths.
 *
 * It reports an empty list before the query has answered, which is the answer
 * this lookup already gave for a folder with no decision. It dies with the
 * engine's own branch at L13.
 *
 * @param queryClient The cache the surfaces read.
 */
export function installDecisionLookup(queryClient: QueryClient): void {
  pendingDecisions = () =>
    (queryClient.getQueryData(["/api/v1/decisions/"]) as Decisions | undefined)?.pending ?? [];
}

/** The pending decisions, read synchronously by the dying engine — filled at install. */
export let pendingDecisions: (() => PendingDecision[]) | undefined;
