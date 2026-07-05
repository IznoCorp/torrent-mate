/**
 * Virtualized live-event feed for the dashboard (tm-shell §5.3).
 *
 * A scrollable, newest-at-bottom list of {@link EventRow}s over the event ring,
 * rendered through **TanStack Virtual** so a 10 000-entry history stays at 60 fps
 * (only the visible window is in the DOM). The feed auto-follows the tail; the
 * follow pauses automatically when the operator scrolls up to inspect history and
 * resumes when they scroll back down (or press the follow toggle).
 */

import { useVirtualizer } from "@tanstack/react-virtual";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactElement,
  type UIEvent,
} from "react";

import type { EventMessage } from "@/api/events";
import { EventRow } from "@/components/dashboard/EventRow";

/** Fixed row height, in px — a constant estimate keeps virtualization cheap. */
const ROW_HEIGHT = 28;
/** Overscan rows above/below the viewport to avoid blank flashes on fast scroll. */
const OVERSCAN = 8;
/** Distance from the bottom, in px, still considered "at the tail" (auto-follow). */
const FOLLOW_THRESHOLD = 24;

/** Props for {@link EventFeed}. */
export interface EventFeedProps {
  /** The bounded, append-ordered event ring (oldest first, newest last). */
  readonly events: readonly EventMessage[];
}

/**
 * EventFeed — the dashboard's live, virtualized event stream.
 *
 * Args:
 *   events: The event ring to render (from ``useEventStreamContext``); the
 *     newest event is the last element and shows at the bottom.
 *
 * Returns:
 *   The feed element (header with a follow toggle + a virtualized scroll region).
 */
export function EventFeed({ events }: EventFeedProps): ReactElement {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoFollow, setAutoFollow] = useState(true);

  const rowVirtualizer = useVirtualizer({
    count: events.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: OVERSCAN,
  });

  // While following, pin the viewport to the newest event as the ring grows.
  useEffect(() => {
    if (autoFollow && events.length > 0) {
      rowVirtualizer.scrollToIndex(events.length - 1, { align: "end" });
    }
  }, [autoFollow, events.length, rowVirtualizer]);

  // Re-evaluate follow on every scroll: near the bottom → follow, scrolled up →
  // pause. Reading layout metrics off the event target keeps this allocation-free.
  const handleScroll = useCallback((event: UIEvent<HTMLDivElement>): void => {
    const el = event.currentTarget;
    const distanceFromBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoFollow(distanceFromBottom <= FOLLOW_THRESHOLD);
  }, []);

  const items = rowVirtualizer.getVirtualItems();

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-tight">
          Flux d’événements
        </h2>
        <button
          type="button"
          aria-pressed={autoFollow}
          onClick={() => {
            setAutoFollow(true);
          }}
          disabled={autoFollow}
          className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:opacity-60"
        >
          {autoFollow ? "Suivi auto activé" : "Reprendre le suivi"}
        </button>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-label="Flux d’événements en direct"
        className="h-80 overflow-y-auto rounded-lg border border-border bg-card md:h-[28rem]"
      >
        {events.length === 0 ? (
          <p className="p-4 text-center text-xs text-muted-foreground">
            En attente d’événements…
          </p>
        ) : (
          <div
            className="relative w-full"
            style={{ height: `${String(rowVirtualizer.getTotalSize())}px` }}
          >
            {items.map((virtualRow) => {
              const event = events[virtualRow.index];
              if (event === undefined) {
                return null;
              }
              return (
                <div
                  key={event.id}
                  className="absolute left-0 top-0 w-full"
                  style={{
                    height: `${String(virtualRow.size)}px`,
                    transform: `translateY(${String(virtualRow.start)}px)`,
                  }}
                >
                  <EventRow event={event} />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
