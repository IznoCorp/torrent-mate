/**
 * TanStack Query hooks for the acquisition surface (acq-watch feature).
 *
 * Four read hooks + three mutations, bound to the typed client in
 * ``@/api/acquisition``.  Query keys follow the established convention
 * (namespaced arrays, mirroring useMaintenanceKeys / useConfigKeys).
 */

import { useMutation, useQuery, useQueryClient, type UseQueryOptions, type UseQueryResult } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  acqKeys,
  createFollow,
  deleteFollow,
  getAcquisitionStatus,
  getCompleteness,
  getDownloads,
  getFollowed,
  getObligations,
  getOverview,
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
import { ApiError } from "@/api/client";
import { useRunToCompletion } from "@/hooks/useRunToCompletion";

/**
 * Toast a mutation failure in French, surfacing the backend detail when the
 * error is a typed {@link ApiError} (409/422/428 carry an operator-readable
 * ``detail``) — X3: no acquisition mutation may fail silently.
 *
 * Args:
 *   action: The French phrase naming the failed action (no trailing period).
 *   err: The error thrown by the mutation.
 */
function toastMutationError(action: string, err: unknown): void {
  if (err instanceof ApiError) {
    // The staging read-only guard already carries a clean French message;
    // any other ApiError surfaces the backend ``detail`` (409/422/428).
    toast.error(
      err.isReadOnly
        ? err.message
        : err.detail !== ""
          ? `${action} — ${err.detail}`
          : `${action}.`,
    );
  } else {
    toast.error(`${action}.`);
  }
}

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
 *       Omitted by most callers (the AcquireStatusBadge in the AppShell
 *       passes ``refetchInterval`` for live polling).
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

/** The « état de la machine » overview rollup (F5 capstone). */
export function useOverview() {
  return useQuery({
    queryKey: acqKeys.overview(),
    queryFn: getOverview,
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
    queryKey: acqKeys.trackedRun(runUid),
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
 * obligations panel all refresh.  Failures toast in French with the backend
 * detail (X3) — call sites add their own ``onSuccess`` wording but never a
 * second error toast.  The 409 duplicate-follow is the exception: refusing
 * the duplicate of the SAME action is the one legitimate refusal and toasts
 * as information, never as an error (NE-DOIT-PAS-3).
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
    onError: (err: unknown) => {
      // NE-DOIT-PAS-3: a 409 (already actively followed) is the duplicate of
      // the same action — an information, never a failure (same house rule as
      // useFollowedPanel's trigger/grab 409 handling).
      if (err instanceof ApiError && err.status === 409) {
        // The refusal itself proves the follow already exists server-side —
        // the local "not followed" view that allowed this submit is stale, so
        // resync the acquisition namespace just like a success would.
        void qc.invalidateQueries({ queryKey: acqKeys.all });
        toast.info("Déjà suivi — ce média est déjà dans les suivis.");
        return;
      }
      toastMutationError("Échec de l'ajout au suivi", err);
    },
  });
}

/**
 * Update a followed series (active flag / cadence).
 *
 * Sends ``PATCH /api/acquisition/followed/{followed_id}``.  On success
 * invalidates the entire acquisition query namespace; failures toast in
 * French with the backend detail (X3).
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
    onError: (err: unknown) => {
      // X3: a failed toggle/cadence edit silently snapped back before this.
      toastMutationError("Échec de la mise à jour du suivi", err);
    },
  });
}

/**
 * Soft-unfollow a series (sets active=False).
 *
 * Sends ``DELETE /api/acquisition/followed/{followed_id}``.  On success
 * invalidates the entire acquisition query namespace; failures toast in
 * French with the backend detail (X3).
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
    onError: (err: unknown) => {
      // X3: an unfollow that failed used to leave the row visibly unchanged
      // with no explanation.
      toastMutationError("Échec du retrait du suivi", err);
    },
  });
}
