/**
 * TanStack Query hook for the scheduler overview (webui-ux Phase 5).
 *
 * Reads ``GET /api/maintenance/schedulers`` — the watcher plus each static cron
 * job with its last-run — for the Dashboard "Planificateurs" panel. Read-only;
 * polls at the same 60 s cadence as the other maintenance panels.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getSchedulers, type SchedulersResponse } from "@/api/client";
import { maintenanceKeys } from "@/hooks/useMaintenanceKeys";

/**
 * Fetch the scheduler overview (watcher + cron jobs).
 *
 * Query key: ``['maintenance', 'schedulers']``. Refetches every 60 s so a
 * recent cron/watcher run surfaces without a manual reload.
 *
 * Returns:
 *   The TanStack Query result for a {@link SchedulersResponse}.
 */
export function useSchedulers(): UseQueryResult<SchedulersResponse> {
  return useQuery({
    queryKey: maintenanceKeys.schedulers,
    queryFn: getSchedulers,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}
