/**
 * StagingLibrary — the OBJ2A rich media-library grid of staged media.
 *
 * A filterable, paginated poster grid over ``GET /api/staging/media``: match
 * filter chips with live counts, a title search, a sort toggle, and a poster
 * card per media. Clicking a card opens a detail drawer with the provider ids,
 * season breakdown, dispatch preview, and the per-media pipeline timeline.
 *
 * Server-side pagination keeps the rendered grid bounded to one page
 * (``PAGE_SIZE`` cards), so the DOM never grows past ~two dozen nodes — no
 * client virtualization is needed at this scale.
 */

import { Film } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactElement,
} from "react";
import { useSearchParams } from "react-router-dom";

import type { StagingMediaItem, StagingMediaParams } from "@/api/client";
import { EmptyState } from "@/components/ds/EmptyState";
import { ErrorState } from "@/components/ds/ErrorState";
import { MediaCard } from "@/components/ds/MediaCard";
import { StatusBadge } from "@/components/ds/StatusBadge";
import { StagingMediaDetail } from "@/components/staging/StagingMediaDetail";
import { matchBadge, posterKind } from "@/components/staging/meta";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useStagingMedia } from "@/hooks/useStagingMedia";

/** Cards per page — bounds the rendered grid (no virtualization needed). */
const PAGE_SIZE = 24;

/** Match filter option: a value + French label + which count feeds its chip. */
export type MatchFilter = "all" | StagingMediaItem["match"];

/**
 * Position filter applied client-side on the fetched page items.
 *
 * - ``"blocked"`` → ``position_state === "blocked"`` (ambiguous, absent,
 *   verify-blocked, and any other blocked case).
 * - ``"active"`` → ``position_state === "active"``.
 * - ``"ready"`` → ``match === "matched" && position_state !== "blocked"``
 *   (verified items ready for continuation or dispatch).
 *
 * Pagination caveat: this filter applies to the current page of 24 items.
 * Staging volumes are small — a server-side parameter is recorded in
 * IMPLEMENTATION.md « Open items ».
 */
export type PositionFilter = "blocked" | "active" | "ready";

const MATCH_FILTERS: readonly { value: MatchFilter; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "matched", label: "Identifiés" },
  { value: "ambiguous", label: "À résoudre" },
  { value: "absent", label: "Non identifiés" },
];

/** Sort option: a value + French label. */
const SORT_OPTIONS: readonly {
  value: NonNullable<StagingMediaParams["sort"]>;
  label: string;
}[] = [
  { value: "recent", label: "Récents" },
  { value: "title", label: "Titre" },
  { value: "size", label: "Taille" },
];

/** Props for {@link StagingLibrary}. */
export interface StagingLibraryProps {
  /**
   * Optional controlled match filter. When provided, the internal match chips
   * are hidden and this value is used for the API call instead of the local
   * state — the parent is responsible for rendering its own filter UI (e.g. a
   * segment bar). When ``undefined``, the component manages its own match state.
   */
  readonly match?: MatchFilter;
  /**
   * Optional client-side position filter applied on the fetched page items.
   *
   * - ``"blocked"`` → ``position_state === "blocked"`` (all awaiting cases).
   * - ``"active"`` → ``position_state === "active"``.
   * - ``"ready"`` → ``match === "matched" && position_state !== "blocked"``.
   *
   * Pagination caveat: this filter applies to the current page of 24 items.
   * Staging volumes are small — a server-side parameter is recorded in
   * IMPLEMENTATION.md « Open items ».
   */
  readonly position?: PositionFilter | undefined;
  /**
   * Invoked when the operator sends a media to the resolution deck. Receives the
   * ``scrape_decision.id`` to open on (C18) — the ambiguous card's own
   * ``decision_id`` or the id returned by enqueuing a non-identified item.
   */
  readonly onOpenResolution?: (decisionId?: number) => void;
}

/** A grid of skeleton poster cards shown while the first page loads. */
function GridSkeleton(): ReactElement {
  return (
    <div
      className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
      aria-busy="true"
    >
      {Array.from({ length: 10 }).map((_, i) => (
        <Skeleton key={`lib-sk-${String(i)}`} className="aspect-[2/3] w-full" />
      ))}
    </div>
  );
}

/**
 * StagingLibrary — the staged-media library grid + detail drawer.
 *
 * Args:
 *   onOpenResolution: Optional handler to switch to the resolution deck.
 *
 * Returns:
 *   The library element.
 */
