/**
 * Medias page — the media library grid + resolution deck + decision browse
 * (``/medias``).
 *
 * Default view is the library grid with pipeline-stage segments. Three tabs:
 * ``Bibliothèque`` (grid with segments), ``À résoudre`` (resolution deck),
 * ``Décisions`` (flat list with status filter chips + detail panel).
 *
 * Reuses:
 * - {@link StagingLibrary} for the poster grid + detail drawer
 * - {@link ResolutionDeck} for the rapid resolution flow
 * - {@link DecisionList} + {@link DecisionDetail} for the full-status browse
 * - {@link ScrapeActivityPanel} for the live scrape-activity feed
 * - {@link useAllDecisions} to merge every status into one flat list
 * - {@link useDecisionDetail} for the selected decision's detail
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
} from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { decisionsKeys, dismissDecision } from "@/api/decisions";
import { useAllDecisions, useDecisionDetail } from "@/hooks/useDecisions";
import { DecisionDetail } from "@/components/decisions/DecisionDetail";
import { DecisionList } from "@/components/decisions/DecisionList";
import { ResolutionDeck } from "@/components/decisions/ResolutionDeck";
import { ScrapeActivityPanel } from "@/components/decisions/ScrapeActivityPanel";
import { PageHeader } from "@/components/ds/PageHeader";
import { StagingLibrary } from "@/components/staging/StagingLibrary";
import type { MatchFilter } from "@/components/staging/StagingLibrary";
import {
  STATUS_SHORT_LABEL,
  STATUS_TOOLTIP,
  type DecisionStatus,
} from "@/components/decisions/triggers";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Tab identifier for the three main views. */
type TabId = "library" | "resolve" | "decisions";

/** Library grid segment identifier. */
type LibrarySegment = "all" | "awaiting" | "active" | "ready";

/** Status filter chips, in display order (matches the API status Literal). */
const STATUS_FILTERS: readonly DecisionStatus[] = [
  "pending",
  "resolved",
  "dismissed",
  "superseded",
];

/** Library segments with French labels. */
const LIBRARY_SEGMENTS: readonly {
  value: LibrarySegment;
  label: string;
}[] = [
  { value: "all", label: "Tous" },
  { value: "awaiting", label: "À traiter" },
  { value: "active", label: "En cours" },
  { value: "ready", label: "Prêts" },
];

/**
 * Map a library segment to the ``match`` filter passed to {@link StagingLibrary}.
 *
 * Plan-drift note: the API has no ``awaiting_action`` or ``position_state``
 * query parameter, and the ``stage`` parameter is single-value (cannot express
 * "all active stages except dispatch"). The mapping uses the closest available
 * filter:
 *
 * - ``Tous`` → no filter (everything).
 * - ``À traiter`` → ``match="ambiguous"`` — items whose identity is uncertain
 *   and need the operator to decide. This is the nearest proxy for "needs action":
 *   every ambiguous item blocks the pipeline until resolved.
 * - ``En cours`` → no filter (same grid as Tous) — there is no server-side
 *   filter for "items with an active pipeline stage". The segment label signals
 *   intent; the actual filter will be tightened when the API grows a
 *   ``position_state`` parameter.
 * - ``Prêts`` → ``match="matched"`` — identified items ready for continuation
 *   or dispatch.
 */
