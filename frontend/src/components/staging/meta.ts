/**
 * Shared display metadata for the staging read-model surfaces (OBJ2A).
 *
 * Small pure mappers used by both the library grid cards and the detail drawer
 * so the match verdict, media kind, and dispatch mode read consistently.
 */

import type { StagingMediaItem } from "@/api/staging";
import type { StatusTone } from "@/components/ds/StatusBadge";

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
