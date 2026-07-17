/**
 * CompactHealth — compact one-row-per-domain health summary for the Contrôle
 * dashboard.
 *
 * Reuses the same data hooks as {@link DisksPanel}, {@link IndexHealthPanel},
 * {@link HealthCard}, and the registry status endpoint — presentation-only
 * compaction, no new data paths.  Each row is a single line of text and a
 * {@link StatusDot}, with detail links to ``/maintenance`` or ``/registry``.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { ReactElement } from "react";

import { getDisks, getIndexHealth } from "@/api/client";
import type { DisksResponse, IndexHealthResponse } from "@/api/client";
import { StatusDot } from "@/components/ds/StatusDot";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { maintenanceKeys } from "@/hooks/useMaintenanceKeys";
import { useHealth } from "@/hooks/useHealth";
import { useRegistryStatus } from "@/hooks/useRegistryStatus";
import { formatGb } from "@/lib/format";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Read a loosely-typed health field as a strict boolean (``true`` only).
 *
 * Mirrors the same guard in {@link HealthCard}.
 */
function isOk(value: unknown): boolean {
  return value === true;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * CompactHealth — one compact row per domain: disks, index, Redis, providers.
 *
 * Returns:
 *   The compact-health card element.
 */
export function CompactHealth(): ReactElement {
  // ---- disks ----------------------------------------------------------------
  const disksQuery: UseQueryResult<DisksResponse> = useQuery({
    queryKey: maintenanceKeys.disks,
    queryFn: getDisks,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

  // ---- index ----------------------------------------------------------------
  const indexQuery: UseQueryResult<IndexHealthResponse> = useQuery({
    queryKey: maintenanceKeys.indexHealth,
    queryFn: getIndexHealth,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

  // ---- Redis (via useHealth) ------------------------------------------------
  const { data: healthData, isError: healthError } = useHealth();
  const redisOk = isOk(healthData?.redis);
  const healthChecking = healthData === undefined && !healthError;

  // ---- providers (registry) -------------------------------------------------
  const { data: registryData } = useRegistryStatus();
  const providers = registryData?.providers ?? [];
  const providersOk = providers.filter(
    (p) => p.circuit_state === "closed",
  ).length;
  const providersTotal = providers.length;

  // ---- Disks row ------------------------------------------------------------
  const disks = disksQuery.data?.disks ?? [];
  const disksLoading = disksQuery.isLoading;

  /** Build the disks summary fragment (e.g. "Disk 1 500 Go libre"). */
  function disksSummary(): ReactElement {
    if (disksLoading) {
      return <span className="text-sm text-muted-foreground">Chargement…</span>;
    }
    if (disks.length === 0) {
      return (
        <span className="text-sm text-muted-foreground">
          Aucun disque configuré.
        </span>
      );
    }
    const parts = disks.map((disk) => {
      const pct = disk.mounted ? Math.round(disk.used_pct) : 100;
      const barPct = Math.min(100, Math.max(0, pct));
      const barTone = !disk.mounted
        ? "bg-destructive"
        : pct >= 90
          ? "bg-warning"
          : "bg-success";
      const free = disk.mounted ? formatGb(disk.free_gb) : "—";

      return (
        <span key={disk.id} className="inline-flex items-center gap-1.5">
          <span className="text-sm font-medium">{disk.label}</span>
          {/* Mini inline capacity bar */}
          <span className="inline-block h-1.5 w-10 overflow-hidden rounded-full bg-muted align-middle">
            <span
              className={`inline-block h-full rounded-full ${barTone}`}
              style={{ width: `${String(barPct)}%` }}
            />
          </span>
          <span className="text-sm tabular-nums">{free} libre</span>
        </span>
      );
    });
    return <span className="flex flex-wrap gap-x-4 gap-y-1">{parts}</span>;
  }

  // ---- Index row ------------------------------------------------------------
  function indexDot(): ReactElement {
    if (indexQuery.isLoading) {
      return <StatusDot status="idle" label="Index — chargement…" />;
    }
    if (indexQuery.isError || indexQuery.data?.degraded) {
      return <StatusDot status="error" label="Index dégradé" />;
    }
    const items = indexQuery.data?.items ?? 0;
    return <StatusDot status="done" label={`${String(items)} items indexés`} />;
  }

  // ---- Redis row ------------------------------------------------------------
  function redisDot(): ReactElement {
    if (healthChecking) {
      return <StatusDot status="idle" label="Redis — vérification…" />;
    }
    if (redisOk) {
      return <StatusDot status="done" label="Redis en ligne" />;
    }
    return <StatusDot status="error" label="Redis hors ligne" />;
  }

  // ---- Providers row --------------------------------------------------------
  function providersDot(): ReactElement {
    if (providersTotal === 0) {
      return <StatusDot status="idle" label="Fournisseurs — aucun configuré" />;
    }
    if (providersOk === providersTotal) {
      return (
        <StatusDot
          status="done"
          label={`${String(providersOk)}/${String(providersTotal)} fournisseurs OK`}
        />
      );
    }
    return (
      <StatusDot
        status={providersOk === 0 ? "error" : "warning"}
        label={`${String(providersOk)}/${String(providersTotal)} fournisseurs OK`}
      />
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>Santé</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {/* Disks */}
        <div className="flex items-center justify-between gap-2">
          {disksSummary()}
          <Link
            to="/maintenance"
            className="shrink-0 text-xs font-medium text-primary hover:underline"
          >
            Détails →
          </Link>
        </div>

        {/* Index */}
        <div className="flex items-center justify-between gap-2">
          {indexDot()}
          <Link
            to="/maintenance"
            className="shrink-0 text-xs font-medium text-primary hover:underline"
          >
            Maintenance →
          </Link>
        </div>

        {/* Redis */}
        <div className="flex items-center justify-between gap-2">
          {redisDot()}
          <span className="shrink-0 text-xs text-muted-foreground">
            Flux temps réel
          </span>
        </div>

        {/* Providers */}
        <div className="flex items-center justify-between gap-2">
          {providersDot()}
          <Link
            to="/registry"
            className="shrink-0 text-xs font-medium text-primary hover:underline"
          >
            Registre →
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
