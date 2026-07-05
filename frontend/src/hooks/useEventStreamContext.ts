/**
 * Application-wide live-event stream context handle for TorrentMateUI
 * (tm-shell §5.3).
 *
 * The React context ({@link EventStreamContext}) and its consumer hook
 * ({@link useEventStreamContext}) live here so the component file
 * ({@link EventStreamProvider}) only exports the component — satisfying the
 * ``react-refresh/only-export-components`` rule.
 *
 * The provider owns the app's **single** WebSocket by mounting
 * {@link useEventStream} exactly once, and republishes its reactive state to
 * every descendant through React context. This provider is the public seam: the
 * TopBar's connection {@link StatusDot} and the dashboard's live feed both read
 * the *same* socket via {@link useEventStreamContext} — no component opens its
 * own connection.
 */

import { createContext, useContext } from "react";

import type { EventStreamState } from "@/hooks/useEventStream";

/** Context handle; ``null`` until an {@link EventStreamProvider} is mounted above. */
export const EventStreamContext = createContext<EventStreamState | null>(null);

/**
 * Read the app-wide event-stream context.
 *
 * Returns:
 *   The current {@link EventStreamState} (events, connection state, build commit,
 *   last cursor).
 *
 * Raises:
 *   Error: When called outside an {@link EventStreamProvider} subtree (a
 *     programming error — the provider wraps the authenticated shell).
 */
export function useEventStreamContext(): EventStreamState {
  const context = useContext(EventStreamContext);
  if (context === null) {
    throw new Error(
      "useEventStreamContext doit être appelé à l'intérieur de <EventStreamProvider>.",
    );
  }
  return context;
}
