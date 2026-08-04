/**
 * MediaSheet — autonomous, reusable media detail component (DESIGN D7).
 *
 * Receives a provider identity and an optional kind hint, fetches the full
 * sheet from ``GET /api/media/{provider}/{provider_id}``, and renders the
 * result in one of four states: loading (skeleton), error (ErrorState),
 * degraded (partial data + warning banner, D9), or loaded (full layout).
 *
 * The component owns its data-fetching lifecycle — the page that hosts it
 * is thin, reading only route params. This keeps the component mountable in
 * a drawer or inline elsewhere without wiring changes.
 */

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import type { ReactElement } from "react";

import { getMediaSheet, type MediaSheetResponse } from "@/api/media";
import { ErrorState } from "@/components/ds/ErrorState";
import { MediaPoster } from "@/components/ds/MediaPoster";
import { StatusBadge } from "@/components/ds/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

/** Props for {@link MediaSheet}. */
export interface MediaSheetProps {
  /** Provider name (``"tmdb"`` / ``"tvdb"``). */
  readonly provider: string;
  /** Provider-specific media identifier. */
  readonly providerId: string;
  /** Optional media kind hint to skip wasted provider probing. */
  readonly kind?: "movie" | "tv";
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map a provider's series status string to a French label + signal tone. */
function seriesStatusLabel(
  status: string,
): { label: string; tone: "success" | "info" | "danger" | "neutral" } {
  switch (status) {
    case "Returning Series":
      return { label: "En cours", tone: "success" };
    case "Ended":
      return { label: "Terminée", tone: "info" };
    case "Canceled":
      return { label: "Annulée", tone: "danger" };
    default:
      return { label: status, tone: "neutral" };
  }
}

/** True when the response carries enough TV-series signals. */
function isTv(data: MediaSheetResponse): boolean {
  return (
    data.series_status !== null ||
    data.episode_count !== null ||
    data.seasons.length > 0
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function MediaSheetSkeleton(): ReactElement {
  return (
    <div
      className="mx-auto max-w-4xl p-4"
      data-testid="media-sheet-loading"
    >
      <div className="flex flex-col gap-6 md:flex-row">
        {/* Poster skeleton */}
        <Skeleton className="aspect-[2/3] w-full shrink-0 rounded-md md:w-64 lg:w-72" />
        <div className="min-w-0 flex-1 space-y-3">
          <Skeleton className="h-7 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-4 w-1/4" />
          <div className="flex gap-1.5">
            <Skeleton className="h-5 w-16 rounded-full" />
            <Skeleton className="h-5 w-20 rounded-full" />
            <Skeleton className="h-5 w-14 rounded-full" />
          </div>
          <Skeleton className="h-20 w-full" />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Degraded warning banner
// ---------------------------------------------------------------------------

function DegradedBanner({
  reason,
}: {
  readonly reason: string;
}): ReactElement {
  return (
    <div
      role="alert"
      className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning"
    >
      <span className="font-medium">Source de données dégradée</span>
      {" — "}
      {reason}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ownership block (D5)
// ---------------------------------------------------------------------------

function OwnershipSection({
  ownership,
  isSeries,
}: {
  readonly ownership: MediaSheetResponse["ownership"];
  readonly isSeries: boolean;
}): ReactElement {
  if (ownership === null) {
    return (
      <div className="rounded-lg border border-dashed border-border p-4">
        <p className="text-sm font-medium">Médiathèque</p>
        <StatusBadge tone="neutral" label="État inconnu" />
        <p className="mt-1 text-xs text-muted-foreground">
          La médiathèque est momentanément inaccessible — impossible de
          déterminer si ce média est possédé.
        </p>
      </div>
    );
  }

  const ownedLabel = ownership.owned ? "Possédé" : "Non possédé";
  const ownedTone = ownership.owned
    ? ("success" as const)
    : ("neutral" as const);

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-center gap-2">
        <p className="text-sm font-medium">Médiathèque</p>
        <StatusBadge tone={ownedTone} label={ownedLabel} />
      </div>

      {isSeries && ownership.seasons.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="pb-1.5 pr-3 font-medium">Saison</th>
                <th className="pb-1.5 pr-3 font-medium">Épisodes</th>
                <th className="pb-1.5 pr-3 font-medium">Possédés</th>
                <th className="pb-1.5 font-medium">Complétude</th>
              </tr>
            </thead>
            <tbody>
              {ownership.seasons.map((s) => {
                const pct =
                  s.episode_count > 0
                    ? Math.round((s.owned_count / s.episode_count) * 100)
                    : 0;
                const complete = s.owned_count >= s.episode_count;
                return (
                  <tr
                    key={s.season_number}
                    className="border-b border-border/50"
                  >
                    <td className="py-1.5 pr-3 font-mono">
                      {s.season_number === 0
                        ? "Spéciaux"
                        : `S${String(s.season_number).padStart(2, "0")}`}
                    </td>
                    <td className="py-1.5 pr-3">{s.episode_count}</td>
                    <td className="py-1.5 pr-3">{s.owned_count}</td>
                    <td className="py-1.5">
                      <StatusBadge
                        tone={complete ? "success" : "warning"}
                        label={
                          complete
                            ? "Complète"
                            : `${pct}%`
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!isSeries && (
        <p className="mt-1 text-xs text-muted-foreground">
          {ownership.owned
            ? "Ce film est présent dans la médiathèque."
            : "Ce film n'est pas encore dans la médiathèque."}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * MediaSheet — the autonomous media detail card.
 *
 * Args:
 *   provider: Provider name.
 *   providerId: Provider-specific media identifier.
 *   kind: Optional kind hint (saves a provider round-trip).
 *
 * Returns:
 *   The media sheet element, in one of four states.
 */
export function MediaSheet({
  provider,
  providerId,
  kind,
}: MediaSheetProps): ReactElement {
  const query = useQuery({
    queryKey: ["media", "sheet", provider, providerId, kind],
    queryFn: () => getMediaSheet(provider, providerId, { kind }),
  });

  // --- Loading ---
  if (query.isLoading) {
    return <MediaSheetSkeleton />;
  }

  // --- Error ---
  if (query.isError) {
    return (
      <div data-testid="media-sheet" className="mx-auto max-w-4xl p-4">
        <ErrorState
          title="Impossible de charger la fiche"
          message={
            query.error instanceof Error
              ? query.error.message
              : "Erreur inconnue"
          }
          onRetry={() => {
            void query.refetch();
          }}
        />
      </div>
    );
  }

  const data = query.data;
  const degraded = data.degraded_reason !== null;
  const series = isTv(data);

  return (
    <div
      data-testid="media-sheet"
      className="mx-auto max-w-4xl p-4"
    >
      {/* --- Degraded warning --- */}
      {degraded && data.degraded_reason !== null && (
        <DegradedBanner reason={data.degraded_reason} />
      )}

      {/* --- Layout: poster + metadata --- */}
      <div className="flex flex-col gap-6 md:flex-row">
        {/* Poster */}
        <div className="w-full shrink-0 md:w-64 lg:w-72">
          <MediaPoster
            title={data.title}
            src={data.poster_url}
            kind={series ? "tv" : "movie"}
          />
        </div>

        {/* Metadata */}
        <div className="min-w-0 flex-1 space-y-4">
          {/* Title + year */}
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              {data.title}
            </h1>
            {data.year !== null && (
              <p className="text-sm text-muted-foreground">{data.year}</p>
            )}
          </div>

          {/* Series status (TV only) */}
          {series && data.series_status !== null && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Statut</span>
              <StatusBadge
                tone={seriesStatusLabel(data.series_status).tone}
                label={seriesStatusLabel(data.series_status).label}
              />
            </div>
          )}

          {/* Director */}
          <div>
            <span className="text-xs text-muted-foreground">Réalisateur</span>
            <p className="text-sm">
              {data.director !== null ? data.director : "Réalisateur inconnu"}
            </p>
          </div>

          {/* Genres */}
          {data.genres.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {data.genres.map((genre) => (
                <Badge key={genre} tone="neutral">
                  {genre}
                </Badge>
              ))}
            </div>
          )}

          {/* Synopsis */}
          {data.overview !== "" && (
            <div>
              <span className="text-xs text-muted-foreground">Synopsis</span>
              <p className="mt-0.5 text-sm leading-relaxed text-foreground/85">
                {data.overview}
              </p>
            </div>
          )}

          {/* Trailer (D10) — only when present */}
          {data.trailer_url !== null && (
            <div>
              <span className="text-xs text-muted-foreground">
                Bande-annonce
              </span>
              <a
                href={data.trailer_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-0.5 flex items-center gap-1 text-sm text-primary underline-offset-2 hover:underline"
              >
                <ExternalLink className="size-3.5" aria-hidden="true" />
                Voir sur YouTube
              </a>
            </div>
          )}

          {/* Series episode count + seasons table (TV only) */}
          {series && (
            <div className="space-y-3">
              {data.episode_count !== null && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">
                    Épisodes
                  </span>
                  <span className="text-sm font-medium">
                    {data.episode_count}
                  </span>
                </div>
              )}

              {data.seasons.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="pb-1.5 pr-3 font-medium">Saison</th>
                        <th className="pb-1.5 font-medium">Épisodes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.seasons.map((s) => (
                        <tr
                          key={s.season_number}
                          className="border-b border-border/50"
                        >
                          <td className="py-1.5 pr-3 font-mono">
                            {s.season_number === 0
                              ? "Spéciaux"
                              : `S${String(s.season_number).padStart(2, "0")}`}
                          </td>
                          <td className="py-1.5">{s.episode_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Ownership (D5) */}
          <OwnershipSection ownership={data.ownership} isSeries={series} />
        </div>
      </div>
    </div>
  );
}
