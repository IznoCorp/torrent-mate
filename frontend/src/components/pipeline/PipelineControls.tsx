/**
 * PipelineControls — the action bar for the pipeline supervision page.
 *
 * Exposes the six actions from the ``/api/pipeline/*`` control routes as compact
 * icon buttons with confirmation dialogs where destructive, plus a Watcher toggle
 * Switch. Every mutation is backed by TanStack Query ``useMutation`` and
 * invalidates ``["pipeline", "status"]`` on success so the status card and
 * stepper pick up the new state.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Square } from "lucide-react";
import type { ReactElement } from "react";
import { useCallback, useState } from "react";

import {
  killPipeline,
  pausePipeline,
  resumePipeline,
  runPipeline,
  setWatcher,
} from "@/api/client";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";

/** The status shape from GET /api/pipeline/status. */
type StatusResponse = components["schemas"]["StatusResponse"];

/** Props for {@link PipelineControls}. */
interface PipelineControlsProps {
  /** Live pipeline status (refetched every 5 s by the page). */
  readonly status: StatusResponse;
}

/**
 * PipelineControls — Démarrer / Pause / Reprendre / Kill buttons + Watcher Switch.
 *
 * Args:
 *   status: The live pipeline status object.
 *
 * Returns:
 *   The controls element.
 */
export function PipelineControls({
  status,
}: PipelineControlsProps): ReactElement {
  const queryClient = useQueryClient();
  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["pipeline", "status"] }),
    [queryClient],
  );

  // ---- dialogs ----
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [showKillDialog, setShowKillDialog] = useState(false);

  // ---- mutations ----
  const runMutation = useMutation({
    mutationFn: () => runPipeline({ dry_run: dryRun }),
    onSuccess: () => {
      setShowRunDialog(false);
      void invalidate();
    },
  });

  const pauseMutation = useMutation({
    mutationFn: pausePipeline,
    onSuccess: invalidate,
  });

  const resumeMutation = useMutation({
    mutationFn: resumePipeline,
    onSuccess: invalidate,
  });

  const killMutation = useMutation({
    mutationFn: killPipeline,
    onSuccess: () => {
      setShowKillDialog(false);
      void invalidate();
    },
  });

  const watcherMutation = useMutation({
    mutationFn: (enabled: boolean) => setWatcher({ enabled }),
    onSuccess: invalidate,
  });

  // ---- derived state ----
  const isIdle = status.state === "idle";
  const isRunning = status.state === "running";
  const isPaused = status.state === "paused";

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {/* Démarrer */}
        <Button
          size="sm"
          disabled={!isIdle || runMutation.isPending}
          onClick={() => { setShowRunDialog(true); }}
        >
          <Play className="size-4" aria-hidden="true" />
          Démarrer
        </Button>

        {/* Pause */}
        <Button
          size="sm"
          variant="outline"
          disabled={!isRunning || pauseMutation.isPending}
          onClick={() => { pauseMutation.mutate(); }}
        >
          <Pause className="size-4" aria-hidden="true" />
          Pause
        </Button>

        {/* Reprendre */}
        <Button
          size="sm"
          variant="outline"
          disabled={!isPaused || resumeMutation.isPending}
          onClick={() => { resumeMutation.mutate(); }}
        >
          <Play className="size-4" aria-hidden="true" />
          Reprendre
        </Button>

        {/* Kill */}
        <Button
          size="sm"
          variant="destructive"
          disabled={(isIdle && !status.run_uid) || killMutation.isPending}
          onClick={() => { setShowKillDialog(true); }}
        >
          <Square className="size-4" aria-hidden="true" />
          Arrêter
        </Button>

        {/* Watcher toggle */}
        <label className="ml-auto flex items-center gap-2 text-sm">
          <Switch
            checked={status.watcher_enabled}
            onCheckedChange={(v) => { watcherMutation.mutate(v); }}
            disabled={watcherMutation.isPending}
            aria-label="Auto-trigger"
          />
          Auto-trigger
        </label>
      </div>

      {/* ---- Run confirmation dialog ---- */}
      <Dialog open={showRunDialog} onOpenChange={setShowRunDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Démarrer le pipeline</DialogTitle>
            <DialogDescription>
              Un nouveau pipeline va être lancé en arrière-plan.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center gap-3 py-2">
            <Switch
              checked={dryRun}
              onCheckedChange={setDryRun}
              tone="success"
              aria-label="Dry-run"
            />
            <span className="text-sm">Dry-run (simulation sans écriture)</span>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowRunDialog(false); }}>
              Annuler
            </Button>
            <Button
              onClick={() => { runMutation.mutate(); }}
              disabled={runMutation.isPending}
            >
              {runMutation.isPending ? "Lancement…" : "Démarrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- Kill confirmation dialog ---- */}
      <Dialog open={showKillDialog} onOpenChange={setShowKillDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Arrêter le pipeline ?</DialogTitle>
            <DialogDescription>
              Le processus en cours sera terminé immédiatement. Cette action est
              irréversible.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowKillDialog(false); }}>
              Annuler
            </Button>
            <Button
              variant="destructive"
              onClick={() => { killMutation.mutate(); }}
              disabled={killMutation.isPending}
            >
              {killMutation.isPending ? "Arrêt…" : "Arrêter"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
