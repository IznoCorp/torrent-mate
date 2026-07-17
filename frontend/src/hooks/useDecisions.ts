/**
 * TanStack Query hooks for the decisions domain (scrape-arbiter §4.1).
 *
 * Thin wrappers over the typed helpers in :mod:`@/api/decisions`.  Follows
 * the pattern established by {@link usePipelineStatus}: stable query keys
 * from {@link decisionsKeys}, ``useMutation`` hooks that invalidate the
 * relevant cache entries on success, and error surfaces as
 * :class:`ApiError`.
 */

import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";

import {
  type DecisionListItem,
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
import { pipelineKeys } from "@/api/pipeline";
import type { DecisionStatus } from "@/components/decisions/triggers";
import { pipelineStagesKeys } from "@/hooks/usePipelineStages";
import { stagingMediaKeys } from "@/hooks/useStagingMedia";

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

// ---------------------------------------------------------------------------
// Shared decision mutations (FRONTEND-DATA-06)
// ---------------------------------------------------------------------------
//
// resolve / dismiss / search-override used to live inline in three components
// (DecisionDetail, ResolutionDeck, and the Decisions page quick-dismiss) with
// divergent invalidation sets — a divergence the codebase documented (F12) then
// resolved in the wrong direction by deleting the hooks. These re-centralize the
// mutations with ONE invalidation set (the UNION of the divergent sets), while
// the per-surface toast copy, local state, via-computation (F09), completion
// poll (F19) and flip animation stay in the components via callbacks — so the
// ratified per-surface UX is untouched.

/** Variables for {@link useResolveDecision}: the decision id + chosen identity. */
export interface ResolveDecisionVars {
  /** Primary key of the ``scrape_decision`` row. */
  readonly id: number;
  /** The chosen provider identity + ``via`` provenance. */
  readonly body: ResolveRequest;
}

/** Per-surface callbacks for {@link useResolveDecision}. */
export interface ResolveDecisionCallbacks {
  /** Called after the invalidation set fires, with the 202 ``run_uid``. */
  readonly onResolved?: (data: ResolveResponse, vars: ResolveDecisionVars) => void;
  /** Called on failure (surface owns the toast / 409 / 410 handling). */
  readonly onError?: (error: unknown, vars: ResolveDecisionVars) => void;
}

/**
 * The UNION invalidation set fired after a decision resolve (FRONTEND-DATA-06).
 *
 * ResolutionDeck refreshed the Flow Board + staging grid so the operator SEES
 * the media advance and leave staging; DecisionDetail refreshed the decisions
 * list + pipeline history for its completion poll. The shared mutation fires the
 * union of both — more invalidation ≥ correctness — so neither surface can drift
 * to a narrower set. (Perf: on the /scraping page this refetches the staging
 * grid + Flow Board too; both are cheap read-model queries and already polling.)
 */
function invalidateAfterResolve(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
  void queryClient.invalidateQueries({ queryKey: pipelineKeys.history });
  void queryClient.invalidateQueries({ queryKey: pipelineStagesKeys.stages });
  void queryClient.invalidateQueries({ queryKey: stagingMediaKeys.all });
}

/**
 * Launch a targeted re-scrape for a decision (``resolve``), shared across the
 * detail panel and the resolution deck.
 *
 * On success the UNION invalidation set ({@link invalidateAfterResolve}) fires,
 * then the surface's ``onResolved`` runs (toast, run-tracking, flip animation).
 *
 * Args:
 *   callbacks: Per-surface success/error callbacks.
 *
 * Returns:
 *   The mutation result; call ``mutate({ id, body })``.
 */
export function useResolveDecision(
  callbacks: ResolveDecisionCallbacks = {},
): UseMutationResult<ResolveResponse, Error, ResolveDecisionVars> {
  const queryClient = useQueryClient();
  return useMutation<ResolveResponse, Error, ResolveDecisionVars>({
    mutationFn: (vars) => resolveDecision(vars.id, vars.body),
    onSuccess: (data, vars) => {
      invalidateAfterResolve(queryClient);
      callbacks.onResolved?.(data, vars);
    },
    onError: (error, vars) => {
      callbacks.onError?.(error, vars);
    },
  });
}

/** Per-surface callbacks for {@link useDismissDecision}. */
export interface DismissDecisionCallbacks {
  /** Called after the decisions list is invalidated. */
  readonly onDismissed?: (data: DecisionDetailResponse, id: number) => void;
  /** Called on failure (surface owns the toast / 409 / 410 handling). */
  readonly onError?: (error: unknown, id: number) => void;
  /** Called on settle (success or error) — e.g. to clear an in-flight flag. */
  readonly onSettled?: (id: number) => void;
}

/**
 * Dismiss a decision, shared across the detail panel, the deck and the list's
 * inline quick-dismiss.
 *
 * On success the decisions namespace is invalidated (the one common set), then
 * the surface's ``onDismissed`` runs. Error/settle handling is delegated to the
 * surface (each has its own 409/410 copy).
 *
 * Args:
 *   callbacks: Per-surface success/error/settle callbacks.
 *
 * Returns:
 *   The mutation result; call ``mutate(id)``.
 */
export function useDismissDecision(
  callbacks: DismissDecisionCallbacks = {},
): UseMutationResult<DecisionDetailResponse, Error, number> {
  const queryClient = useQueryClient();
  return useMutation<DecisionDetailResponse, Error, number>({
    mutationFn: (id) => dismissDecision(id),
    onSuccess: (data, id) => {
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
      callbacks.onDismissed?.(data, id);
    },
    onError: (error, id) => {
      callbacks.onError?.(error, id);
    },
    onSettled: (_data, _error, id) => {
      callbacks.onSettled?.(id);
    },
  });
}

/** Variables for {@link useSearchDecision}: the decision id + search body. */
export interface SearchDecisionVars {
  /** Primary key of the ``scrape_decision`` row. */
  readonly id: number;
  /** The search title + optional year. */
  readonly body: SearchRequest;
}

/** Per-surface callbacks for {@link useSearchDecision}. */
export interface SearchDecisionCallbacks {
  /** Called with the fresh candidate results. */
  readonly onResults?: (data: SearchResponse, vars: SearchDecisionVars) => void;
  /** Called on failure (surface owns the toast / 410 / 502 handling). */
  readonly onError?: (error: unknown, vars: SearchDecisionVars) => void;
}

/**
 * Search live providers for candidate matches (search-override), shared across
 * the detail panel and the deck.
 *
 * A search mutates no server state (the results are ephemeral, applied to local
 * component state), so there is NO invalidation — the surface's ``onResults``
 * owns the local update.
 *
 * Args:
 *   callbacks: Per-surface success/error callbacks.
 *
 * Returns:
 *   The mutation result; call ``mutate({ id, body })``.
 */
export function useSearchDecision(
  callbacks: SearchDecisionCallbacks = {},
): UseMutationResult<SearchResponse, Error, SearchDecisionVars> {
  return useMutation<SearchResponse, Error, SearchDecisionVars>({
    mutationFn: (vars) => searchDecisionCandidates(vars.id, vars.body),
    onSuccess: (data, vars) => {
      callbacks.onResults?.(data, vars);
    },
    onError: (error, vars) => {
      callbacks.onError?.(error, vars);
    },
  });
}