function segmentToMatch(segment: LibrarySegment): MatchFilter | undefined {
  switch (segment) {
    case "ready":
      return "matched";
    case "awaiting":
      return "ambiguous";
    case "all":
    case "active":
    default:
      return undefined;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Skeleton placeholder shown while the decision list is loading. */
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
 * Medias — the authenticated medias route (``/medias``).
 *
 * Layout:
 * - Desktop: tab bar → content (library grid with segments, resolution deck, or
 *   decision list + detail side-by-side).
 * - Mobile: tab bar → content stacks vertically; decision detail replaces list
 *   with a "Retour" back button.
 *
 * URL-addressable: ``?media=<id>`` opens the library detail drawer,
 * ``?decision=<id>`` opens the decision detail panel.
 *
 * Returns:
 *   The medias page element.
 */
export default function Medias(): ReactElement {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  // The active tab initialises from the URL so deep-links survive a fresh load:
  // ?media targets the library grid, ?decision targets the decisions tab.
  const [tab, setTab] = useState<TabId>(() =>
    searchParams.has("media")
      ? "library"
      : searchParams.has("decision")
        ? "decisions"
        : "library",
  );

  // Library grid segment (only relevant when tab === "library").
  const [segment, setSegment] = useState<LibrarySegment>("all");

  // C18: the decision the deck should open on, set when the operator resolves a
  // specific card (ambiguous or freshly enqueued). Null = open at the head.
  const [deckDecisionId, setDeckDecisionId] = useState<number | null>(null);

  // ---- Décisions tab state ----------------------------------------------------
  // Optional, multi-select status filter. Empty set = show ALL statuses (default).
  const [activeStatuses, setActiveStatuses] = useState<Set<DecisionStatus>>(
    () => new Set(),
  );
  const rawDecision = searchParams.get("decision");
  const selectedId =
    rawDecision != null && /^\d+$/.test(rawDecision)
      ? Number(rawDecision)
      : null;
  // On mobile the detail replaces the list whenever a decision is selected.
  const showDetailMobile = selectedId != null;
  const openDecision = useCallback(
    (id: number) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("decision", String(id));
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );
  const closeDecision = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("decision");
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);
  // The decision id whose inline "Ignorer" quick-dismiss is in flight.
  const [dismissingId, setDismissingId] = useState<number | null>(null);

  // Stable array for the hook: an empty filter fetches (and merges) all statuses.
  const activeStatusesList = useMemo<DecisionStatus[]>(
    () => STATUS_FILTERS.filter((s) => activeStatuses.has(s)),
    [activeStatuses],
  );

  const {
    items,
    counts,
    isLoading: listLoading,
    isError: listError,
    errored,
  } = useAllDecisions(activeStatusesList);

  // A partial failure on the core `pending` signal must be surfaced, not
  // coerced to "0 pending" (SF2). This is distinct from `listError` (which is
  // only true when EVERY status query failed).
  const pendingFailed = errored.has("pending");
  const pendingCount = counts.pending ?? 0;

  const {
    data: detailData,
    isLoading: detailLoading,
    isError: detailError,
    error: detailErrorObj,
  } = useDecisionDetail(selectedId ?? 0);

  // ---- Inline quick-dismiss mutation ------------------------------------------
  const quickDismissMutation = useMutation({
    mutationFn: (id: number) => dismissDecision(id),
    onSuccess: () => {
      toast.success("Décision ignorée.");
      void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        if (error.status === 410) {
          toast.error(
            "Cette décision a été remplacée par une version plus récente.",
          );
        } else if (error.status === 409) {
          toast.error("Cette décision n'est plus en attente.");
        } else {
          toast.error(error.detail);
        }
        void queryClient.invalidateQueries({ queryKey: decisionsKeys.all });
      } else {
        toast.error("Erreur inattendue.");
      }
    },
    onSettled: () => {
      setDismissingId(null);
    },
  });

  // ---- Event handlers ----------------------------------------------------------

  function handleSelect(id: number): void {
    openDecision(id);
  }

  function handleDecisionHandled(): void {
    closeDecision();
  }

  function handleBackToList(): void {
    closeDecision();
  }

  function handleQuickDismiss(id: number): void {
    setDismissingId(id);
    quickDismissMutation.mutate(id);
  }

  /** Toggle a status filter chip on/off (multi-select). */
  function handleToggleStatus(status: DecisionStatus): void {
    setActiveStatuses((prev) => {
      const next = new Set(prev);
      if (next.has(status)) {
        next.delete(status);
      } else {
        next.add(status);
      }
      return next;
    });
    // A filter change can drop the selected row from view; deselect to avoid a
    // stale detail panel (matches the previous status-tab reset behaviour).
    closeDecision();
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
    closeDecision();
  }, [detailError, detailErrorObj, queryClient, closeDecision]);

  // ---- Render ------------------------------------------------------------------

  return (
    <section className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title="Médias"
        actions={
          <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
            <Button
              type="button"
              size="sm"
              variant={tab === "library" ? "default" : "ghost"}
              onClick={() => {
                setTab("library");
              }}
            >
              Bibliothèque
            </Button>
            <Button
              type="button"
              size="sm"
              variant={tab === "resolve" ? "default" : "ghost"}
              onClick={() => {
                setTab("resolve");
              }}
            >
              À résoudre
              {pendingCount > 0 ? ` (${String(pendingCount)})` : ""}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={tab === "decisions" ? "default" : "ghost"}
              onClick={() => {
                setTab("decisions");
              }}
            >
              Décisions
            </Button>
          </div>
        }
      />

      <ScrapeActivityPanel />

      {tab === "library" ? (
        <>
          {/* ---- Library grid segments ---------------------------------------- */}
          <div
            className="flex items-center gap-1 rounded-md border border-border p-0.5 w-fit"
            role="group"
            aria-label="Filtrer par étape du pipeline"
          >
            {LIBRARY_SEGMENTS.map((seg) => (
              <Button
                key={seg.value}
                type="button"
                size="sm"
                variant={segment === seg.value ? "default" : "ghost"}
                aria-pressed={segment === seg.value}
                onClick={() => {
                  setSegment(seg.value);
                }}
              >
                {seg.label}
              </Button>
            ))}
          </div>

          <StagingLibrary
            {...((segMatch) =>
              segMatch != null ? { match: segMatch } : {})(
              segmentToMatch(segment),
            )}
            onOpenResolution={(decisionId) => {
              setDeckDecisionId(decisionId ?? null);
              setTab("resolve");
            }}
          />
        </>
      ) : tab === "resolve" ? (
        <ResolutionDeck
          {...(deckDecisionId != null
            ? { initialDecisionId: deckDecisionId }
            : {})}
        />
      ) : (
        <>
          {/* ---- Optional status filter chips -------------------------------- */}
          <div className="flex flex-col gap-1.5">
            <div
              className="flex flex-wrap items-center gap-2"
              role="group"
              aria-label="Filtrer les décisions par statut (optionnel)"
            >
              {STATUS_FILTERS.map((status) => {
                const active = activeStatuses.has(status);
                const count = counts[status];
                // A null count means that status's query failed — show "?" rather
                // than a misleading "0" (SF2).
                const countLabel = count == null ? "?" : String(count);
                return (
                  <button
                    key={status}
                    type="button"
                    aria-pressed={active}
                    title={
                      count == null
                        ? `${STATUS_TOOLTIP[status]} — échec du chargement`
                        : STATUS_TOOLTIP[status]
                    }
                    onClick={() => {
                      handleToggleStatus(status);
                    }}
                  >
                    <Badge
                      tone={active ? "solid" : "outline"}
                      className="cursor-pointer"
                    >
                      {STATUS_SHORT_LABEL[status]}
                      <span className="ml-1 opacity-70">({countLabel})</span>
                    </Badge>
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              {activeStatuses.size === 0
                ? "Toutes les décisions sont affichées — cliquez un statut pour filtrer."
                : "Filtre actif — cliquez un statut pour l'activer/le désactiver."}
            </p>
          </div>

          {/* ---- Partial-failure banner (SF2) -------------------------------- */}
          {!listError && pendingFailed && (
            <p role="alert" className="text-sm text-danger">
              Impossible de charger les décisions en attente — le nombre affiché
              peut être incomplet. Réessayez.
            </p>
          )}

          {/* ---- Content area ------------------------------------------------ */}
          {listError ? (
            <p className="text-sm text-danger">
              Erreur lors du chargement des décisions.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
              {/* List panel — hidden on mobile when detail is showing, always
                  visible on desktop */}
              <div className={showDetailMobile ? "hidden lg:block" : "block"}>
                {listLoading && items.length === 0 ? (
                  <ListSkeleton />
                ) : (
                  <DecisionList
                    items={items}
                    onSelect={handleSelect}
                    onQuickDismiss={handleQuickDismiss}
                    dismissingId={dismissingId}
                  />
                )}
              </div>

              {/* Detail panel — a SINGLE DecisionDetail instance (F36): shown on
                  mobile when selected (with a back button), side-by-side on
                  desktop, and replaced by the placeholder when nothing is
                  selected. */}
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
                      // key={id} resets DecisionDetail's local state per
                      // decision so a search / runUid from one never leaks onto
                      // another (F02).
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
        </>
      )}
    </section>
  );
}
