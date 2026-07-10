/**
 * DecisionList — a scrollable flat list of scrape-decision rows.
 *
 * Each row shows the extracted title, a truncated staging path, a trigger chip
 * (coloured badge), a status badge (relabelled + tooltipped per §4.1), and the
 * candidate count.  Clicking a row calls the ``onSelect`` callback with the
 * item's id.  Pending rows additionally expose an inline "Ignorer" quick action
 * so the operator can dismiss without opening the detail panel.
 *
 * Empty state: a muted message when there are no decisions in the current view.
 */

import { type ReactElement } from "react";

import type { DecisionListItem } from "@/api/decisions";
import {
  statusLabel,
  statusTone,
  statusTooltip,
  TRIGGER_LABEL,
  TRIGGER_TONE,
} from "@/components/decisions/triggers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Trigger → Badge tone mapping.
 *
 * The DS Badge palette has seven tones: solid, neutral, outline, success,
 * warning, danger, info.  The three scrape-arbiter triggers are mapped to the
 * closest semantic match:
 *
 * - ``below_threshold`` → ``danger`` (red — score too low, needs attention)
 * - ``mid_band`` → ``warning`` (yellow — score in the grey zone)
 * - ``ambiguous`` → ``info`` (blue — multiple matches, needs review)
 *
 * There is no orange tone in the current DS palette; ``info`` is used for
 * ``ambiguous`` because it signals "needs attention" without the urgency of
 * ``danger`` or the caution of ``warning``.
 */
const TRIGGER_VARIANT = TRIGGER_TONE;

/**
 * Extract a short, human-readable folder name from an absolute staging path.
 *
 * Takes the last component of the path.  On macOS the staging root may contain
 * spaces; ``split("/")`` handles them correctly.
 *
 * Args:
 *   path: Absolute staging path (NFC-normalized by the API).
 *
 * Returns:
 *   The last path segment, or the full path if it has no separator.
 */
function folderName(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] ?? path;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Props for {@link DecisionList}.  All props are read-only. */
export interface DecisionListProps {
  /** The list of decision summary rows to display. */
  readonly items: readonly DecisionListItem[];
  /** Called with the decision id when a row is clicked. */
  readonly onSelect: (id: number) => void;
  /**
   * Called with the decision id when the inline "Ignorer" quick action is used
   * on a ``pending`` row. Omit to hide the inline action.
   */
  readonly onQuickDismiss?: (id: number) => void;
  /** The id currently being dismissed via the inline action (disables its button). */
  readonly dismissingId?: number | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * DecisionList — renders scrape decisions as a scrollable flat list.
 *
 * Each row is an interactive element showing:
 *
 * - Extracted title (bold) + year.
 * - Status badge (relabelled + tooltipped) and candidate count.
 * - Folder name (truncated, muted) + trigger chip.
 * - An inline "Ignorer" quick action on ``pending`` rows (when ``onQuickDismiss``
 *   is provided).
 *
 * When ``items`` is empty, a muted "Aucune décision" message is shown.
 *
 * Args:
 *   items: The decision rows from the API (any status).
 *   onSelect: Row-selection callback, receives the decision id.
 *   onQuickDismiss: Optional inline-dismiss callback for pending rows.
 *   dismissingId: Optional id whose inline dismiss is in flight.
 *
 * Returns:
 *   The decision-list card element.
 */
export function DecisionList({
  items,
  onSelect,
  onQuickDismiss,
  dismissingId = null,
}: DecisionListProps): ReactElement {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Décisions</CardTitle>
        <CardDescription>File de décisions de scraping</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune décision.</p>
        ) : (
          items.map((item) => {
            const triggerTone = TRIGGER_VARIANT[item.trigger] ?? "info";
            const triggerLabel = TRIGGER_LABEL[item.trigger] ?? item.trigger;
            const folder = folderName(item.staging_path);
            const rowStatusLabel = statusLabel(item.status);
            const rowStatusTone = statusTone(item.status);
            const rowStatusTooltip = statusTooltip(item.status);
            const isPending = item.status === "pending";
            const canQuickDismiss = isPending && onQuickDismiss != null;

            return (
              // The row is a plain container (not a <button>) so the inline
              // action button can nest without invalid <button> nesting; the
              // clickable title area is its own button for keyboard access.
              <div
                key={item.id}
                className="flex flex-col gap-1 rounded-md border border-border bg-card p-3 transition-colors hover:bg-accent"
              >
                <div className="flex items-start justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(item.id);
                    }}
                    className="flex-1 text-left text-sm font-medium"
                  >
                    {item.extracted_title}
                    {item.extracted_year != null && (
                      <span className="ml-1 font-normal text-muted-foreground">
                        ({item.extracted_year})
                      </span>
                    )}
                  </button>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {/* title on a wrapping span (the DS Badge component does
                        not accept a title prop per the lint contract). */}
                    <span title={rowStatusTooltip} className="inline-flex">
                      <Badge tone={rowStatusTone}>{rowStatusLabel}</Badge>
                    </span>
                    <Badge tone="neutral">{item.candidates_count}</Badge>
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(item.id);
                    }}
                    className="block max-w-[55%] truncate text-left text-xs text-muted-foreground"
                    title={item.staging_path}
                  >
                    {folder}
                  </button>
                  <div className="flex items-center gap-1.5">
                    <Badge tone={triggerTone}>{triggerLabel}</Badge>
                    {canQuickDismiss && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={dismissingId === item.id}
                        onClick={() => {
                          onQuickDismiss(item.id);
                        }}
                      >
                        {dismissingId === item.id ? "…" : "Ignorer"}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
