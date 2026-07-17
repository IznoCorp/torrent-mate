/**
 * RunDetail — full-detail view for a single pipeline run.
 *
 * Part of TorrentMateUI pipe-control Phase 5 (run-history). Fetches the run
 * detail from ``GET /api/pipeline/history/{run_uid}`` via TanStack Query,
 * renders a header row with key metadata, the {@link PipelineStepper} in
 * READ-ONLY mode, and an error section when the run terminated abnormally.
 *
 * Displayed inline on the ``/maintenance`` page below the run-history tables
 * when a row in {@link RunHistoryTable} is clicked; the selection is
 * URL-addressable (``?run=<uid>``, DOIT-10). A "Retour" button calls
 * ``onClose`` (which clears the query param).
 */

import { useQuery } from "@tanstack/react-query";
import { Fragment, type ReactElement } from "react";

import {
  getPipelineRunDetail,
  pipelineKeys,
  type RunDetail as RunDetailData,
} from "@/api/pipeline";
import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { StalledPanel } from "@/components/pipeline/StalledPanel";
import { triggerLabel } from "@/components/pipeline/triggers";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate, formatDuration, runOutcomeInfo } from "@/lib/format";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/** Props for {@link RunDetail}. */
export interface RunDetailProps {
  /** The unique run identifier to fetch and display. */
  readonly runUid: string;
  /** Called when the user clicks the "Retour" button. */
  readonly onClose: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Options display helper
// ---------------------------------------------------------------------------

/**
 * Render the ``options_json`` payload for a maintenance run.
 *
 * Attempts ``JSON.parse`` defensively. On success with a plain object, renders
 * each key/value pair in a small two-column grid. On parse failure or a
 * non-object result, falls back to a ``<pre>`` block showing the raw or
 * stringified value.
 *
 * Args:
 *   raw: The raw JSON string from ``RunDetail.options_json``.
 *
 * Returns:
 *   A rendered representation of the options.
 */
function OptionsDisplay({ raw }: { readonly raw: string }): ReactElement {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      !Array.isArray(parsed)
    ) {
      const entries = Object.entries(parsed as Record<string, unknown>);
      if (entries.length === 0) {
        return <p className="text-xs text-muted-foreground">—</p>;
      }
      return (
        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          {entries.map(([key, value]) => (
            <Fragment key={key}>
              <span className="font-mono font-medium text-muted-foreground">
                {key}
              </span>
              <span className="font-mono">{String(value)}</span>
            </Fragment>
          ))}
        </div>
      );
    }
    // Fallback: render the parsed value as indented JSON.
    return (
      <pre className="font-mono text-xs">{JSON.stringify(parsed, null, 2)}</pre>
    );
  } catch {
    // Parse failure: show the raw string.
    return <pre className="font-mono text-xs">{raw}</pre>;
  }
}

/**
 * RunDetail — full detail for a single pipeline run.
 *
 * Fetches the run detail via ``getPipelineRunDetail`` and renders:
 *
 * - A header with the run UID, trigger, outcome Badge, duration, and start/end
 *   dates.
 * - For pipeline runs: the 9-stage {@link PipelineStepper} in READ-ONLY mode
 *   fed from ``RunDetail.steps``.
 * - For maintenance runs: the executed command, parsed options, and captured
 *   output tail.
 * - An error section (danger-styled {@link Card}) when ``error`` is present.
 * - A "Retour" button that calls ``onClose``.
 *
 * Args:
 *   runUid: The run identifier to fetch.
 *   onClose: Callback to dismiss the detail view.
 *
 * Returns:
 *   The run-detail element.
 */
/** French labels for maintenance-run counters (steps_json ``counts``). */
const MAINTENANCE_COUNT_LABELS: Record<string, string> = {
  detected: "Épisodes détectés",
  enqueued: "Mis en file",
  skipped_owned: "Déjà en médiathèque",
  skipped_dup: "Déjà en file",
  resurrected: "Réouverts",
  closed_owned: "Clôturés (en médiathèque)",
  requeued_missing: "Remis en file (torrent disparu)",
  grabbed: "Récupérés",
  retried: "À retenter",
  abandoned: "Abandonnés",
  skipped: "Ignorés",
  fixed: "Corrigés",
  errors: "Erreurs",
  artwork_recovered: "Posters récupérés",
};

/** Flatten a maintenance run's step counts into labelled non-zero rows. */
function maintenanceCountRows(
  steps: RunDetailData["steps"],
): [string, number][] {
  const rows: [string, number][] = [];
  for (const step of steps) {
    for (const [key, value] of Object.entries(step.counts ?? {})) {
      if (typeof value === "number" && value > 0) {
        rows.push([MAINTENANCE_COUNT_LABELS[key] ?? key, value]);
      }
    }
  }
  return rows;
}

/**
 * Describe a maintenance run's ``queue`` wait in plain French, if any (§6).
 *
 * The runner appends a ``queue`` step while it waits for ``pipeline.lock``
 * (status ``waiting_pipeline_lock``) and closes it (status ``done``) with the
 * true wait window when the lock frees. The LAST queue entry carries the
 * current truth.
 *
 * Args:
 *   steps: The run's persisted step entries.
 *   outcome: The run outcome (live wait only shows while ``running``).
 *
 * Returns:
 *   A French one-liner, or null when the run never queued.
 */
