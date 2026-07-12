import { Clapperboard, Film, Tv } from "lucide-react";
import { useState, type ReactElement } from "react";

import { cn } from "@/lib/utils";

/** Props for {@link MediaPoster} (conforms to the DS MediaPoster contract). */
export interface MediaPosterProps {
  /** The media title — used as the image alt + initials fallback. */
  readonly title: string;
  /** Poster URL (http/https). When absent or broken, an initials fallback shows. */
  readonly src?: string | null;
  /** Media kind, surfaced as a corner chip when given. */
  readonly kind?: "movie" | "tv";
  /** Optional extra classes on the aspect box. */
  readonly className?: string;
}

/** Derive up to two uppercase initials from a title for the fallback. */
function initialsOf(title: string): string {
  const words = title.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const first = words[0]?.charAt(0) ?? "";
  const second = words.length > 1 ? (words[1]?.charAt(0) ?? "") : "";
  return (first + second).toUpperCase();
}

/**
 * MediaPoster — an aspect-2/3 poster with a graceful initials fallback.
 *
 * Renders the provider poster when available; on a missing or broken URL it
 * degrades to the media's initials over a muted gradient (never a broken-image
 * icon). Images are lazy-loaded. An optional ``kind`` chip labels film/série.
 *
 * Args:
 *   title: The media title (image alt + fallback initials).
 *   src: Poster URL, or ``null``/absent for the fallback.
 *   kind: Optional media kind for the corner chip.
 *   className: Optional extra classes.
 *
 * Returns:
 *   The poster element.
 */
export function MediaPoster({
  title,
  src,
  kind,
  className,
}: MediaPosterProps): ReactElement {
  const [broken, setBroken] = useState(false);
  const showImage = src != null && src !== "" && !broken;
  const FallbackIcon =
    kind === "movie" ? Film : kind === "tv" ? Tv : Clapperboard;

  return (
    <div
      className={cn(
        "relative aspect-[2/3] w-full overflow-hidden rounded-md bg-muted",
        className,
      )}
    >
      {showImage ? (
        <img
          src={src}
          alt={title}
          loading="lazy"
          className="size-full object-cover"
          onError={() => {
            setBroken(true);
          }}
        />
      ) : (
        <div
          className="relative flex size-full items-center justify-center overflow-hidden bg-gradient-to-br from-accent/50 via-card to-muted"
          aria-label={title}
          role="img"
        >
          {/* Faint media-kind watermark so a poster-less card reads as designed,
              not empty — the initials sit above it. */}
          <FallbackIcon
            className="absolute -bottom-4 -right-3 size-2/3 text-foreground/[0.05]"
            strokeWidth={1.25}
            aria-hidden
          />
          <span className="relative font-mono text-3xl font-semibold tracking-tight text-muted-foreground/90">
            {initialsOf(title)}
          </span>
        </div>
      )}
      {kind !== undefined && (
        <span className="absolute left-1.5 top-1.5 rounded bg-background/80 px-1.5 py-0.5 text-xs font-medium text-foreground backdrop-blur-sm">
          {kind === "movie" ? "Film" : "Série"}
        </span>
      )}
    </div>
  );
}
