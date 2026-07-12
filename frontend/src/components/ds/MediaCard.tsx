import type { ReactElement, ReactNode } from "react";

import { MediaPoster } from "@/components/ds/MediaPoster";
import { cn } from "@/lib/utils";

/** Props for {@link MediaCard}. */
export interface MediaCardProps {
  /** Media title. */
  readonly title: string;
  /** Release year, when known. */
  readonly year?: number | null;
  /** Media kind (poster corner chip). */
  readonly kind?: "movie" | "tv";
  /** Poster URL, or absent for the initials fallback. */
  readonly posterUrl?: string | null;
  /** Optional plot summary (line-clamped to 3 lines). */
  readonly overview?: string | null;
  /** Optional chips slot under the title (ids, score, état…). */
  readonly badges?: ReactNode;
  /** Optional actions slot rendered below the meta, outside the click region. */
  readonly footer?: ReactNode;
  /** Highlight the card as selected (ring). */
  readonly selected?: boolean;
  /** When given, the poster+meta region becomes a button firing this. */
  readonly onOpen?: () => void;
  /**
   * Layout density (C17). ``"compact"`` tightens the meta padding and hides the
   * overview so more cards fit per row; ``"comfortable"`` (default) keeps the
   * full card. The grid column count is the caller's responsibility.
   */
  readonly density?: "comfortable" | "compact";
}

/**
 * MediaCard — the catalog card used by the library, search results, candidates,
 * and the watch list: a poster hero over title/year, an optional overview, a
 * chips slot, and an optional actions footer.
 *
 * The poster+meta region is a single button when ``onOpen`` is provided (so the
 * whole card opens the media); the ``footer`` sits outside that button to avoid
 * nested interactive controls.
 *
 * Args:
 *   title, year, kind, posterUrl, overview: The media fields.
 *   badges: Optional chips under the title.
 *   footer: Optional actions below the meta.
 *   selected: Highlight ring.
 *   onOpen: Optional open handler (makes the card region a button).
 *
 * Returns:
 *   The media card element.
 */
export function MediaCard({
  title,
  year,
  kind,
  posterUrl,
  overview,
  badges,
  footer,
  selected = false,
  onOpen,
  density = "comfortable",
}: MediaCardProps): ReactElement {
  const isCompact = density === "compact";
  const meta = (
    <>
      <MediaPoster
        title={title}
        src={posterUrl ?? null}
        {...(kind !== undefined ? { kind } : {})}
      />
      <div className={cn("flex flex-col gap-1", isCompact ? "p-2" : "p-3")}>
        <div className="flex items-baseline justify-between gap-2">
          <span className="line-clamp-2 text-sm font-medium">{title}</span>
          {year != null && (
            <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
              {year}
            </span>
          )}
        </div>
        {badges !== undefined && (
          <div className="flex flex-wrap items-center gap-1">{badges}</div>
        )}
        {/* Compact hides the overview so more cards fit per row (C17). */}
        {!isCompact && overview != null && overview !== "" && (
          <p className="line-clamp-3 text-xs text-muted-foreground">
            {overview}
          </p>
        )}
      </div>
    </>
  );

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-lg border bg-card transition-colors",
        selected ? "border-primary ring-2 ring-primary" : "border-border",
      )}
    >
      {onOpen !== undefined ? (
        <button
          type="button"
          onClick={onOpen}
          className="flex flex-col text-left transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {meta}
        </button>
      ) : (
        <div className="flex flex-col">{meta}</div>
      )}
      {footer !== undefined && (
        <div className="mt-auto flex items-center gap-2 border-t border-border p-2">
          {footer}
        </div>
      )}
    </div>
  );
}
