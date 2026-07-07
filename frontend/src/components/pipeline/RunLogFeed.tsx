/**
 * RunLogFeed — a scoped live-log viewer for one pipeline run.
 *
 * Reads the application-wide event stream from {@link useEventStreamContext} and
 * filters to the active run (best-effort via ``data.run_uid``). Each matching
 * event is rendered as a design-system {@link LogLine}: a human-readable
 * ``data.line`` (maintenance ``run_log`` envelopes carry one output line per
 * event) is surfaced verbatim, otherwise the raw JSON payload is dumped. The
 * feed auto-scrolls to the newest event; a "revenir en bas" button appears when
 * the operator scrolls up.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactElement,
  type UIEvent,
} from "react";

import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import { LogLine, type LogLevel } from "@/components/ds/LogLine";

import {
  formatEventTime,
  severityForEventType,
  type Severity,
} from "@/components/dashboard/eventRow.utils";

/** Distance from the bottom, in px, still considered "at the tail" (auto-follow). */
const FOLLOW_THRESHOLD = 24;

/**
 * How each severity bucket maps to a {@link LogLine} level.
 *
 * ``danger`` → ``error``, ``warning`` → ``warn``, ``neutral`` → ``info``.
 * We don't render a StatusDot here (unlike EventRow) because the feed is
 * already scoped to one run — the level colour alone is the signal.
 */
const SEVERITY_LEVEL: Record<Severity, LogLevel> = {
  danger: "error",
  warning: "warn",
  neutral: "info",
};

/** Props for {@link RunLogFeed}. */
export interface RunLogFeedProps {
  /**
   * The run identifier to filter events by.
   *
   * When non-null, only events whose ``data.run_uid`` (or ``data.run_id``)
   * matches are shown. When ``null`` or ``undefined``, all events are shown
   * (the single-trigger invariant means only one run is active at a time).
   */
  readonly runUid?: string | null | undefined;
}

/**
 * Best-effort filter predicate: does the event carry the given run identifier?
 *
 * The {@link import("@/api/events").EventMessage.data} payload is opaque
 * (``Record<string, unknown>``), so we probe the two common key names. If the
 * event shape has no run identifier, the single-trigger invariant applies —
 * all events belong to the sole active run.
 *
 * Args:
 *   data: The event payload.
 *   uid: The run identifier to match, or ``null``/``undefined`` to accept all.
 *
 * Returns:
 *   ``true`` when the event should be shown.
 */
function eventMatchesRun(
  data: Record<string, unknown>,
  uid: string | null | undefined,
): boolean {
  if (uid == null) {
    return true;
  }
  const runUid = data.run_uid;
  if (typeof runUid === "string") {
    return runUid === uid;
  }
  const runId = data.run_id;
  if (typeof runId === "string") {
    return runId === uid;
  }
  // Event payload carries no run identifier — show everything.
  return true;
}

/**
 * RunLogFeed — scoped live log for the current or past pipeline run.
 *
 * Args:
 *   runUid: Optional run identifier to filter events.
 *
 * Returns:
 *   The log feed element.
 */
export function RunLogFeed({ runUid }: RunLogFeedProps): ReactElement {
  const { events } = useEventStreamContext();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoFollow, setAutoFollow] = useState(true);

  // Respect prefers-reduced-motion: when set, skip the smooth auto-scroll and
  // use an instant jump so the user is not disoriented by motion they can't see.
  // Guarded for jsdom where matchMedia may not exist.
  const prefersReducedMotion = useRef(
    ((): boolean => {
      try {
        return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      } catch {
        return false;
      }
    })(),
  );

  // Filter to the active run.
  const filtered = events.filter((e) => eventMatchesRun(e.data, runUid));

  // Auto-scroll to bottom whenever a new event arrives and follow is on.
  useEffect(() => {
    if (autoFollow && filtered.length > 0 && scrollRef.current) {
      const el = scrollRef.current;
      if (prefersReducedMotion.current) {
        el.scrollTop = el.scrollHeight;
      } else {
        el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
      }
    }
  }, [autoFollow, filtered.length]);

  // Re-evaluate follow on every scroll.
  const handleScroll = useCallback((event: UIEvent<HTMLDivElement>): void => {
    const el = event.currentTarget;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoFollow(distanceFromBottom <= FOLLOW_THRESHOLD);
  }, []);

  const scrollToBottom = useCallback((): void => {
    setAutoFollow(true);
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  const isEmpty = filtered.length === 0;

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold tracking-tight">
          Journal d&rsquo;exécution
        </h2>
        {!autoFollow && !isEmpty && (
          <button
            type="button"
            onClick={scrollToBottom}
            className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            Revenir en bas
          </button>
        )}
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-label="Journal d'exécution du pipeline"
        className="h-80 overflow-y-auto rounded-lg border border-border bg-card p-2 md:h-[28rem]"
      >
        {isEmpty ? (
          <p className="flex h-full items-center justify-center text-xs text-muted-foreground">
            Aucun log pour cette exécution.
          </p>
        ) : (
          <div className="flex flex-col gap-px">
            {filtered.map((event) => {
              const severity = severityForEventType(event.type);
              const level = SEVERITY_LEVEL[severity];
              const time = formatEventTime(event.id);
              // Prefer a human-readable ``data.line`` (maintenance ``run_log``
              // envelopes carry one output line per event) over the raw JSON
              // payload; fall back to the JSON dump for structured pipeline
              // events that have no ``line`` field. Backward-compatible: events
              // without a string ``line`` render exactly as before.
              const line =
                typeof event.data.line === "string" ? event.data.line : null;

              return (
                <LogLine key={event.id} level={level} time={time}>
                  <span className="font-medium">{event.type}</span>
                  {" — "}
                  <span className="text-muted-foreground">
                    {line ?? JSON.stringify(event.data)}
                  </span>
                </LogLine>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
