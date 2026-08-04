/**
 * Shared display metadata for the staging read-model surfaces (OBJ2A).
 *
 * Small pure mappers used by both the library grid cards and the detail drawer
 * so the match verdict, media kind, and dispatch mode read consistently.
 */

import type { StagingMediaItem } from "@/api/staging";
import type { StatusTone } from "@/components/ds/StatusBadge";
import { mediaSheetHref } from "@/lib/media-href";

/** Matching verdict → status chip tone + French label. */
export function matchBadge(
  match: StagingMediaItem["match"],
): { tone: StatusTone; label: string } {
  switch (match) {
    case "matched":
      return { tone: "success", label: "Identifié" };
    case "ambiguous":
      return { tone: "warning", label: "À résoudre" };
    default:
      return { tone: "neutral", label: "Non identifié" };
  }
}

/** Map a read-model media kind to the {@link MediaPoster} kind chip, or undefined. */
export function posterKind(
  kind: StagingMediaItem["media_kind"],
): "movie" | "tv" | undefined {
  if (kind === "movie") return "movie";
  if (kind === "tvshow") return "tv";
  return undefined;
}

/** Human-readable French media-kind label. */
export function kindLabel(kind: StagingMediaItem["media_kind"]): string {
  const labels: Record<StagingMediaItem["media_kind"], string> = {
    movie: "Film",
    tvshow: "Série",
    ebook: "Livre",
    audio: "Audio",
    app: "Application",
    other: "Autre",
    unsorted: "Non trié",
  };
  return labels[kind];
}

/** Dispatch-mode → French label for the dispatch-target preview. */
export function dispatchLabel(
  mode: NonNullable<StagingMediaItem["dispatch_target"]>["mode"],
): string {
  switch (mode) {
    case "replace":
      return "Remplacement";
    case "merge":
      return "Fusion";
    case "new":
      return "Nouveau";
    default:
      return "Indéterminé";
  }
}

// Compact byte-size formatter — re-exported from the single `lib/format`
// owner (ACC-10).
export { formatSize } from "@/lib/format";

/**
 * Derive a media-sheet href from a staged media item's provider ids.
 *
 * Priority: tvdb > tmdb.  Returns ``null`` when no provider id is known
 * (§11 exception — an unidentified media must lead to resolution, never a
 * dead link).
 *
 * Args:
 *   item: A staged media read-model item.
 *
 * Returns:
 *   A media sheet href, or ``null`` when ``provider_ids`` is empty or has no
 *   recognised provider.
 */
export function stagingMediaSheetHref(
  item: StagingMediaItem,
): string | null {
  const ids = item.provider_ids;
  if (Object.keys(ids).length === 0) return null;
  const kind =
    item.media_kind === "movie"
      ? ("movie" as const)
      : item.media_kind === "tvshow"
        ? ("tv" as const)
        : undefined;
  // Priority: tvdb > tmdb (imdb has no sheet route).
  if (ids.tvdb) {
    return mediaSheetHref({
      provider: "tvdb",
      providerId: ids.tvdb,
      ...(kind !== undefined ? { kind } : {}),
    });
  }
  if (ids.tmdb) {
    return mediaSheetHref({
      provider: "tmdb",
      providerId: ids.tmdb,
      ...(kind !== undefined ? { kind } : {}),
    });
  }
  return null;
}
