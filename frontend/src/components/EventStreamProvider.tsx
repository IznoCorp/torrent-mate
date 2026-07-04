/**
 * Application-wide live-event stream context for TorrentMateUI (tm-shell §5.3).
 *
 * `EventStreamProvider` owns the app's **single** WebSocket by mounting
 * {@link useEventStream} exactly once, and republishes its reactive state to
 * every descendant through React context. This provider is the public seam: the
 * TopBar's connection {@link StatusDot} and the dashboard's live feed both read
 * the *same* socket via {@link useEventStreamContext} — no component opens its
 * own connection.
 *
 * Mount boundary: it lives **inside** the authenticated shell (see
 * `AppShell.tsx`), so the login page never opens a socket and the connection's
 * lifetime tracks the authenticated session.
 */

import {
  createContext,
  useContext,
  type ReactElement,
  type ReactNode,
} from "react";

import { useEventStream, type EventStreamState } from "@/hooks/useEventStream";

/** Context handle; ``null`` until an {@link EventStreamProvider} is mounted above. */
const EventStreamContext = createContext<EventStreamState | null>(null);

/**
 * Provide the app-wide event-stream context by mounting the WebSocket hook once.
 *
 * Args:
 *   children: The authenticated subtree that reads the stream via
 *     {@link useEventStreamContext} (the shell and every page it renders).
 *
 * Returns:
 *   The provider element wrapping ``children``.
 */
export function EventStreamProvider({
  children,
}: {
  children: ReactNode;
}): ReactElement {
  const value = useEventStream();
  return (
    <EventStreamContext.Provider value={value}>
      {children}
    </EventStreamContext.Provider>
  );
}

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
      "useEventStreamContext doit être appelé à l’intérieur de <EventStreamProvider>.",
    );
  }
  return context;
}
