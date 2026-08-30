// What Arrivées asks the server for, and nothing else.
//
// THE FIRST SURFACE OF L09, and the shape every other one follows. Three reads:
// the pipeline's own status, what is sitting in staging, and the decisions the
// scrape could not make alone. Each goes through the query cache — invariant 4 —
// and none of them is issued from a `useEffect` — invariant 5.
//
// THE ANSWER IS CONVERTED BACK INTO THE ENGINE'S NAMES, and that is a
// transitional step with a date rather than a design. This surface's MARKUP is
// still drawn by producers in `legacy.js` (`cardHTML`, `secInner`,
// `factRowsHTML`), which read `t`, `s`, `r`, `d`, `c`; the contract answers in
// full English words. `lib/engine-shape.ts` inverts the projection L08
// DECLARED, so the two ends cannot drift — and the whole conversion dies with
// those producers at L13.
//
// THE KEYS ARE THE ADDRESS, deliberately. A cache key that repeated the
// surface's name would make two surfaces reading one resource miss each other's
// invalidations; the address is what the resource IS.
import { useQuery, type QueryClient } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { QueueCard } from "../../lib/engine-queue";
import { queueNow } from "../../lib/queue";
import type { PendingDecision, Pipeline, SettledDecision } from "./reference";

/** What the staging read answers with, once it wears the engine's names. */
export type Staging = {
  stuck: QueueCard[];
  moving: QueueCard[];
  settled: QueueCard[];
};

/** What the decisions read answers with, once it wears the engine's names. */
export type Decisions = {
  pending: PendingDecision[];
  settled: SettledDecision[];
};

/**
 * The pipeline's own status: its steps, its trigger vocabulary, its last run.
 *
 * @returns The query, its data already in the engine's names.
 */
export function usePipeline() {
  return useQuery({
    queryKey: ["/api/pipeline/status"],
    queryFn: async () =>
      toEngineShape<Pipeline>("PIPELINE", await read("/api/pipeline/status")),
  });
}

/**
 * What is sitting in staging: stuck, moving, settled.
 *
 * THE SCENARIO IS PART OF THE KEY, and it has to be. The engine has always
 * carried two datasets and the prototype's harness switches between them
 * (`scen`); a key that ignored which one was asked for would answer the first
 * one it cached, and a named state would render the other one's data.
 *
 * @param scenario Which dataset to read, as the harness's own dial names it.
 * @returns The query, its cards already in the engine's names.
 */
export function useStaging(scenario: string) {
  return useQuery({
    queryKey: ["/api/staging/media", scenario],
    queryFn: async () => {
      const query = new URLSearchParams(scenario ? { scenario } : {});
      const answer = await read<Record<string, unknown[]>>("/api/staging/media", query);
      // EACH LIST CONVERTS UNDER ITS OWN FAMILY, because that is what the
      // declaration says: the three share the `$card` shorthand, and naming
      // them separately is what keeps the day one of them stops sharing it from
      // being silent.
      return {
        stuck: toEngineShape<QueueCard[]>("STUCK_REAL", answer.stuck),
        moving: toEngineShape<QueueCard[]>("MOVING", answer.moving),
        settled: toEngineShape<QueueCard[]>("SETTLED_REAL", answer.settled),
      } satisfies Staging;
    },
  });
}

/**
 * The decisions the scrape could not make alone, on both sides of resolution.
 *
 * @returns The query, its decisions already in the engine's names.
 */
export function useDecisions() {
  return useQuery({
    queryKey: ["/api/decisions/"],
    queryFn: async () => {
      const answer = await read<{ pending: unknown; settled: unknown }>("/api/decisions/");
      return {
        pending: toEngineShape<PendingDecision[]>("PENDING_DECISIONS", answer.pending),
        settled: toEngineShape<SettledDecision[]>("DECISIONS_REGLEES", answer.settled),
      } satisfies Decisions;
    },
  });
}

/**
 * Publishes the pending decisions for the dying engine to read synchronously.
 *
 * WHY A SEAM AND NOT AN IMPORT. `legacy.js` answers « does this folder have a
 * pending decision » from inside a click handler, which cannot await — and it
 * is the same question the resolution screen asks. §13 of the constitution:
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
  window.__pendingDecisions = () =>
    (queryClient.getQueryData(["/api/decisions/"]) as Decisions | undefined)?.pending ?? [];
}

declare global {
  interface Window {
    /** The pending decisions, read synchronously by the dying engine. */
    __pendingDecisions?: () => PendingDecision[];
  }
}

/**
 * What awaits the operator on this page — the navigation table's badge.
 *
 * WHAT IS STUCK, and only that. Arrivées carries the health of the pipeline:
 * what is moving needs nobody, what is settled is done, and what is STUCK is
 * the thing a badge exists to say. One derivation, read by the tab bar, by the
 * drawer and — while it still draws them — by the engine through the seam.
 *
 * Returns:
 *     How many items are stuck in staging.
 */
export function arrivalsBadge(): number {
  return queueNow().stuck.length;
}
