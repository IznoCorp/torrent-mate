/**
 * WatcherPanel — the "Watcher" tab: enabled state + toggle and the recent
 * watcher-run table.
 *
 * Extracted from `AcquisitionPage.tsx` (C12). Behaviour unchanged.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactElement } from "react";

import { acqKeys } from "@/api/acquisition";
import { setWatcher } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAcquisitionStatus } from "@/hooks/useAcquisition";

import {
  formatDatetime,
  relativeTime,
  STATUS_LABEL,
  STATUS_TONE,
  truncate,
} from "./meta";

/**
 * WatcherPanel — watcher status card + recent-runs table.
 *
 * Returns:
 *   The watcher panel element.
 */
export function WatcherPanel(): ReactElement {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useAcquisitionStatus();

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => setWatcher({ enabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: acqKeys.status() });
    },
  });

  // ── Loading ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  // ── Error ──────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <p className="py-4 text-muted-foreground">
        Erreur de chargement :{" "}
        {error instanceof Error ? error.message : "Inconnue"}
      </p>
    );
  }

  const { watcher_enabled, last_successful_run_at, recent_runs } = data;

  // ── Normal ─────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Status card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-base">État du watcher</CardTitle>
          <Badge tone={watcher_enabled ? "success" : "neutral"}>
            {watcher_enabled ? "Activé" : "Désactivé"}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                Dernière exécution
              </p>
              <p className="text-sm font-medium">
                {last_successful_run_at != null
                  ? `${formatDatetime(last_successful_run_at)} (${relativeTime(last_successful_run_at)})`
                  : "Jamais"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Label htmlFor="watcher-toggle" className="text-xs">
                Activé
              </Label>
              <Switch
                id="watcher-toggle"
                checked={watcher_enabled}
                onCheckedChange={(checked) => {
                  toggleMutation.mutate(checked);
                }}
                disabled={toggleMutation.isPending}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recent runs */}
      <div>
        <h3 className="mb-2 text-sm font-semibold">
          Exécutions récentes du watcher
        </h3>
        {recent_runs.length === 0 ? (
          <p className="py-4 text-center text-muted-foreground">
            Aucune exécution récente enregistrée.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Run UID</TableHead>
                <TableHead>Démarré</TableHead>
                <TableHead>Terminé</TableHead>
                <TableHead>Résultat</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recent_runs.map((run) => (
                <TableRow key={run.run_uid}>
                  <TableCell className="font-mono text-xs">
                    {truncate(run.run_uid, 12)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {formatDatetime(run.started_at)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {formatDatetime(run.ended_at)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      tone={
                        run.outcome != null
                          ? (STATUS_TONE[run.outcome] ?? "neutral")
                          : "neutral"
                      }
                    >
                      {run.outcome != null
                        ? (STATUS_LABEL[run.outcome] ?? run.outcome)
                        : "—"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
