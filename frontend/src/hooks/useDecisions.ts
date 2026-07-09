/**
 * TanStack Query hooks for the decisions domain (scrape-arbiter §4.1).
 *
 * Thin wrappers over the typed helpers in :mod:`@/api/decisions`.  Follows
 * the pattern established by {@link usePipelineStatus}: stable query keys
 * from {@link decisionsKeys}, ``useMutation`` hooks that invalidate the
 * relevant cache entries on success, and error surfaces as
 * :class:`ApiError`.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type DecisionsParams,
  type DecisionsResponse,
  type DecisionDetailResponse,
  type ResolveRequest,
  type ResolveResponse,
  type SearchRequest,
  type SearchResponse,
  decisionsKeys,
  dismissDecision,
  fetchDecisionDetail,
  fetchDecisions,
  resolveDecision,
  searchDecisionCandidates,
} from "@/api/decisions";

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
// Mutation hooks
// ---------------------------------------------------------------------------

/**
 * Launch a targeted re-scrape for a decision.
 *
 * Mutation with ``onSuccess`` invalidation of ``['decisions']`` (so the list
 * and detail cache refresh) and ``['pipeline', 'history']`` (so the new
 * scrape-resolve run appears in the pipeline history).
 *
 * Returns:
 *   A ``useMutation`` handle that accepts ``{id, body}``.
 */
export function useResolveDecision() {
  const queryClient = useQueryClient();

  return useMutation<ResolveResponse, Error, { id: number; body: ResolveRequest }>({
    mutationFn: ({ id, body }) => resolveDecision(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["pipeline", "history"] });
    },
  });
}

/**
 * Dismiss a decision (manual or MediaElch path).
 *
 * Mutation with ``onSuccess`` invalidation of ``['decisions']`` so the list
 * refreshes.  Also invalidates ``['decisions', id]`` so the detail view (if
 * open) reflects the ``'dismissed'`` status.
 *
 * Returns:
 *   A ``useMutation`` handle that accepts an ``id``.
 */
export function useDismissDecision() {
  const queryClient = useQueryClient();

  return useMutation<DecisionDetailResponse, Error, number>({
    mutationFn: (id) => dismissDecision(id),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.detail(id) });
    },
  });
}

/**
 * Search live providers for candidate matches (read-only, POST body).
 *
 * Mutation with **no** query key invalidation — the search results are
 * ephemeral and displayed inline; they do not update persisted state.
 *
 * Returns:
 *   A ``useMutation`` handle that accepts ``{id, body}``.
 */
export function useSearchCandidates() {
  return useMutation<SearchResponse, Error, { id: number; body: SearchRequest }>({
    mutationFn: ({ id, body }) => searchDecisionCandidates(id, body),
  });
}
