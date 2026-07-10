/**
 * TanStack Query hooks for the acquisition surface (acq-watch feature).
 *
 * Four read hooks + three mutations, bound to the typed client in
 * ``@/api/acquisition``.  Query keys follow the established convention
 * (namespaced arrays, mirroring useMaintenanceKeys / useConfigKeys).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  acqKeys,
  createFollow,
  deleteFollow,
  getAcquisitionStatus,
  getFollowed,
  getObligations,
  getWanted,
  updateFollow,
  type CreateFollowRequest,
  type FollowedParams,
  type ObligationsParams,
  type UpdateFollowRequest,
  type WantedParams,
} from "@/api/acquisition";

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
 * Fetch paginated wanted items.
 *
 * Query key: ``['acquisition', 'wanted', {status, page, page_size}]``.
 *
 * Args:
 *   params: Optional filter (``status``, ``page``, ``page_size``).  Defaults
 *       to ``{}`` which the backend interprets as status=all, page=1,
 *       page_size=50.
 *
 * Returns:
 *   The TanStack Query result for a {@link WantedResponse}.
 */
export function useWanted(params: WantedParams = {}) {
  return useQuery({
    queryKey: acqKeys.wanted(params),
    queryFn: () => getWanted(params),
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
