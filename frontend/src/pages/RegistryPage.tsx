/**
 * Registry page — provider health dashboard (``/registry``, S6 reg-health).
 *
 * Renders one card per configured provider with live circuit-breaker state,
 * recent-failure count, last success/failure timestamps, and last call
 * latency.  The cards are invalidated live when any registry or circuit event
 * arrives on the WebSocket (R13 ref pattern — processes only new events, not
 * the whole ring on every render).
 *
 * A ``live: false`` provider has never emitted an event; its state is an
 * optimistic baseline.  The card renders with a subtle muted indicator
 * ("En attente de données live") and dimmed opacity.
 *
 * Reuses:
 * - {@link useRegistryStatus} TanStack Query hook
 * - {@link useEventStreamContext} for live circuit/registry events
 * - shadcn {@link Card}, {@link Badge}, {@link Skeleton}
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, type ReactElement } from "react";

import { registryKeys } from "@/api/registry";
import { useRegistryStatus } from "@/hooks/useRegistryStatus";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Event class names the panel listens for (DESIGN §3.4). */
const REGISTRY_EVENT_TYPES = new Set([
  "CircuitBreakerOpened",
  "CircuitBreakerClosed",
  "CircuitBreakerHalfOpened",
  "RegistryFanOutCompleted",
]);

/** Circuit-state → badge tone mapping. */
const CIRCUIT_TONE: Record<string, "success" | "danger" | "warning"> = {
  closed: "success",
  open: "danger",
  half_open: "warning",
};

/** Circuit-state → French label. */
const CIRCUIT_LABEL: Record<string, string> = {
  closed: "OK",
  open: "Ouvert",
  half_open: "Semi-ouvert",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format a Unix-epoch float as a relative-time string in French. */
function relativeTime(epoch: number | null | undefined): string {
  if (epoch == null) return "—";
  const diff = Date.now() - epoch * 1000;
  if (diff < 60_000) return "à l'instant";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `il y a ${String(mins)} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${String(hours)} h`;
  const days = Math.floor(hours / 24);
  return `il y a ${String(days)} j`;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RegistryPage(): ReactElement {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useRegistryStatus();
  const { events } = useEventStreamContext();

  // Invalidate the snapshot on any registry/circuit event, but only scan
  // events appended since the last render — not the whole ring every time
  // (AppShell R13 ref pattern, coherence study F13).
  const lastProcessedRef = useRef(0);
  useEffect(() => {
    const start = Math.min(lastProcessedRef.current, events.length);
    const fresh = events.slice(start);
    lastProcessedRef.current = events.length;
    const hasRegistryEvent = fresh.some((e) =>
      REGISTRY_EVENT_TYPES.has(e.type),
    );
    if (hasRegistryEvent) {
      void queryClient.invalidateQueries({ queryKey: registryKeys.status() });
    }
  }, [events, queryClient]);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-4 p-4">
        <h1 className="text-2xl font-bold">Registre des fournisseurs</h1>
        {Array.from({ length: 3 }).map((_, idx) => (
          <Skeleton key={`sk-${String(idx)}`} className="h-28 w-full" />
        ))}
      </div>
    );
  }

  // ── Error ────────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div className="p-4">
        <h1 className="text-2xl font-bold">Registre des fournisseurs</h1>
        <p className="mt-4 text-muted-foreground">
          Impossible de charger le statut :{" "}
          {error instanceof Error ? error.message : "Erreur inconnue"}
        </p>
      </div>
    );
  }

  const { providers } = data;

  // ── Empty state ──────────────────────────────────────────────────────────
  if (providers.length === 0) {
    return (
      <div className="p-4">
        <h1 className="text-2xl font-bold">Registre des fournisseurs</h1>
        <p className="mt-4 text-muted-foreground">
          Aucun fournisseur configuré.
        </p>
      </div>
    );
  }

  // ── Normal render ────────────────────────────────────────────────────────
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">Registre des fournisseurs</h1>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {providers.map((p) => (
          <Card
            key={p.provider_name}
            className={!p.live ? "opacity-60" : undefined}
          >
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-lg">{p.provider_name}</CardTitle>
              <Badge tone={CIRCUIT_TONE[p.circuit_state]}>
                {CIRCUIT_LABEL[p.circuit_state] ?? p.circuit_state}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              {!p.live && (
                <p className="text-muted-foreground">
                  En attente de données live
                </p>
              )}
              <p>Échecs récents : {p.failure_count_recent}</p>
              <p>Dernier succès : {relativeTime(p.last_success_at)}</p>
              <p>Dernier échec : {relativeTime(p.last_failure_at)}</p>
              <p>
                Latence :{" "}
                {p.last_latency_ms != null
                  ? `${p.last_latency_ms.toFixed(0)} ms`
                  : "—"}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
