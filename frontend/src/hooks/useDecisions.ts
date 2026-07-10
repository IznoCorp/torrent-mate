/**
 * TanStack Query hooks for the decisions domain (scrape-arbiter §4.1).
 *
 * Thin wrappers over the typed helpers in :mod:`@/api/decisions`.  Follows
 * the pattern established by {@link usePipelineStatus}: stable query keys
 * from {@link decisionsKeys}, ``useMutation`` hooks that invalidate the
 * relevant cache entries on success, and error surfaces as
 * :class:`ApiError`.
 */

import { useQueries, useQuery } from "@tanstack/react-query";

import {
  type DecisionListItem,
  type DecisionsParams,
  type DecisionsResponse,
  type DecisionDetailResponse,
  decisionsKeys,
  fetchDecisionDetail,
  fetchDecisions,
} from "@/api/decisions";
import type { DecisionStatus } from "@/components/decisions/triggers";

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

/**
 * Fetch a paginated list of scrape decisions.
 *
 * Query key: ``['decisions', { status, page, page_size }]``.
 *
 * Args:
 *   params: Optional pagination and filter query parameters.  Defaults to
 *       ``{}`` which the backend interprets as ``status='pending'``, page 1,
 *       page_size 50.
 *
 * Returns:
 *   The TanStack Query result for a {@link DecisionsResponse}.
 */
export function useDecisions(params: DecisionsParams = {}) {
  return useQuery<DecisionsResponse>({
    queryKey: decisionsKeys.list(params),
    queryFn: () => fetchDecisions(params),
  });
}

/**
 * Fetch full detail for a single scrape decision.
 *
 * Query key: ``['decisions', id]``.
 *
 * Args:
 *   id: Primary key of the ``scrape_decision`` row.
 *
 * Returns:
 *   The TanStack Query result for a {@link DecisionDetailResponse}.
 */
export function useDecisionDetail(id: number) {
  return useQuery<DecisionDetailResponse>({
    queryKey: decisionsKeys.detail(id),
    queryFn: () => fetchDecisionDetail(id),
    enabled: id > 0,
  });
}

// ---------------------------------------------------------------------------
// Aggregated all-status list (§4.1 flat list)
// ---------------------------------------------------------------------------

/** The four backend decision statuses, in operator-facing display order. */
const ALL_STATUSES: readonly DecisionStatus[] = [
  "pending",
  "resolved",
  "dismissed",
  "superseded",
];

/**
 * The API caps ``page_size`` at 200 and there is no "all statuses" filter (the
 * ``status`` param defaults to ``pending`` and only accepts a single enum
 * value). We fetch one page per status at the max page size — enough for the
 * operator's decision backlog without paging UI in the flat view.
 */
const AGGREGATE_PAGE_SIZE = 200;

/** Aggregated result of {@link useAllDecisions}. */
export interface AllDecisionsResult {
  /** Merged, deduped, newest-first list across every status. */
  readonly items: readonly DecisionListItem[];
  /**
   * Per-status total row count (independent of the flat list length).
   *
   * ``null`` for a status whose query FAILED — so a transient 500 renders as
   * "undetermined", not a misleading "0" (SF2). A successful query is always a
   * number (``0`` genuinely means zero rows).
   */
  readonly counts: Readonly<Record<DecisionStatus, number | null>>;
  /** ``true`` while any of the four per-status queries is still loading. */
  readonly isLoading: boolean;
  /** ``true`` when every per-status query failed (partial success is tolerated). */
  readonly isError: boolean;
  /**
   * The set of statuses whose query FAILED (SF2).
   *
   * Lets the page distinguish "0 pending" (successful, empty) from "pending
   * failed to load" (query errored) per status — a partial failure on the core
   * ``pending`` signal must not be silently coerced to zero.
   */
  readonly errored: ReadonlySet<DecisionStatus>;
}

/**
 * Fetch decisions across ALL statuses and merge them into one flat list.
 *
 * The ``GET /api/decisions`` endpoint takes a single ``status`` filter (default
 * ``pending``) with no "all" option, so a flat cross-status view requires one
 * query per status merged client-side. Each status is fetched in parallel via
 * {@link useQueries}; the four results are concatenated, deduplicated by ``id``
 * (a row can only ever hold one status, but a status transition between two
 * fetches could momentarily surface the same ``id`` twice), and sorted
 * newest-first by ``created_at``.
 *
 * Partial failure is tolerated: if e.g. the ``superseded`` query fails but the
 * others succeed, the merged list still shows the successful statuses and
 * ``isError`` stays ``false``. ``isError`` is ``true`` only when every query
 * failed.
 *
 * Args:
 *   activeStatuses: Optional subset of statuses to include. When omitted or
 *       empty, all four statuses are fetched (the default flat view). Passing a
 *       subset lets the page's optional filter chips narrow the fetch without a
 *       separate code path.
 *
 * Returns:
 *   An {@link AllDecisionsResult} with the merged ``items``, per-status
 *   ``counts``, and aggregate ``isLoading`` / ``isError`` flags.
 */
export function useAllDecisions(
  activeStatuses?: readonly DecisionStatus[],
): AllDecisionsResult {
  // An empty/omitted filter means "show everything"; a non-empty subset narrows
  // both the fetch and the merge. Counts are always requested for every status
  // so the chips can show a live total even when filtered out of the list.
  const listStatuses =
    activeStatuses != null && activeStatuses.length > 0
      ? activeStatuses
      : ALL_STATUSES;

  const results = useQueries({
    queries: ALL_STATUSES.map((status) => {
      const params: DecisionsParams = {
        status,
        page: 1,
        page_size: AGGREGATE_PAGE_SIZE,
      };
      return {
        queryKey: decisionsKeys.list(params),
        queryFn: () => fetchDecisions(params),
      };
    }),
  });

  // Per-status totals for the chip counters (independent of the active filter).
  // A FAILED query yields ``null`` (undetermined), NOT ``0`` — coercing a failed
  // query to zero would render a transient 500 as a false "0 decisions" (SF2).
  const counts = {} as Record<DecisionStatus, number | null>;
  const errored = new Set<DecisionStatus>();
  ALL_STATUSES.forEach((status, idx) => {
    const result = results[idx];
    if (result?.isError === true) {
      counts[status] = null;
      errored.add(status);
    } else {
      counts[status] = result?.data?.total ?? 0;
    }
  });

  // Merge only the statuses in scope, dedup by id, newest-first.
  const activeSet = new Set(listStatuses);
  const byId = new Map<number, DecisionListItem>();
  ALL_STATUSES.forEach((status, idx) => {
    if (!activeSet.has(status)) return;
    const data = results[idx]?.data;
    if (data == null) return;
    for (const item of data.items) {
      byId.set(item.id, item);
    }
  });
  const items = Array.from(byId.values()).sort(
    (a, b) => b.created_at - a.created_at,
  );

  const isLoading = results.some((r) => r.isLoading);
  const isError = results.every((r) => r.isError);

  return { items, counts, isLoading, isError, errored };
}

// NOTE (coherence study F12): the resolve / dismiss / search MUTATIONS live
// inline in DecisionDetail.tsx, where they carry the per-call toast, local
// state, via-computation (F09), and completion-poll (F19) logic. The former
// useResolveDecision / useDismissDecision / useSearchCandidates hooks here were
// dead code that had already diverged from those inline copies (dual source of
// truth) and were deleted. Keep only the two query hooks above.
