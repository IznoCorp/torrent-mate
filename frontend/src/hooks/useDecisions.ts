/**
 * TanStack Query hooks for the decisions domain (scrape-arbiter §4.1).
 *
 * Thin wrappers over the typed helpers in :mod:`@/api/decisions`.  Follows
 * the pattern established by {@link usePipelineStatus}: stable query keys
 * from {@link decisionsKeys}, ``useMutation`` hooks that invalidate the
 * relevant cache entries on success, and error surfaces as
 * :class:`ApiError`.
 */

import { useQuery } from "@tanstack/react-query";

import {
  type DecisionsParams,
  type DecisionsResponse,
  type DecisionDetailResponse,
  decisionsKeys,
  fetchDecisionDetail,
  fetchDecisions,
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

// NOTE (coherence study F12): the resolve / dismiss / search MUTATIONS live
// inline in DecisionDetail.tsx, where they carry the per-call toast, local
// state, via-computation (F09), and completion-poll (F19) logic. The former
// useResolveDecision / useDismissDecision / useSearchCandidates hooks here were
// dead code that had already diverged from those inline copies (dual source of
// truth) and were deleted. Keep only the two query hooks above.
