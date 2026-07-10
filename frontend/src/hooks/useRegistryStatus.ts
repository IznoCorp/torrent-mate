/**
 * TanStack Query hook for the registry status domain (reg-health §3.4).
 *
 * Thin wrapper over the typed helper in :mod:`@/api/registry`.  Follows
 * the pattern established by {@link useDecisions}: stable query keys from
 * {@link registryKeys}, a single ``useQuery`` hook.
 */

import { useQuery } from "@tanstack/react-query";

import {
  type RegistryStatusResponse,
  fetchRegistryStatus,
  registryKeys,
} from "@/api/registry";

/**
 * Fetch the live registry status snapshot.
 *
 * Query key: ``['registry', 'status']``.
 *
 * Returns:
 *   The TanStack Query result for a {@link RegistryStatusResponse}.
 */
export function useRegistryStatus() {
  return useQuery<RegistryStatusResponse>({
    queryKey: registryKeys.status(),
    queryFn: () => fetchRegistryStatus(),
  });
}
