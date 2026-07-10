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

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactElement } from "react";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { decisionsKeys } from "@/api/decisions";
import { useDecisionDetail, useDecisions } from "@/hooks/useDecisions";
import { DecisionDetail } from "@/components/decisions/DecisionDetail";
import { DecisionList } from "@/components/decisions/DecisionList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** The closed set of statuses the operator can filter by (matches the API Literal). */
type StatusFilter = "pending" | "resolved" | "dismissed" | "superseded";

/** Status values the operator can filter by. */
const STATUS_FILTERS: readonly { value: StatusFilter; label: string }[] = [
  { value: "pending", label: "En attente" },
  { value: "resolved", label: "Résolues" },
  { value: "dismissed", label: "Ignorées" },
  { value: "superseded", label: "Remplacées" },
];

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
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StatusFilter>("pending");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  // When true on mobile, the detail panel replaces the list.
  const [showDetailMobile, setShowDetailMobile] = useState(false);

  const {
    data: listData,
    isLoading: listLoading,
    isError: listError,
  } = useDecisions({ status });

  const {
    data: detailData,
    isLoading: detailLoading,
    isError: detailError,
    error: detailErrorObj,
  } = useDecisionDetail(selectedId ?? 0);

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

  function handleStatusChange(newStatus: StatusFilter): void {
    setStatus(newStatus);
    setSelectedId(null);
    setShowDetailMobile(false);
  }

  // A detail GET can 410 when the row was superseded between the list render
  // and the click (the backend list-GC makes this a normal race). Deselect +
  // refresh the list instead of rendering an eternal skeleton (F14).
  useEffect(() => {
    if (!detailError) return;
    if (detailErrorObj instanceof ApiError && detailErrorObj.status === 410) {
      toast.error(
        "Cette décision a été remplacée par une version plus récente.",
      );
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
    }
    setSelectedId(null);
    setShowDetailMobile(false);
  }, [detailError, detailErrorObj, queryClient]);

  // ---- render ----------------------------------------------------------------

  return (
    <section className="mx-auto flex max-w-6xl flex-col gap-4">
      <h1 className="text-xl font-semibold tracking-tight">
        Décisions de scraping
      </h1>

      {/* ---- Status filter chips --------------------------------------------- */}
      <div
        className="flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Filtrer les décisions par statut"
      >
        {STATUS_FILTERS.map((filter) => {
          const active = status === filter.value;
          return (
            <button
              key={filter.value}
              type="button"
              aria-pressed={active}
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

          {/* Detail panel — a SINGLE DecisionDetail instance (F36): shown on
              mobile when selected (with a back button), side-by-side on desktop,
              and replaced by the placeholder when nothing is selected. */}
          <div
            className={
              selectedId != null
                ? showDetailMobile
                  ? "block"
                  : "hidden lg:block"
                : "hidden lg:flex lg:items-center lg:justify-center lg:rounded-lg lg:border lg:border-dashed lg:border-border lg:p-8"
            }
          >
            {selectedId != null ? (
              <>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mb-2 lg:hidden"
                  onClick={handleBackToList}
                >
                  ← Retour à la liste
                </Button>

                {detailLoading || detailData == null ? (
                  <Skeleton className="h-64 w-full" />
                ) : (
                  // key={id} resets DecisionDetail's local state per decision
                  // so a search / runUid from one never leaks onto another (F02).
                  <DecisionDetail
                    key={detailData.id}
                    decision={detailData}
                    onDecisionHandled={handleDecisionHandled}
                  />
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Sélectionnez une décision pour voir les détails.
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
