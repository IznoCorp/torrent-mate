/**
 * MediaSheetPage — thin route host for the autonomous {@link MediaSheet} component.
 *
 * Reads ``provider`` and ``providerId`` from the route params and the optional
 * ``kind`` hint from the query string, then mounts the component. The page
 * itself carries no data logic — the component owns its fetch lifecycle so it
 * can later be mounted in a drawer or inline elsewhere without wiring changes
 * (DESIGN D7).
 */

import type { ReactElement } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { MediaSheet } from "@/components/media/MediaSheet";

/**
 * MediaSheetPage — the route-level entry for ``/media/:provider/:providerId``.
 *
 * Returns:
 *   The media sheet element.
 */
export default function MediaSheetPage(): ReactElement {
  const { provider, providerId } = useParams<{
    provider: string;
    providerId: string;
  }>();
  const [searchParams] = useSearchParams();
  const kindParam = searchParams.get("kind");

  // Only accept known kind values — anything else falls through to no-hint.
  const kind: "movie" | "tv" | undefined =
    kindParam === "movie" || kindParam === "tv" ? kindParam : undefined;

  // Params are guaranteed present by the route pattern; this is a defensive
  // gate only — a malformed URL reaching here would crash anyway.
  if (provider === undefined || providerId === undefined) {
    return <div data-testid="media-sheet" />;
  }

  return (
    <MediaSheet provider={provider} providerId={providerId} kind={kind} />
  );
}
