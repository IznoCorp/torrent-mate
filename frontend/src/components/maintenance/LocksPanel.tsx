/**
 * LocksPanel — pipeline lock state, sentinels, and tmp-orphan monitoring.
 *
 * Polls ``GET /api/maintenance/locks`` every 10 s so a lock acquisition or
 * release is reflected promptly. Renders the main pipeline lock, the pause and
 * watcher-paused sentinels, and a count + expandable list of temporary orphan
 * entries found on disk.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useState, type ReactElement } from "react";

import { getLocks, type LocksResponse } from "@/api/client";
import type { components } from "@/api/schema";
import { StatusDot } from "@/components/ds/StatusDot";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { maintenanceKeys } from "@/hooks/useMaintenanceKeys";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LockState = components["schemas"]["LockState"];
type Sentinels = components["schemas"]["Sentinels"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Classify a lock's health from its held / stale / alive state.
 *
 * Args:
 *   lock: The lock state object from the API.
 *
 * Returns:
 *   ``"fail"`` when stale (lock file exists but PID is dead),
 *   ``"warn"`` when held by a live process, ``"ok"`` when not held.
 */
function lockStatus(lock: LockState): {
  readonly status: "done" | "warning" | "error";
  readonly label: string;
} {
  if (lock.stale) return { status: "error", label: "Verrou obsolète" };
  if (lock.held && lock.pid_alive)
    return {
      status: "warning",
      label: `Pris — PID ${String(lock.pid ?? "?")}`,
    };
  if (lock.held) return { status: "error", label: "Pris — PID mort" };
  return { status: "done", label: "Libre" };
}

/**
 * Format a duration in seconds as a human-readable French relative age.
 *
 * Args:
 *   ageS: Age in seconds, or null / undefined.
 *
 * Returns:
 *   A human-readable string like ``"12 min"`` or ``"—"`` when null.
 */
function humanAge(ageS: number | null | undefined): string {
  if (ageS == null) return "—";
  const s = Math.round(ageS);
  if (s < 60) return `${String(s)} s`;
  if (s < 3600) return `${String(Math.floor(s / 60))} min`;
  if (s < 86400) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${String(h)} h ${String(m).padStart(2, "0")} min`;
  }
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  return `${String(d)} j ${String(h)} h`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * LocksPanel — a card showing pipeline lock state, pause / watcher sentinels,
 * and a collapsible list of temporary orphan entries.
 *
 * Polls ``GET /api/maintenance/locks`` every 10 s for near-real-time lock
 * visibility.
 *
 * Returns:
 *   The locks card element.
 */
export function LocksPanel(): ReactElement {
  const { data, isLoading, isError }: UseQueryResult<LocksResponse> = useQuery({
    queryKey: maintenanceKeys.locks,
    queryFn: getLocks,
    // C25: while the background disk sweep is pending, poll quickly so the
    // orphans panel fills in as soon as it lands; back off to 10 s once ready.
    refetchInterval: (query) =>
      query.state.data?.sweep.status === "pending" ? 1_500 : 10_000,
    refetchOnWindowFocus: true,
  });

  const [orphansExpanded, setOrphansExpanded] = useState(false);

  const lock = data?.pipeline_lock;
  const sentinels: Sentinels | undefined = data?.sentinels;
  const sweep = data?.sweep;
  const sweepPending = sweep?.status === "pending";
  const orphans = sweep?.orphans ?? [];

  const lockInfo = lock != null ? lockStatus(lock) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Verrous</CardTitle>
        <CardDescription>Locks, sentinelles, orphelins</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isLoading && (
          <p className="text-sm text-muted-foreground">
            Chargement des verrous…
          </p>
        )}
        {isError && (
          <p className="text-sm text-muted-foreground">
            Erreur lors du chargement.
          </p>
        )}

        {!isLoading && !isError && lock != null && lockInfo != null && (
          <>
            {/* Pipeline lock */}
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Verrou du pipeline</span>
              <StatusDot status={lockInfo.status} label={lockInfo.label} />
            </div>

            {/* Sentinels */}
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Sentinelles
              </span>
              <div className="flex items-center justify-between">
                <span className="text-xs">Pause</span>
                <span className="text-xs text-muted-foreground">
                  {sentinels?.pause === true
                    ? `Activée — ${humanAge(sentinels.pause_age_s)}`
                    : "Inactive"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs">Watcher</span>
                <span className="text-xs text-muted-foreground">
                  {sentinels?.watcher_paused === true
                    ? `Désactivé — ${humanAge(sentinels.watcher_paused_age_s)}`
                    : "Actif"}
                </span>
              </div>
            </div>

            {/* Tmp orphans — the disk sweep runs in the background (C25): while
                it is pending only THIS panel shows a skeleton, the locks above
                are already live. */}
            <div className="flex flex-col gap-1">
              {sweepPending ? (
                <>
                  <span className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Orphelins tmp
                    <span className="normal-case text-muted-foreground/70">
                      analyse en cours…
                    </span>
                  </span>
                  <div className="rounded-md border border-border bg-muted/30 p-2">
                    <Skeleton className="h-4 w-full" />
                  </div>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      setOrphansExpanded((prev) => !prev);
                    }}
                    className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {orphansExpanded ? (
                      <ChevronUp className="size-3" aria-hidden="true" />
                    ) : (
                      <ChevronDown className="size-3" aria-hidden="true" />
                    )}
                    Orphelins tmp ({String(orphans.length)})
                  </button>

                  {orphansExpanded && (
                    <div className="max-h-40 overflow-y-auto rounded-md border border-border bg-muted/30 p-2">
                      {orphans.length === 0 ? (
                        <p className="text-xs text-muted-foreground">Aucun.</p>
                      ) : (
                        <ul className="flex flex-col gap-1">
                          {orphans.map((orphan) => (
                            <li
                              key={orphan.path}
                              className="text-xs text-muted-foreground"
                            >
                              <span className="font-mono">{orphan.path}</span>
                              <span className="ml-2">
                                — {humanAge(orphan.age_s)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
