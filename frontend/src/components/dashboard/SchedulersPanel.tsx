/**
 * SchedulersPanel — the Dashboard "Planificateurs" overview (webui-ux Phase 5).
 *
 * Renders one row per scheduled agent from ``GET /api/maintenance/schedulers``
 * (via {@link useSchedulers}): the download watcher plus each static cron job.
 * Each row shows the agent name, a kind badge (watcher / cron), its
 * schedule-or-enabled state, the last-run relative time, and a last-outcome
 * tone. Responsive (name + badge stack on the left, meta on the right ≥ sm),
 * with explicit loading / error / empty states.
 */

import type { ReactElement } from "react";

import type { SchedulerItem } from "@/api/maintenance";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { relativeTime } from "@/lib/format";
import { useSchedulers } from "@/hooks/useSchedulers";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Map a scheduler's last outcome to a {@link Badge} tone.
 *
 * Args:
 *   outcome: The row's ``last_outcome`` (``"success"`` / ``"error"`` /
 *       ``"killed"`` / ``null``).
 *
 * Returns:
 *   A DS badge tone.
 */
function outcomeTone(outcome: string | null | undefined): BadgeProps["tone"] {
  switch (outcome) {
    case "success":
      return "success";
    case "error":
    case "killed":
      return "danger";
    default:
      return "neutral";
  }
}

/**
 * Human-readable French label for a last outcome.
 *
 * Args:
 *   outcome: The row's ``last_outcome``.
 *
 * Returns:
 *   A French label, or ``"Jamais exécuté"`` when unknown.
 */
function outcomeLabel(outcome: string | null | undefined): string {
  switch (outcome) {
    case "success":
      return "Réussi";
    case "error":
      return "Échec";
    case "killed":
      return "Interrompu";
    default:
      return "Jamais exécuté";
  }
}

/**
 * The right-hand meta line describing WHEN this agent runs.
 *
 * The watcher is event-driven (enabled / paused); a cron shows its schedule.
 *
 * Args:
 *   item: The scheduler row.
 *
 * Returns:
 *   A French schedule/enabled string.
 */
function scheduleText(item: SchedulerItem): string {
  if (item.kind === "watcher") {
    return item.enabled === false
      ? "En pause"
      : "Actif (à la fin des téléchargements)";
  }
  return item.schedule ?? "Planification inconnue";
}

// ---------------------------------------------------------------------------
// Row
// ---------------------------------------------------------------------------

/**
 * A single scheduler row.
 *
 * Args:
 *   item: The scheduler entry to render.
 *
 * Returns:
 *   The row element.
 */
function SchedulerRow({
  item,
}: {
  readonly item: SchedulerItem;
}): ReactElement {
  const kindTone: BadgeProps["tone"] =
    item.kind === "watcher" ? "info" : "neutral";
  const kindLabel = item.kind === "watcher" ? "Surveillance" : "Cron";

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex items-center gap-2">
          <Badge tone={kindTone}>{kindLabel}</Badge>
          <span className="truncate text-sm font-medium">
            {item.display_name}
          </span>
        </div>
        <span className="text-xs text-muted-foreground">
          {scheduleText(item)}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-2 sm:flex-col sm:items-end sm:gap-1">
        <Badge tone={outcomeTone(item.last_outcome)} dot>
          {outcomeLabel(item.last_outcome)}
        </Badge>
        <span className="text-xs tabular-nums text-muted-foreground">
          {relativeTime(item.last_run_at)}
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

/**
 * SchedulersPanel — a card listing every scheduled agent with its last run.
 *
 * Polls ``GET /api/maintenance/schedulers`` every 60 s (via
 * {@link useSchedulers}).
 *
 * Returns:
 *   The schedulers card element.
 */
export function SchedulersPanel(): ReactElement {
  const { data, isLoading, isError } = useSchedulers();
  const schedulers = data?.schedulers ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Planificateurs</CardTitle>
        <CardDescription>
          Surveillance et tâches planifiées, avec leur dernière exécution
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {isLoading && (
          <p className="text-sm text-muted-foreground">
            Chargement des planificateurs…
          </p>
        )}
        {isError && (
          <p className="text-sm text-muted-foreground">
            Erreur lors du chargement.
          </p>
        )}
        {!isLoading &&
          !isError &&
          schedulers.map((item) => (
            <SchedulerRow key={item.name} item={item} />
          ))}
        {!isLoading && !isError && schedulers.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucun planificateur.</p>
        )}
      </CardContent>
    </Card>
  );
}
