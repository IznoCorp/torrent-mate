import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Skeleton — an animated placeholder for loading content.
 *
 * Renders a pulsing rounded rectangle that inherits the muted background colour.
 * Compose with Tailwind sizing utilities (``className="h-4 w-48"``) to match the
 * shape of the content it replaces.
 *
 * @param className Additional classes forwarded to the wrapper ``<div>``.
 */
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>): React.ReactNode {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}

export { Skeleton };
