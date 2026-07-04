/**
 * Dashboard telemetry hooks for TorrentMateUI (tm-shell §5.3).
 *
 * Thin TanStack Query wrappers over the typed API client (``@/api/client``) for
 * the two read-only status endpoints the dashboard cards surface:
 *
 * - {@link useHealth} — ``GET /api/health`` (Redis + DB reachability), polled on
 *   a 30 s interval so a Redis outage shows up promptly as a degraded banner.
 * - {@link useVersion} — ``GET /api/version`` (package version + build commit),
 *   effectively immutable for the life of the tab (``staleTime: Infinity``).
 *
 * Both queries are typed straight off the OpenAPI schema — no ``any`` crosses the
 * boundary; consumers narrow the loosely-typed payload fields themselves.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getHealth, getVersion } from "@/api/client";

/** Health probe interval, in ms — a Redis/DB drop surfaces within one window. */
const HEALTH_REFETCH_MS = 30_000;

/** The ``GET /api/health`` payload shape (``{status, redis, db}``, loosely typed). */
export type HealthStatus = Awaited<ReturnType<typeof getHealth>>;

/** The ``GET /api/version`` payload shape (``{version, build_commit}``). */
export type VersionInfo = Awaited<ReturnType<typeof getVersion>>;

/**
 * Stable React-Query keys for the dashboard telemetry domain.
 *
 * Exported so tests and any future consumer read/invalidate the exact same
 * cache entries as the cards.
 */
export const telemetryKeys = {
  /** Health query key: ``['health']``. */
  health: ["health"] as const,
  /** Version query key: ``['version']``. */
  version: ["version"] as const,
};

/**
 * Poll the backend health probe (``GET /api/health``).
 *
 * Refetches every {@link HEALTH_REFETCH_MS} so a Redis outage or missing DB is
 * reflected in the health card without a manual reload. ``retry: false`` keeps a
 * transient failure honest — a failed probe *is* the signal the card renders.
 *
 * Returns:
 *   The query result; ``data`` carries ``{status, redis, db}`` when reachable,
 *   ``error`` an :class:`ApiError` when the probe itself failed.
 */
export function useHealth(): UseQueryResult<HealthStatus> {
  return useQuery({
    queryKey: telemetryKeys.health,
    queryFn: getHealth,
    refetchInterval: HEALTH_REFETCH_MS,
    retry: false,
  });
}

/**
 * Read the deployed version + build commit (``GET /api/version``).
 *
 * The version is fixed for the tab's lifetime, so ``staleTime: Infinity`` avoids
 * any refetch; a genuinely new server build is detected live through the event
 * stream's ``build_commit`` (see {@link VersionCard}), not by polling here.
 *
 * Returns:
 *   The query result; ``data`` carries ``{version, build_commit}``.
 */
export function useVersion(): UseQueryResult<VersionInfo> {
  return useQuery({
    queryKey: telemetryKeys.version,
    queryFn: getVersion,
    staleTime: Number.POSITIVE_INFINITY,
  });
}
