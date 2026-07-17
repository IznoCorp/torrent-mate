/**
 * TanStack Query hooks for the acquisition surface (acq-watch feature).
 *
 * Four read hooks + three mutations, bound to the typed client in
 * ``@/api/acquisition``.  Query keys follow the established convention
 * (namespaced arrays, mirroring useMaintenanceKeys / useConfigKeys).
 */

import { useMutation, useQuery, useQueryClient, type UseQueryOptions, type UseQueryResult } from "@tanstack/react-query";

import {
  acqKeys,
  createFollow,
  deleteFollow,
  getAcquisitionStatus,
  getCompleteness,
  getDownloads,
  getFollowed,
  getObligations,
  getWanted,
  searchMedia,
  updateFollow,
  type AcquisitionStatusResponse,
  type CreateFollowRequest,
  type FollowedParams,
  type MediaSearchParams,
  type ObligationsParams,
  type UpdateFollowRequest,
  type WantedParams,
  type WantedResponse,
} from "@/api/acquisition";
import { useRunToCompletion } from "@/hooks/useRunToCompletion";

// ---------------------------------------------------------------------------
// Read hooks
// ---------------------------------------------------------------------------

/**
 * Fetch the followed series list.
 *
 * Query key: ``['acquisition', 'followed', {active}]``.
 *
 * Args:
 *   params: Optional filter (``active``: ``"active"``, ``"all"``, or
 *       ``"inactive"``).  Defaults to ``{}`` which the backend interprets
 *       as ``active="active"``.
 *
 * Returns:
 *   The TanStack Query result for a {@link FollowedResponse}.
 */
export function useFollowed(params: FollowedParams = {}) {
  return useQuery({
    queryKey: acqKeys.followed(params),
    queryFn: () => getFollowed(params),
  });
}

/**
 * Search live providers for media to follow (add-by-search, OBJ3).
 *
 * Disabled until ``q`` is non-empty so no request fires on an empty box.
 * Query key: ``['acquisition', 'search', {q, kind}]``.
 *
 * Args:
 *   q: The title to search for.
 *   kind: Optional ``"movie"``/``"tv"`` restriction.
 *
 * Returns:
 *   The TanStack Query result for a {@link MediaSearchResponse}.
 */
export function useMediaSearch(q: string, kind?: "movie" | "tv") {
  const trimmed = q.trim();
  const params: MediaSearchParams =
    kind != null ? { q: trimmed, kind } : { q: trimmed };
  return useQuery({
    queryKey: acqKeys.search(params),
    queryFn: () => searchMedia(params),
    enabled: trimmed.length > 0,
  });
}

/**
 * Fetch paginated wanted items.
 *
 * Query key: ``['acquisition', 'wanted', {status, page, page_size}]``.
 *
 * Args:
 *   params: Optional filter (``status``, ``page``, ``page_size``).  Defaults
 *       to ``{}`` which the backend interprets as status=all, page=1,
 *       page_size=50.
 *   queryOptions: Optional ``refetchInterval`` / ``staleTime`` overrides.
 *       Omitted by existing callers (the default React Query behaviour —
 *       cache-while-stale, no polling).
 *
 * Returns:
 *   The TanStack Query result for a {@link WantedResponse}.
 */
export function useWanted(
  params: WantedParams = {},
  queryOptions?: Partial<
    Pick<UseQueryOptions<WantedResponse>, "refetchInterval" | "staleTime">
  >,
): UseQueryResult<WantedResponse> {
  return useQuery({
    queryKey: acqKeys.wanted(params),
    queryFn: () => getWanted(params),
    ...queryOptions,
  });
}

/**
 * Fetch seed obligations with ratio state.
 *
 * Query key: ``['acquisition', 'obligations', {status}]``.
 *
 * Args:
 *   params: Optional filter (``status``: ``"all"``, ``"pending"``,
 *       ``"breached"``, or ``"satisfied"``).  Defaults to ``{}`` which the
 *       backend interprets as ``status="all"``.
 *
 * Returns:
 *   The TanStack Query result for an {@link ObligationsResponse}.
 */
export function useObligations(params: ObligationsParams = {}) {
  return useQuery({
    queryKey: acqKeys.obligations(params),
    queryFn: () => getObligations(params),
  });
}

