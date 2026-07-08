/**
 * RunDetail — full-detail view for a single pipeline run.
 *
 * Part of TorrentMateUI pipe-control Phase 5 (run-history). Fetches the run
 * detail from ``GET /api/pipeline/history/{run_uid}`` via TanStack Query,
 * renders a header row with key metadata, the {@link PipelineStepper} in
 * READ-ONLY mode, and an error section when the run terminated abnormally.
 *
 * Displayed inline on the ``/pipeline`` page below the controls when a row
 * in {@link RunHistoryTable} is clicked. A "Retour" button calls ``onClose``.
 */

import { useQuery } from "@tanstack/react-query";
import { Fragment, type ReactElement } from "react";

import { getPipelineRunDetail } from "@/api/client";
import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// ---------------------------------------------------------------------------
// Outcome → Badge tone mapping
// ---------------------------------------------------------------------------

/** Maps an outcome string to a DS Badge tone + French label. */
const OUTCOME_BADGE: Record<
  string,
  { readonly tone: BadgeProps["tone"]; readonly label: string }
> = {
  success: { tone: "success", label: "Succès" },
  error: { tone: "danger", label: "Erreur" },
  killed: { tone: "warning", label: "Arrêté" },
  running: { tone: "info", label: "En cours" },
  paused: { tone: "info", label: "En pause" },
};

/** Default outcome info for null/unknown outcomes. */
const DEFAULT_OUTCOME = {
  tone: "neutral" as BadgeProps["tone"],
  label: "—",
};

/**
 * Look up the tone + label for a given outcome string.
 *
 * Args:
 *   outcome: The pipeline outcome, or null.
 *
 * Returns:
 *   A ``{tone, label}`` pair for the Badge.
 */
function outcomeInfo(outcome: string | null | undefined): {
  readonly tone: BadgeProps["tone"];
  readonly label: string;
} {
  if (outcome == null) return DEFAULT_OUTCOME;
  return OUTCOME_BADGE[outcome] ?? DEFAULT_OUTCOME;
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/**
 * Format an ISO 8601 UTC timestamp into a French-localised date string.
 *
 * Args:
 *   iso: The ISO 8601 UTC timestamp.
 *
 * Returns:
 *   A short date+time string formatted for the ``fr`` locale.
 */
function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("fr", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

/**
 * Format a duration in seconds to a compact ``Xm Ys`` or ``Ys`` string.
 *
 * Args:
 *   seconds: Duration in seconds, or null/undefined.
 *
 * Returns:
 *   A human-readable duration string, or ``"—"`` if null.
 */
function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${String(s)}s`;
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${String(mins)}m ${String(secs).padStart(2, "0")}s`;
}

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
        <div className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs">
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
export function RunDetail({ runUid, onClose }: RunDetailProps): ReactElement {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["pipeline", "history", runUid] as const,
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

  const { tone, label } = outcomeInfo(data.outcome);

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
            <p className="font-medium">{data.trigger}</p>
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
      </CardContent>
    </Card>
  );
}