function queueWaitInfo(
  steps: RunDetailData["steps"],
  outcome: string | null | undefined,
): string | null {
  let last: RunDetailData["steps"][number] | null = null;
  for (const step of steps) {
    if (step.name === "queue") last = step;
  }
  if (last == null) return null;
  if (last.status === "waiting_pipeline_lock") {
    return outcome === "running"
      ? "En file d'attente — un autre run tient le verrou du pipeline ; démarrage automatique à sa libération."
      : null;
  }
  const waited = last.elapsed_s;
  if (waited == null || waited <= 0) return null;
  return `A patienté en file d'attente ${formatDuration(waited)} avant de démarrer (verrou pipeline occupé).`;
}

export function RunDetail({ runUid, onClose }: RunDetailProps): ReactElement {
  const { data, isLoading, isError } = useQuery({
    queryKey: pipelineKeys.historyDetail(runUid),
    queryFn: () => getPipelineRunDetail(runUid),
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-4 text-center text-xs text-muted-foreground">
          Chargement…
        </CardContent>
      </Card>
    );
  }

  if (isError || data === undefined) {
    return (
      <Card>
        <CardContent className="py-4 text-center text-xs text-muted-foreground">
          Erreur lors du chargement du détail.
        </CardContent>
      </Card>
    );
  }

  const maintenanceCounts =
    data.kind === "maintenance" ? maintenanceCountRows(data.steps) : [];
  const queueInfo =
    data.kind === "maintenance"
      ? queueWaitInfo(data.steps, data.outcome)
      : null;

  // §8 — per-step skip/defer/error reasons persisted from the StepReport,
  // grouped by step, so the operator sees WHY items did not advance. The
  // 'queue' waiting step is not a reason — it has its own banner above.
  const stepReasons = data.steps
    .filter((s) => s.name !== "queue" && (s.reasons?.length ?? 0) > 0)
    .map((s) => ({ step: s.name, reasons: s.reasons ?? [] }));

  const { tone, label } = runOutcomeInfo(data.outcome);

  return (
    <Card className="gap-4">
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex items-center gap-3">
          <CardTitle className="text-base">
            Exécution{" "}
            <span className="font-mono tabular-nums text-sm text-muted-foreground">
              {data.run_uid.slice(0, 8)}…
            </span>
          </CardTitle>
          <Badge tone={tone} dot>
            {label}
          </Badge>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-border px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          Retour
        </button>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {/* Metadata row */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-4">
          <div>
            <span className="text-muted-foreground">Déclencheur</span>
            <p className="font-medium">{triggerLabel(data.trigger)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Durée</span>
            <p className="font-mono tabular-nums font-medium">
              {formatDuration(data.duration_s)}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Début</span>
            <p className="font-mono tabular-nums font-medium">
              {formatDate(data.started_at)}
            </p>
          </div>
          <div>
            <span className="text-muted-foreground">Fin</span>
            <p className="font-mono tabular-nums font-medium">
              {data.ended_at != null ? formatDate(data.ended_at) : "—"}
            </p>
          </div>
        </div>

        {/* Maintenance section or Pipeline Stepper */}
        {data.kind === "maintenance" ? (
          <div className="flex flex-col gap-3">
            {/* Command */}
            {data.command != null && data.command !== "" && (
              <div>
                <span className="text-xs text-muted-foreground">Commande</span>
                <p className="font-mono text-sm font-medium">{data.command}</p>
              </div>
            )}
            {/* §6 visible queue — the wait for pipeline.lock is a state the
                operator sees (live) and an honest trace afterwards. */}
            {queueInfo != null && (
              <p className="rounded-md border border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
                {queueInfo}
              </p>
            )}
            {/* Numeric result (§1/§2) — the run's counts in plain French.
                Without this block a maintenance run showed no outcome at all
                (e.g. « Posters récupérés » sat invisible in steps_json). */}
            {maintenanceCounts.length > 0 && (
              <div>
                <span className="text-xs text-muted-foreground">Résultat</span>
                <ul className="mt-1 flex flex-col gap-0.5 text-sm">
                  {maintenanceCounts.map(([label, value]) => (
                    <li
                      key={label}
                      className="flex items-center justify-between gap-2 border-b border-border/60 py-1 last:border-b-0"
                    >
                      <span className="text-muted-foreground">{label}</span>
                      <span className="font-mono tabular-nums">{value}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {/* Options */}
            {data.options_json != null && data.options_json !== "" && (
              <div>
                <span className="text-xs text-muted-foreground">Options</span>
                <OptionsDisplay raw={data.options_json} />
              </div>
            )}
            {/* Output tail */}
            {data.output_tail != null && data.output_tail !== "" && (
              <div>
                <span className="text-xs text-muted-foreground">Sortie</span>
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 font-mono text-xs">
                  {data.output_tail}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <PipelineStepper steps={data.steps} />
        )}

        {/* §8 — « ce qui n'a pas avancé » extracted to StalledPanel (5.1). */}
        <StalledPanel stepReasons={stepReasons} />

        {/* Error section — danger-styled Card */}
        {data.error != null && data.error !== "" && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4">
            <p className="mb-1 text-xs font-semibold text-destructive">
              Erreur
            </p>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap font-mono text-xs text-destructive/90">
              {data.error}
            </pre>
          </div>
        )}

        {/* Durable log journal for PIPELINE runs — captured output_tail
            (universal run journal). Written by every invocation path (web,
            CLI steps, safety_net), so finished runs always have a log to
            show even without a live feed. Maintenance runs render their
            output in the dedicated section above. */}
        {data.kind !== "maintenance" &&
          data.output_tail != null &&
          data.output_tail !== "" && (
            <div className="rounded-lg border border-border bg-muted/30 p-4">
              <p className="mb-1 text-xs font-semibold text-muted-foreground">
                Journal
              </p>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs text-foreground/90">
                {data.output_tail}
              </pre>
            </div>
          )}
      </CardContent>
    </Card>
  );
}
