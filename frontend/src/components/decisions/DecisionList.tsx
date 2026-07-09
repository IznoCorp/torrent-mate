/**
 * DecisionList — a scrollable list of pending scrape-decision rows.
 *
 * Each row shows the extracted title, a truncated staging path, a trigger chip
 * (coloured badge), and the candidate count.  Clicking a row calls the
 * ``onSelect`` callback with the item's id.
 *
 * Empty state: a muted message when there are no pending decisions.
 */

import { type ReactElement } from "react";

import type { DecisionListItem } from "@/api/decisions";
import { Badge } from "@/components/ui/badge";
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
const TRIGGER_VARIANT: Record<string, "danger" | "warning" | "info"> = {
  below_threshold: "danger",
  mid_band: "warning",
  ambiguous: "info",
};

/**
 * French labels for each trigger reason.
 */
const TRIGGER_LABEL: Record<string, string> = {
  below_threshold: "Score faible",
  mid_band: "Zone grise",
  ambiguous: "Ambigu",
};

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
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * DecisionList — renders pending scrape decisions as a scrollable list.
 *
 * Each row is an interactive element showing:
 *
 * - Extracted title (bold).
 * - Folder name (truncated, muted).
 * - Trigger chip (coloured {@link Badge}).
 * - Candidate count badge.
 *
 * When ``items`` is empty, a muted "Aucune décision" message is shown.
 *
 * Args:
 *   items: The pending decision rows from the API.
 *   onSelect: Row-selection callback, receives the decision id.
 *
 * Returns:
 *   The decision-list card element.
 */
export function DecisionList({
  items,
  onSelect,
}: DecisionListProps): ReactElement {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Décisions</CardTitle>
        <CardDescription>Candidats en attente de résolution</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune décision en attente.
          </p>
        ) : (
          items.map((item) => {
            const triggerTone = TRIGGER_VARIANT[item.trigger] ?? "info";
            const triggerLabel = TRIGGER_LABEL[item.trigger] ?? item.trigger;
            const folder = folderName(item.staging_path);

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  onSelect(item.id);
                }}
                className="flex flex-col gap-1 rounded-md border border-border bg-card p-3 text-left transition-colors hover:bg-accent"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium">
                    {item.extracted_title}
                    {item.extracted_year != null && (
                      <span className="ml-1 font-normal text-muted-foreground">
                        ({item.extracted_year})
                      </span>
                    )}
                  </span>
                  <Badge tone="neutral">{item.candidates_count}</Badge>
                </div>

                <div className="flex items-center justify-between gap-2">
                  <span
                    className="block max-w-[60%] truncate text-xs text-muted-foreground"
                    title={item.staging_path}
                  >
                    {folder}
                  </span>
                  <Badge tone={triggerTone}>{triggerLabel}</Badge>
                </div>
              </button>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
