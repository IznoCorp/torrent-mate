/**
 * TanStack Query hooks for the acquisition surface (acq-watch feature).
 *
 * Four read hooks + three mutations, bound to the typed client in
 * ``@/api/acquisition``.  Query keys follow the established convention
 * (namespaced arrays, mirroring useMaintenanceKeys / useConfigKeys).
 */

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useState } from "react";
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
  getJourneys,
  getToHandle,
  getWanted,
  grabSeason,
  searchMedia,
  triggerFollowedSearch,
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
import { formatRunResult } from "@/components/acquisition/meta";
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
export function useFollowed(
  params: FollowedParams = {},
  options: { refetchInterval?: number; staleTime?: number } = {},
) {
  return useQuery({
    queryKey: acqKeys.followed(params),
    queryFn: () => getFollowed(params),
    ...options,
  });
}

/**
 * Rows fetched per search page. Large enough that the carousel has somewhere to
 * scroll before the next request lands, small enough not to stall on providers.
 * Paging is cheap since the backend caches the ranked lot per (query, kind), so
 * every page after the first costs no provider call at all.
 */
export const SEARCH_PAGE_SIZE = 30;

/**
 * How long a search result set stays fresh in the client cache.
 *
 * Matches the backend's own lot TTL: re-running a search the operator just ran —
 * clearing the box and retyping, or coming back to the tab — should be instant
 * rather than a second full round-trip. The global default is 5 s, which is far
 * too short for a provider-backed search.
 */
const SEARCH_STALE_MS = 5 * 60 * 1000;

/**
 * Search live providers for media to follow (add-by-search, OBJ3).
 *
 * Paginated: the operator can walk the whole ranked list instead of the first
 * few rows. Disabled until ``q`` is non-empty so no request fires on an empty box.
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
  return useInfiniteQuery({
    queryKey: acqKeys.search(params),
    queryFn: ({ pageParam }) =>
      searchMedia({ ...params, offset: pageParam, limit: SEARCH_PAGE_SIZE }),
    initialPageParam: 0,
    // The backend reports the TOTAL number of ranked candidates, not the page
    // size, so "is there more" is an arithmetic fact rather than a guess based
    // on whether the last page came back full.
    getNextPageParam: (lastPage) => {
      const seen = lastPage.offset + lastPage.results.length;
      return seen < lastPage.total ? seen : undefined;
    },
    staleTime: SEARCH_STALE_MS,
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

/** « À traiter » — les bloqués portés par une acquisition (§14.3). */
export function useToHandle() {
  return useQuery({
    queryKey: acqKeys.toHandle(),
    queryFn: getToHandle,
    refetchInterval: 60_000,
  });
}

/** « Parcours » — chaque acquisition tracée du grab au rangement (F1). */
export function useJourneys() {
  return useQuery({
    queryKey: acqKeys.journeys(),
    queryFn: getJourneys,
    refetchInterval: 60_000,
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
 * « What awaits the operator » — ONE derivation (§13).
 *
 * The nav badge and the « Maintenant » tab badge answer the same question and
 * must read the same computation: takeable follows + blocked items. An
 * in-flight item awaits nothing from the operator and is not counted. When
 * EITHER source fails — or the server admits a degraded read — the total is
 * unknowable and ``unknown`` is true: showing the half we have would
 * under-count what needs attention.
 *
 * Returns:
 *   ``{ count, unknown }``.
 */
export function useWaitingForOperator(): {
  count: number;
  unknown: boolean;
} {
  const followed = useFollowed({}, { refetchInterval: 60_000, staleTime: 55_000 });
  const toHandle = useToHandle();
  const takeable = (followed.data?.items ?? []).filter(
    (i) => i.status === "a_recuperer",
  ).length;
  const blocked = toHandle.data?.items.length ?? 0;
  return {
    count: takeable + blocked,
    unknown:
      followed.isError || toHandle.isError || (toHandle.data?.degraded ?? false),
  };
}

/**
 * Launch the full search chain for one followed series and TRACK the run.
 *
 * Fire-and-track, not fire-and-forget: the 202 only means « launched », so the
 * launch toast says what runs; the run is then tracked to its real end and the
 * closing toast carries the NUMERIC result — an action whose outcome never
 * comes back reads as an action that did nothing (§8).
 *
 * Returns:
 *   The mutation; call ``mutate(followedId)``.
 */
export function useGrabNow() {
  const qc = useQueryClient();
  const [trackedRun, setTrackedRun] = useState<string | null>(null);
  const finishedRun = useTrackedAcquisitionRun(trackedRun);
  if (finishedRun?.ended_at != null && trackedRun != null) {
    if (finishedRun.outcome === "success") {
      const summary = formatRunResult(finishedRun.result);
      toast.success(`Exécution terminée${summary ? ` — ${summary}` : ""}.`);
    } else {
      toast.error("L'exécution a échoué — voir les exécutions récentes.");
    }
    setTrackedRun(null);
    void qc.invalidateQueries({ queryKey: acqKeys.all });
  }

  return useMutation({
    mutationFn: (id: number) => triggerFollowedSearch(id),
    onSuccess: (res) => {
      // The chain runs server-side end to end — say so, then follow the run.
      toast.info("Vérification lancée — catalogue, trackers, puis récupération…");
      setTrackedRun(res.run_uid);
      void qc.invalidateQueries({ queryKey: acqKeys.all });
    },
    onError: (err: unknown) => {
      toastMutationError("Échec du lancement de la recherche", err);
    },
  });
}


/**
 * Manually enqueue one season of a followed series (idempotent server-side).
 *
 * Returns:
 *   The mutation; call ``mutate({ id, season })``.
 */
export function useGrabSeason() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, season }: { id: number; season: number }) =>
      grabSeason(id, season),
    onSuccess: () => {
      toast.info("Saison mise en file de recherche.");
      void qc.invalidateQueries({ queryKey: acqKeys.all });
    },
    onError: (err: unknown) => {
      toastMutationError("Échec de la mise en file de la saison", err);
    },
  });
}

/**
 * Update a followed series (active flag / cadence).
 *
 * Sends ``PATCH /api/acquisition/followed/{followed_id}``. On success
 * invalidates the acquisition namespace; failures toast in French with the
 * backend detail (X3).
 *
 * Returns:
 *   The mutation result; call ``mutate({id, body})``.
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
