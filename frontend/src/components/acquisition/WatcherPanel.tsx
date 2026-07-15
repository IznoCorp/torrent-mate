/**
 * WatcherPanel — the "Watcher" tab: enabled state + toggle and the recent
 * watcher-run table.
 *
 * Extracted from `AcquisitionPage.tsx` (C12). Behaviour unchanged.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";
import { toast } from "sonner";

import { acqKeys, triggerDetect } from "@/api/acquisition";
import { ApiError, setWatcher } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import {
  useAcquisitionStatus,
  useTrackedAcquisitionRun,
} from "@/hooks/useAcquisition";

import {
  DEFERRED_REASON_LABEL,
  formatDatetime,
  formatRunResult,
  relativeTime,
  RUN_OUTCOME_LABEL,
  RUN_OUTCOME_TONE,
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

  // §5 manual detect trigger. Fire → track the run to its NUMERIC result; the
  // success toast fires only when the run actually ends (never on the 202).
  const [trackedRun, setTrackedRun] = useState<string | null>(null);
  const finishedRun = useTrackedAcquisitionRun(trackedRun);
  if (finishedRun?.ended_at != null && trackedRun != null) {
    if (finishedRun.outcome === "success") {
      const summary = formatRunResult(finishedRun.result);
      toast.success(`Détection terminée${summary ? ` — ${summary}` : ""}.`);
    } else {
      toast.error("La détection a échoué — voir les exécutions récentes.");
    }
    setTrackedRun(null);
    void queryClient.invalidateQueries({ queryKey: acqKeys.all });
  }

  const detectMutation = useMutation({
    mutationFn: () => triggerDetect(),
    onSuccess: (res) => {
      toast.info("Détection lancée…");
      setTrackedRun(res.run_uid);
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("Une détection est déjà en cours.");
      } else {
        toast.error("Impossible de lancer la détection.");
      }
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

  const { watcher_enabled, last_successful_run_at, recent_runs, deferred } =
    data;

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
          {/* Stacks below sm: at 390px the controls group (~260px) cannot share
              a row with the date without overflowing/overlapping it. */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-sm text-muted-foreground">
                Dernière exécution
              </p>
              <p className="text-sm font-medium">
                {last_successful_run_at != null
                  ? `${formatDatetime(last_successful_run_at)} (${relativeTime(last_successful_run_at)})`
                  : "Jamais"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                size="sm"
                onClick={() => {
                  detectMutation.mutate();
                }}
                disabled={detectMutation.isPending || trackedRun != null}
              >
                {trackedRun != null
                  ? "Détection en cours…"
                  : "Détecter maintenant"}
              </Button>
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
          </div>
          {/* §1 — transiently-deferred torrents stay VISIBLE: without this
              line a ratio/space/content skip is an invisible state (the
              watcher silently stops firing for them). */}
          {deferred.length > 0 && (
            <div className="rounded-md border border-border bg-muted/40 p-2">
              <p className="text-xs font-medium">
                {deferred.length} torrent{deferred.length > 1 ? "s" : ""} en
                attente d'ingestion
              </p>
              <ul className="mt-1 space-y-0.5">
                {deferred.map((d) => (
                  <li
                    key={`${d.name}-${d.reason}`}
                    className="text-xs text-muted-foreground break-words"
                  >
                    {d.name} — {DEFERRED_REASON_LABEL[d.reason] ?? d.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent runs */}
      <div>
        <h3 className="mb-2 text-sm font-semibold">Exécutions récentes</h3>
        {recent_runs.length === 0 ? (
          <p className="py-4 text-center text-muted-foreground">
            Aucune exécution récente enregistrée.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Démarré</TableHead>
                <TableHead>Résultat</TableHead>
                <TableHead>État</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recent_runs.map((run) => {
                const label =
                  run.command === "follow-detect"
                    ? "Détection"
                    : run.command === "grab"
                      ? "Récupération"
                      : "Pipeline";
                const numeric = formatRunResult(run.result);
                const pending = run.ended_at == null;
                return (
                  <TableRow key={run.run_uid}>
                    <TableCell className="text-xs font-medium">
                      {label}
                    </TableCell>
                    <TableCell className="text-xs">
                      {formatDatetime(run.started_at)}{" "}
                      <span className="text-muted-foreground">
                        ({relativeTime(run.started_at)})
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">
                      {numeric || (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {pending ? (
                        <Badge tone="info">En cours…</Badge>
                      ) : (
                        <Badge
                          tone={
                            run.outcome != null
                              ? (RUN_OUTCOME_TONE[run.outcome] ?? "neutral")
                              : "neutral"
                          }
                        >
                          {run.outcome != null
                            ? (RUN_OUTCOME_LABEL[run.outcome] ?? run.outcome)
                            : "—"}
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
