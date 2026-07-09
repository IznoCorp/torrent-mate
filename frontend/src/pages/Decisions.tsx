/**
 * Decisions page — the scrape-arbiter decision queue (``/scraping``).
 *
 * Renders a status-filtered list of scrape decisions with a side-by-side
 * detail panel on desktop.  The layout stacks vertically on mobile:
 * selecting a row replaces the list with the detail view; a "Retour"
 * button returns to the list.
 *
 * Reuses:
 * - {@link DecisionList} for the row list
 * - {@link DecisionDetail} for the selected item's full detail + actions
 * - {@link useDecisions} / {@link useDecisionDetail} TanStack hooks (§4.1)
 */

import { useState, type ReactElement } from "react";

import { useDecisionDetail, useDecisions } from "@/hooks/useDecisions";
import { DecisionDetail } from "@/components/decisions/DecisionDetail";
import { DecisionList } from "@/components/decisions/DecisionList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Status values the operator can filter by. */
const STATUS_FILTERS = [
  { value: "pending", label: "En attente" },
  { value: "resolved", label: "Résolues" },
  { value: "dismissed", label: "Ignorées" },
  { value: "superseded", label: "Remplacées" },
] as const;

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Skeleton placeholder shown while the list query is loading. */
function ListSkeleton(): ReactElement {
  return (
    <div className="flex flex-col gap-3 p-4">
      {Array.from({ length: 5 }).map((_, idx) => (
        <Skeleton key={`sk-${String(idx)}`} className="h-16 w-full" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

/**
 * Decisions — the authenticated decisions route (``/scraping``).
 *
 * Layout:
 * - Desktop: filter chips → [DecisionList | DecisionDetail] side-by-side.
 * - Mobile: filter chips → list (stacked), detail replaces list with a
 *   "Retour" back button.
 *
 * Returns:
 *   The decisions page element.
 */
export default function Decisions(): ReactElement {
  const [status, setStatus] = useState<string>("pending");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  // When true on mobile, the detail panel replaces the list.
  const [showDetailMobile, setShowDetailMobile] = useState(false);

  const {
    data: listData,
    isLoading: listLoading,
    isError: listError,
  } = useDecisions({ status });

  const { data: detailData, isLoading: detailLoading } = useDecisionDetail(
    selectedId ?? 0,
  );

  // ---- event handlers --------------------------------------------------------

  function handleSelect(id: number): void {
    setSelectedId(id);
    setShowDetailMobile(true);
  }

  function handleDecisionHandled(): void {
    setSelectedId(null);
    setShowDetailMobile(false);
  }

  function handleBackToList(): void {
    setSelectedId(null);
    setShowDetailMobile(false);
  }

  function handleStatusChange(newStatus: string): void {
    setStatus(newStatus);
    setSelectedId(null);
    setShowDetailMobile(false);
  }

  // ---- render ----------------------------------------------------------------

  return (
    <section className="mx-auto flex max-w-6xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">
        Décisions de scraping
      </h1>

      {/* ---- Status filter chips --------------------------------------------- */}
      <div className="flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((filter) => {
          const active = status === filter.value;
          return (
            <button
              key={filter.value}
              type="button"
              onClick={() => {
                handleStatusChange(filter.value);
              }}
            >
              <Badge
                tone={active ? "solid" : "outline"}
                className="cursor-pointer"
              >
                {filter.label}
              </Badge>
            </button>
          );
        })}
      </div>

      {/* ---- Content area ---------------------------------------------------- */}
      {listError ? (
        <p className="text-sm text-[var(--danger)]">
          Erreur lors du chargement des décisions.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          {/* List panel — hidden on mobile when detail is showing, always visible on desktop */}
          <div className={showDetailMobile ? "hidden lg:block" : "block"}>
            {listLoading || listData == null ? (
              <ListSkeleton />
            ) : (
              <DecisionList items={listData.items} onSelect={handleSelect} />
            )}
          </div>

          {/* Detail panel — mobile: replaces list with back button */}
          <div className={showDetailMobile ? "block lg:hidden" : "hidden"}>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="mb-2"
              onClick={handleBackToList}
            >
              ← Retour à la liste
            </Button>

            {detailLoading || detailData == null ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <DecisionDetail
                decision={detailData}
                onDecisionHandled={handleDecisionHandled}
              />
            )}
          </div>

          {/* Detail panel — desktop: side-by-side when selected */}
          <div className={selectedId != null ? "hidden lg:block" : "hidden"}>
            {detailLoading || detailData == null ? (
              <Skeleton className="h-64 w-full" />
            ) : (
              <DecisionDetail
                decision={detailData}
                onDecisionHandled={handleDecisionHandled}
              />
            )}
          </div>

          {/* Desktop placeholder when nothing is selected */}
          <div
            className={
              selectedId == null
                ? "hidden lg:flex lg:items-center lg:justify-center lg:rounded-lg lg:border lg:border-dashed lg:border-border lg:p-8"
                : "hidden"
            }
          >
            <p className="text-sm text-muted-foreground">
              Sélectionnez une décision pour voir les détails.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
