/**
 * Stable TanStack Query keys for the maintenance domain (S3 — maint-dash).
 *
 * Exported so panels and tests read / invalidate the exact same cache entries.
 */

export const maintenanceKeys = {
  disks: ["maintenance", "disks"] as const,
  locks: ["maintenance", "locks"] as const,
  indexHealth: ["maintenance", "index-health"] as const,
};
