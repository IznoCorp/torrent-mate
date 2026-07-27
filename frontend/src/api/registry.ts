/**
 * Typed API client helpers for the /api/registry REST endpoints
 * (reg-health, DESIGN §3.3).
 *
 * Every helper routes through {@link apiFetch} with schema-typed path
 * params (R15) — no raw fetch and no ``any``.  Response types are
 * inferred from the regenerated ``schema.d.ts`` so a backend signature
 * change breaks at compile time, not at runtime.
 */

import type { SuccessBody } from "./_schema-helpers";
import type { components, paths } from "./schema";
import { apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Re-export schema component types so the UI layer can import from one place.
// ---------------------------------------------------------------------------

/** A single provider's runtime status as returned by GET /api/registry/status. */
export type ProviderStatusItem = components["schemas"]["ProviderStatusItem"];

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/** Response body for ``GET /api/registry/status``. */
export type RegistryStatusResponse = SuccessBody<
  paths["/api/registry/status"]["get"]["responses"]
>;

// ---------------------------------------------------------------------------
// Stable TanStack Query keys
// ---------------------------------------------------------------------------

/**
 * Stable React-Query keys for the registry domain.
 *
 * Exported so mutations and the event-stream patch can invalidate the exact
 * same cache entries.  Follows the established ``decisionsKeys`` /
 * ``pipelineKeys`` / ``maintenanceKeys`` pattern.
 */
export const registryKeys = {
  /** Root registry key: ``['registry']``. */
  all: ["registry"] as const,

  /** Status query key: ``['registry', 'status']``. */
  status: () => ["registry", "status"] as const,
};

// ---------------------------------------------------------------------------
// Typed endpoint helpers
// ---------------------------------------------------------------------------

/**
 * Fetch the live status of every configured provider.
 *
 * Sends ``GET /api/registry/status`` through the typed {@link apiFetch}
 * (R15).  Read-only — no ``X-Requested-With`` header.
 *
 * Returns:
 *   A {@link RegistryStatusResponse} with a ``providers[]`` of
 *   {@link ProviderStatusItem}.
 */
export function fetchRegistryStatus(): Promise<RegistryStatusResponse> {
  return apiFetch("/api/registry/status", {
    method: "get",
  });
}
