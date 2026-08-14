/**
 * DecisionList — the queue of scrape decisions.
 *
 * Every row is a {@link DecisionRow}: the same card the journal draws, because
 * they are two views of one thing — a folder the scrape could not name. Drawing
 * them separately is how the same decision came to read « Réglée » on one
 * screen and « identifiée » on the other.
 *
 * A pending row also carries an inline « Laisser tel quel », so the operator
 * can agree with the machine without opening the arbitration. It is a shortcut
 * to something that screen also offers, never the only way in (R43).
 *
 * Empty state: an explicit one, never a blank list.
 */

import { type ReactElement } from "react";

import type { DecisionListItem } from "@/api/decisions";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ds/EmptyState";
import { decisionFacts } from "@/components/decisions/decisionFacts";
import { DecisionRow } from "@/components/ds/DecisionRow";

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
   * Called with the decision id when the inline « Laisser tel quel » shortcut
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
 * - An inline « Laisser tel quel » shortcut on ``pending`` rows (when ``onQuickDismiss``
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
          <EmptyState
            compact
            title="Aucune décision"
            description="Rien n'attend d'arbitrage : aucun média n'est resté ambigu."
          />
        ) : (
          items.map((item) => (
            /* One card for a decision, wherever it is drawn — the queue and the
               journal are two views of one thing. The inline « Laisser tel
               quel » stays outside the card: it is the LIST's shortcut to an
               action the arbitration screen also offers, never the only way in
               (R43). */
            <div key={item.id} className="flex flex-col gap-1">
              <DecisionRow
                {...decisionFacts(item)}
                candidates={item.candidates_count}
                onOpen={() => {
                  onSelect(item.id);
                }}
              />
              {item.status === "pending" && onQuickDismiss != null && (
                <Button
                  variant="ghost"
                  size="sm"
                  // X4 — the mobile touch minimum. A shortcut nobody can hit
                  // is not a shortcut.
                  className="min-h-11 self-end md:min-h-8"
                  disabled={dismissingId === item.id}
                  onClick={() => {
                    onQuickDismiss(item.id);
                  }}
                >
                  {dismissingId === item.id ? "En cours…" : "Laisser tel quel"}
                </Button>
              )}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
