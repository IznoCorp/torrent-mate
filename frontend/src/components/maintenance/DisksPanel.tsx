/**
 * DisksPanel — storage disk mount status and capacity monitoring.
 *
 * Polls ``GET /api/maintenance/disks`` every 60 s and renders one row per
 * configured disk: a {@link StatPanel} with free / total capacity, a coloured
 * fill bar reflecting used space, and a {@link StatusDot} signalling
 * mount + free-space health.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { ReactElement } from "react";

import { getDisks, type DisksResponse } from "@/api/client";
import type { components } from "@/api/schema";
import { StatPanel } from "@/components/ds/StatPanel";
import { StatusDot } from "@/components/ds/StatusDot";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { maintenanceKeys } from "@/hooks/useMaintenanceKeys";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DiskInfo = components["schemas"]["DiskInfo"];

/** Health classification for a single disk. */
type DiskHealth = "ok" | "warn" | "fail";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Classify a disk's health from its mount state and free-space ratio.
 *
 * Args:
 *   disk: The disk info object from the API.
 *
 * Returns:
 *   ``"fail"`` when unmounted, ``"warn"`` when free space is ≤ 10 %, ``"ok"``
 *   otherwise.
 */
function diskHealth(disk: DiskInfo): DiskHealth {
  if (!disk.mounted) return "fail";
  if (disk.used_pct >= 90) return "warn";
  return "ok";
}

/**
 * Map a {@link DiskHealth} to a {@link StatusDot} status.
 *
 * Args:
 *   health: The classified disk health.
 *
 * Returns:
 *   The StatusDot status string.
 */
function healthToStatus(health: DiskHealth): "done" | "warning" | "error" {
  switch (health) {
    case "ok":
      return "done";
    case "warn":
      return "warning";
    case "fail":
      return "error";
  }
}

/**
 * Human-readable label for a disk health classification.
 *
 * Args:
 *   health: The classified disk health.
 *
 * Returns:
 *   A French label.
 */
function healthLabel(health: DiskHealth): string {
  switch (health) {
    case "ok":
      return "OK";
    case "warn":
      return "Espace faible";
    case "fail":
      return "Non monté";
  }
}

/**
 * Format a gibibyte value to one decimal, appending " Go".
 *
 * Args:
 *   gb: The value in gibibytes.
 *
 * Returns:
 *   A formatted string like ``"238.5 Go"``.
 */
function fmtGb(gb: number): string {
  return `${gb.toFixed(1)} Go`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * DisksPanel — a card listing every configured storage disk with its mount
 * status, free / total capacity, and a capacity bar.
 *
 * Polls ``GET /api/maintenance/disks`` every 60 s.
 *
 * Returns:
 *   The disks card element.
 */
export function DisksPanel(): ReactElement {
  const { data, isLoading, isError }: UseQueryResult<DisksResponse> = useQuery({
    queryKey: maintenanceKeys.disks,
    queryFn: getDisks,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

  const disks = data?.disks ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Disques</CardTitle>
        <CardDescription>Espace et statut de montage</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isLoading && (
          <p className="text-sm text-muted-foreground">
            Chargement des disques…
          </p>
        )}
        {isError && (
          <p className="text-sm text-muted-foreground">
            Erreur lors du chargement.
          </p>
        )}
        {!isLoading &&
          !isError &&
          disks.map((disk) => {
            const health = diskHealth(disk);
            const status = healthToStatus(health);
            const pct = disk.mounted ? Math.round(disk.used_pct) : 100;
            // Clamp for the fill bar visual.
            const barPct = Math.min(100, Math.max(0, pct));
            const barTone =
              health === "fail"
                ? "bg-destructive"
                : health === "warn"
                  ? "bg-warning"
                  : "bg-success";

            return (
              <div key={disk.id} className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{disk.label}</span>
                  <StatusDot status={status} label={healthLabel(health)} />
                </div>

                <StatPanel
                  value={disk.mounted ? fmtGb(disk.free_gb) : "—"}
                  unit={disk.mounted ? `libre / ${fmtGb(disk.total_gb)}` : undefined}
                />

                {/* Capacity fill bar */}
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full transition-all ${barTone}`}
                    style={{ width: `${String(barPct)}%` }}
                  />
                </div>
              </div>
            );
          })}
        {!isLoading && !isError && disks.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Aucun disque configuré.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