export function StagingLibrary({
  match: matchControlled,
  position,
  onOpenResolution,
}: StagingLibraryProps): ReactElement {
  const [matchInternal, setMatchInternal] = useState<MatchFilter>("all");
  const match = matchControlled ?? matchInternal;
  const [sort, setSort] =
    useState<NonNullable<StagingMediaParams["sort"]>>("recent");
  const [search, setSearch] = useState("");
  // A1: "sans bande-annonce" — keep only items lacking a trailer file.
  const [missingTrailer, setMissingTrailer] = useState(false);
  const [page, setPage] = useState(1);
  // The open media detail is URL-addressable (?media=<id>) so the browser/router
  // Back button closes it like any route. Opening pushes a history entry;
  // closing replaces it (Escape/overlay/X leave no dangling entry, and Back on
  // an open detail pops straight to the grid).
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get("media");
  const openDetail = useCallback(
    (id: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("media", id);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );
  const closeDetail = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("media");
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);
  // C17: comfortable (default) vs compact grid density.
  const [density, setDensity] = useState<"comfortable" | "compact">(
    "comfortable",
  );

  // Compact packs more columns and drops the overview (via MediaCard density);
  // comfortable keeps the roomy 2→5 grid. No per-card overrides (C17).
  const gridClass =
    density === "compact"
      ? "grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7"
      : "grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5";

  const params = useMemo<StagingMediaParams>(() => {
    // with_dispatch (A2): populate each item's dispatch_target so the detail
    // drawer's "où sera-t-il rangé" preview actually renders (was never requested).
    const p: StagingMediaParams = {
      sort,
      page,
      page_size: PAGE_SIZE,
      with_dispatch: true,
    };
    if (match !== "all") p.match = match;
    if (missingTrailer) p.missing_trailer = true;
    const trimmed = search.trim();
    if (trimmed !== "") p.q = trimmed;
    return p;
  }, [match, sort, page, search, missingTrailer]);

  const query = useStagingMedia(params);
  const data = query.data;
  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const counts = data?.counts;
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  /**
   * Client-side position filter applied on the current page of items. This is a
   * lightweight overlay — the server-side pagination is unchanged, so the total
   * page count may overstate the actual reachable items when a position filter is
   * active. Staging volumes are small enough that this is acceptable for now; a
   * server-side ``position`` query parameter is recorded in
   * IMPLEMENTATION.md « Open items ».
   */
  const filteredItems = useMemo(() => {
    if (position === undefined) return items;
    return items.filter((item) => {
      switch (position) {
        case "blocked":
          return item.position_state === "blocked";
        case "active":
          return item.position_state === "active";
        case "ready":
          return item.match === "matched" && item.position_state !== "blocked";
      }
    });
  }, [items, position]);

  const selected = items.find((i) => i.id === selectedId) ?? null;

  // D3: ?media= not found on the current page — surface an inline notice so the
  // operator knows the param was not silently ignored (honest exit).
  const [mediaNotFoundNotice, setMediaNotFoundNotice] = useState(false);
  useEffect(() => {
    if (
      selectedId !== null &&
      !query.isLoading &&
      !query.isError &&
      selected === null
    ) {
      setMediaNotFoundNotice(true);
    } else if (selectedId === null) {
      setMediaNotFoundNotice(false);
    }
  }, [selectedId, selected, query.isLoading, query.isError]);

  /** Count feeding a match filter chip (undefined while loading → hidden). */
  function chipCount(value: MatchFilter): number | undefined {
    if (counts === undefined) return undefined;
    if (value === "all") return counts.total;
    return counts[value];
  }

  /** Apply a filter change and reset to the first page. */
  function resetTo<T>(setter: (v: T) => void, value: T): void {
    setter(value);
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* ---- Controls ------------------------------------------------------- */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="search"
            value={search}
            placeholder="Rechercher un titre…"
            className="h-9 w-full sm:max-w-xs"
            onChange={(e) => {
              resetTo(setSearch, e.target.value);
            }}
          />
          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            {/* Density toggle (C17) — comfortable vs compact grid. */}
            <div
              className="flex items-center gap-1 rounded-md border border-border p-0.5"
              role="group"
              aria-label="Densité d'affichage"
            >
              {(
                [
                  { value: "comfortable", label: "Confortable" },
                  { value: "compact", label: "Compact" },
                ] as const
              ).map((opt) => (
                <Button
                  key={opt.value}
                  type="button"
                  size="sm"
                  variant={density === opt.value ? "default" : "ghost"}
                  aria-pressed={density === opt.value}
                  onClick={() => {
                    setDensity(opt.value);
                  }}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
            <div
              className="flex items-center gap-1 rounded-md border border-border p-0.5"
              role="group"
              aria-label="Trier"
            >
              {SORT_OPTIONS.map((opt) => (
                <Button
                  key={opt.value}
                  type="button"
                  size="sm"
                  variant={sort === opt.value ? "default" : "ghost"}
                  onClick={() => {
                    resetTo(setSort, opt.value);
                  }}
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>
        </div>

        {matchControlled === undefined && (
          <div
            className="flex flex-wrap items-center gap-2"
            role="group"
            aria-label="Filtrer par identification"
          >
            {MATCH_FILTERS.map((filter) => {
              const active = match === filter.value;
              const count = chipCount(filter.value);
              // C18: an idle "À résoudre" chip with a non-zero count wears the
              // warning tone so pending ambiguities call for attention.
              const pendingAmbiguous =
                filter.value === "ambiguous" && (count ?? 0) > 0;
              const tone = active
                ? "solid"
                : pendingAmbiguous
                  ? "warning"
                  : "outline";
              return (
                <button
                  key={filter.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => {
                    resetTo(setMatchInternal, filter.value);
                  }}
                >
                  <Badge tone={tone} className="cursor-pointer">
                    {filter.label}
                    {count !== undefined && (
                      <span className="ml-1 opacity-70">({count})</span>
                    )}
                  </Badge>
                </button>
              );
            })}
            {/* A1: "sans bande-annonce" toggle — a separate axis from the match
              chips, so it sits after them with a divider. */}
            <span className="mx-1 h-4 w-px bg-border" aria-hidden />
            <button
              type="button"
              aria-pressed={missingTrailer}
              onClick={() => {
                resetTo(setMissingTrailer, !missingTrailer);
              }}
            >
              <Badge
                tone={missingTrailer ? "solid" : "outline"}
                className="cursor-pointer"
              >
                Sans bande-annonce
                {counts !== undefined && (
                  <span className="ml-1 opacity-70">
                    ({counts.total - counts.with_trailer})
                  </span>
                )}
              </Badge>
            </button>
          </div>
        )}
      </div>

      {/* ---- Content -------------------------------------------------------- */}
      {/* D3: ?media= not found on the current page — honest notice. */}
      {mediaNotFoundNotice && (
        <p
          role="alert"
          className="rounded-md border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground"
        >
          Média introuvable sur cette page — ajustez les filtres ou la
          recherche.
        </p>
      )}
      {query.isLoading ? (
        <GridSkeleton />
      ) : query.isError ? (
        <ErrorState
          title="Impossible de charger la bibliothèque"
          {...(query.error instanceof Error
            ? { message: query.error.message }
            : {})}
          onRetry={() => {
            void query.refetch();
          }}
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={Film}
          title="Aucun média en attente"
          description={
            match === "all"
              ? "La zone de transit est vide — rien à trier pour le moment."
              : "Aucun média ne correspond à ce filtre."
          }
        />
      ) : (
        <>
          <div className={gridClass}>
            {filteredItems.map((item) => {
              const badge = matchBadge(item.match);
              const kind = posterKind(item.media_kind);
              const seasonCount = item.seasons?.length ?? 0;
              return (
                <MediaCard
                  key={item.id}
                  title={item.title}
                  year={item.year ?? null}
                  posterUrl={item.poster_url ?? null}
                  {...(kind !== undefined ? { kind } : {})}
                  overview={item.overview ?? null}
                  density={density}
                  onOpen={() => {
                    openDetail(item.id);
                  }}
                  badges={
                    <>
                      <StatusBadge tone={badge.tone} label={badge.label} />
                      {seasonCount > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {seasonCount} saison{seasonCount > 1 ? "s" : ""}
                        </span>
                      )}
                    </>
                  }
                />
              );
            })}
          </div>

          {/* ---- Pagination ------------------------------------------------- */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => {
                  setPage((p) => Math.max(1, p - 1));
                }}
              >
                Précédent
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} / {totalPages}
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => {
                  setPage((p) => Math.min(totalPages, p + 1));
                }}
              >
                Suivant
              </Button>
            </div>
          )}
        </>
      )}

      {/* ---- Detail drawer -------------------------------------------------- */}
      <Sheet
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) closeDetail();
        }}
      >
        <SheetContent className="w-full gap-0 overflow-y-auto px-6 pb-6 sm:max-w-md">
          {selected !== null && (
            <>
              <SheetHeader className="pr-8">
                <SheetTitle>{selected.title}</SheetTitle>
              </SheetHeader>
              <div className="mt-4">
                <StagingMediaDetail
                  item={selected}
                  {...(onOpenResolution !== undefined
                    ? {
                        onResolve: (decisionId?: number) => {
                          // Drop the ?media param so the detail doesn't reopen
                          // when the operator returns from the deck.
                          closeDetail();
                          onOpenResolution(decisionId);
                        },
                      }
                    : {})}
                />
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