/**
 * Fetch acquisition status (watcher state + recent runs).
 *
 * Query key: ``['acquisition', 'status']``.
 *
 * Returns:
 *   The TanStack Query result for an {@link AcquisitionStatusResponse}.
 */
export function useAcquisitionStatus() {
  return useQuery({
    queryKey: acqKeys.status(),
    queryFn: getAcquisitionStatus,
  });
}

/**
 * Poll the live progress of every grabbed torrent (A4).
 *
 * Query key: ``['acquisition', 'downloads']``. Refetches every 3 s so a
 * download's progress bar advances in near-real-time; the server side is
 * fail-soft (``client_available=false`` on a torrent-client outage).
 *
 * Returns:
 *   The TanStack Query result for an {@link AcquisitionDownloadsResponse}.
 */
export function useDownloads() {
  return useQuery({
    queryKey: acqKeys.downloads(),
    queryFn: getDownloads,
    refetchInterval: 3_000,
  });
}

/**
 * Fetch the §5 completeness matrix for one followed series (lazy).
 *
 * Query key: ``['acquisition', 'completeness', id]``. Disabled until
 * ``enabled`` is true (the accordion opens) — the endpoint hits the provider
 * catalog, so it must never fire for every card eagerly.
 *
 * Args:
 *   id: The ``followed_series`` rowid.
 *   enabled: Whether the query may fire.
 *
 * Returns:
 *   The TanStack Query result for a {@link CompletenessResponse}.
 */
export function useCompleteness(id: number, enabled: boolean) {
  return useQuery({
    queryKey: acqKeys.completeness(id),
    queryFn: () => getCompleteness(id),
    enabled,
    staleTime: 60_000,
  });
}

/**
 * Track a launched acquisition run to its §5 numeric result.
 *
 * Polls ``GET /api/acquisition/status`` every 2 s while *runUid* is set and
 * its run has not ended; stops polling once ``ended_at`` lands. The caller
 * watches the returned run entry to toast the real result — never a blind
 * success toast on the 202 (§5: « un toast de succès sur un run mort est
 * interdit »).
 *
 * Args:
 *   runUid: The launched run's identifier, or ``null`` when idle.
 *
 * Returns:
 *   The tracked run entry (or ``undefined`` while unknown).
 */
export function useTrackedAcquisitionRun(runUid: string | null) {
  // The shared launch-202 → poll → terminal machine. Terminal is per-run:
  // this surface polls the acquisition status list and watches the tracked
  // run's ``ended_at`` (not a pipeline-run ``outcome``).
  const query = useRunToCompletion<AcquisitionStatusResponse>({
    queryKey: [...acqKeys.status(), "tracked", runUid],
    queryFn: getAcquisitionStatus,
    enabled: runUid != null,
    intervalMs: 2000,
    isTerminal: (data) => {
      const run = data?.recent_runs.find((r) => r.run_uid === runUid);
      return run?.ended_at != null;
    },
  });
  return runUid == null
    ? undefined
    : query.data?.recent_runs.find((r) => r.run_uid === runUid);
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

/**
 * Follow (or reactivate) a series.
 *
 * Sends ``POST /api/acquisition/followed``.  On success invalidates the
 * entire acquisition query namespace so the followed list, wanted queue, and
 * obligations panel all refresh.
 *
 * Returns:
 *   The mutation result; call ``mutateAsync(body)`` from a form.
 */
export function useFollow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateFollowRequest) => createFollow(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: acqKeys.all });
    },
  });
}

/**
 * Update a followed series (active flag / cadence).
 *
 * Sends ``PATCH /api/acquisition/followed/{followed_id}``.  On success
 * invalidates the entire acquisition query namespace.
 *
 * Args:
 *   (none — pass ``{id, body}`` to ``mutateAsync``)
 *
 * Returns:
 *   The mutation result; call ``mutateAsync({id, body})`` from a toggle or
 *   cadence form.
 */
export function useUpdateFollow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: UpdateFollowRequest }) =>
      updateFollow(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: acqKeys.all });
    },
  });
}

/**
 * Soft-unfollow a series (sets active=False).
 *
 * Sends ``DELETE /api/acquisition/followed/{followed_id}``.  On success
 * invalidates the entire acquisition query namespace.
 *
 * Returns:
 *   The mutation result; call ``mutateAsync(id)`` with the followed row id.
 */
export function useUnfollow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteFollow(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: acqKeys.all });
    },
  });
}
