import type { VariantProps } from "class-variance-authority";
import * as React from "react";

import { badgeVariants } from "@/components/ui/badge-variants";
import { cn } from "@/lib/utils";

/**
 * Semantic badge tone — the subset of {@link badgeVariants} tones reserved for
 * status/outcome signals (healthy/done, error, attention, info, neutral,
 * a dimmer « unknown » muted, and the violet « upcoming » for a future item).
 * Excludes presentational-only tones (``"solid"``, ``"outline"``).
 *
 * ``muted``, ``waiting`` and ``upcoming`` were added for the episode-states
 * matrix so its six per-episode states each read as a DISTINCT tone (operator
 * #9 « une couleur par statut ») : ``muted`` is the colourless dashed ghost of
 * ``non_verifie`` (« je ne sais pas »), ``waiting`` the teal of « En attente de
 * torrent » (searched, nothing conforming yet), and ``upcoming`` the violet
 * accent of an announced, not-yet-aired episode. The three cannot collide with
 * ``info`` (« En cours d'acquisition ») nor with each other — no two states
 * share a hue, and ``muted`` has none at all.
 */
export type BadgeTone =
  | "success"
  | "danger"
  | "warning"
  | "info"
  | "neutral"
  | "muted"
  | "waiting"
  | "upcoming";

/** Props for {@link Badge}. */
export interface BadgeProps
  extends
    React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** Show a leading status dot in the tone colour. @default false */
  readonly dot?: boolean;
}

/**
 * Badge — the compact status / metadata chip of TorrentMate's dense tables and
 * panels (design-system `components/core/Badge`).
 *
 * Semantic tones map to the DS signal palette (success = healthy/done, danger =
 * error/HnR, warning = attention, info = scraping). Pass `mono` for machine
 * values and `dot` for a leading status dot.
 *
 * Args:
 *   tone: Colour tone (default `neutral`).
 *   mono: Use the monospace family (default `false`).
 *   dot: Show a leading status dot (default `false`).
 *
 * Returns:
 *   The badge element.
 */
export function Badge({
  tone,
  mono,
  dot = false,
  className,
  children,
  ...rest
}: BadgeProps): React.JSX.Element {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ tone, mono }), className)}
      {...rest}
    >
      {dot && (
        <span
          className="size-1.5 shrink-0 rounded-full bg-current"
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
