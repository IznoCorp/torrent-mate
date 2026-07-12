import type { ReactElement } from "react";

import { BRAND_ICON } from "@/lib/env";
import { cn } from "@/lib/utils";

/** Props for {@link BrandMark}. */
export interface BrandMarkProps {
  /** Extra classes for sizing/spacing (defaults to a 28px square). */
  readonly className?: string;
}

/**
 * BrandMark — the TorrentMate logo, sourced from the environment-aware
 * {@link BRAND_ICON} (prod vs staging variant).
 *
 * The single place a raw brand ``<img>`` lives in product code: everywhere else
 * renders ``<BrandMark />`` so the DS owns the one brand-image element (see the
 * ``lint:ds`` ``react/forbid-elements`` rule forbidding raw ``<img>``). Purely
 * decorative — ``alt=""`` so screen readers skip it.
 *
 * Args:
 *   className: Optional sizing/spacing classes (default ``size-7``).
 *
 * Returns:
 *   The brand image element.
 */
export function BrandMark({ className }: BrandMarkProps): ReactElement {
  return <img src={BRAND_ICON} alt="" className={cn("size-7", className)} />;
}
