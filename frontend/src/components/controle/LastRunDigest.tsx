/**
 * LastRunDigest — one-card digest of the most recent pipeline run.
 *
 * Renders the trigger label, relative age, a compact counts summary, and a
 * link to ``/pipeline?run=<uid>``.  When there is no run history the card
 * shows a calm empty state.
 */

import { Link } from "react-router-dom";
import type { ReactElement } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { triggerLabel, triggerTone } from "@/components/pipeline/triggers";
import type { LastPipelineRun } from "@/hooks/useLastPipelineRun";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Format an ISO 8601 UTC timestamp as a relative-time string in French.
 *
 * Args:
 *   iso: The ISO 8601 string, or ``null``.
 *
 * Returns:
 *   A human-readable relative age (e.g. ``"il y a 3 min"``), or ``"—"`` when
 *   the timestamp is absent.
 */
function relativeTime(iso: string | null): string {
  if (iso == null) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return "à l'instant";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `il y a ${String(mins)} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${String(hours)} h`;
  const days = Math.floor(hours / 24);
  return `il y a ${String(days)} j`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Props for {@link LastRunDigest}.
 *
 * Receives the full {@link LastPipelineRun} from the parent so the card can
 * remain a pure renderer — no data fetching of its own.
 */
export interface LastRunDigestProps {
  /** The last run's interpreted summary.  {@link useLastPipelineRun} never
   * returns ``null`` — when there is no history ``runUid`` is ``null`` and the
   * component renders a calm empty-state card. */
  readonly lastRun: LastPipelineRun | null;
}

/**
 * LastRunDigest — a compact card showing the trigger, age, counts, and a
 * detail link for the most recent pipeline run.
 *
 * Args:
 *   lastRun: The hook result from {@link useLastPipelineRun}.
 *
 * Returns:
 *   The digest card element.
 */
export function LastRunDigest({ lastRun }: LastRunDigestProps): ReactElement {
  // API unreachable — honest error card (C4).
  if (lastRun?.isError === true) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Dernier run</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">Historique indisponible</p>
        </CardContent>
      </Card>
    );
  }

  // No history yet — calm empty state.
  if (lastRun?.runUid == null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Dernier run</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Aucun run enregistré pour le moment.
          </p>
        </CardContent>
      </Card>
    );
  }

  const trigger = lastRun.trigger ?? "";
  const label = triggerLabel(trigger);
  const tone = triggerTone(trigger);
  const age = relativeTime(lastRun.startedAt);

  // Build the counts fragment (e.g. "3 traités · 78 ignorés").
  const countParts: string[] = [];
  if (lastRun.totalProcessed > 0) {
    countParts.push(
      `${String(lastRun.totalProcessed)} traité${lastRun.totalProcessed > 1 ? "s" : ""}`,
    );
  }
  if (lastRun.totalSkipped > 0) {
    countParts.push(
      `${String(lastRun.totalSkipped)} ignoré${lastRun.totalSkipped > 1 ? "s" : ""}`,
    );
  }
  const countsText =
    countParts.length > 0 ? countParts.join(" · ") : "Aucune action";

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <span>Dernier run</span>
          <Badge tone={tone}>{label}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        <p className="text-sm tabular-nums">
          <span className="text-muted-foreground">Lancé </span>
          {age}
        </p>
        <p className="text-sm tabular-nums">{countsText}</p>
        <Link
          to={`/pipeline?run=${encodeURIComponent(lastRun.runUid)}`}
          className="text-sm font-medium text-primary hover:underline"
        >
          Voir le détail →
        </Link>
      </CardContent>
    </Card>
  );
}
