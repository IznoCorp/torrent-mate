/**
 * InterpretedRunFeed — the default, human-readable run narrative.
 *
 * Reads the app-wide event stream ({@link useEventStreamContext}), filters to
 * the active run (by ``data.run_uid`` / ``data.run_id``), folds the events into
 * plain-French lines via {@link interpretRun}, and renders them as a scrollable
 * list. This is the DEFAULT Pipeline view (webui-ux Phase 2.3); the raw WS
 * ``RunLogFeed`` moves inside a collapsed accordion below.
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactElement,
  type UIEvent,
} from "react";

import type { EventMessage } from "@/api/events";
import { useEventStreamContext } from "@/hooks/useEventStreamContext";
import {
  interpretRun,
  type InterpretedLine,
  type LineTone,
} from "@/components/pipeline/interpretRun";

/** Distance from the bottom, in px, still considered "at the tail" (auto-follow). */
const FOLLOW_THRESHOLD = 24;

/** Tone → text colour class for an interpreted line. */
const TONE_CLASS: Record<LineTone, string> = {
  info: "text-muted-foreground",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};

/** Props for {@link InterpretedRunFeed}. */
export interface InterpretedRunFeedProps {
  /**
   * The run identifier to filter events by. When ``null``/``undefined`` all
   * events are interpreted (the single-active-run invariant).
   */
  readonly runUid?: string | null | undefined;
  /**
   * Optional pre-computed lines (used for the idle "last run" summary that is
   * fed from the persisted history instead of the live WS stream). When set,
   * the live-event path is bypassed entirely.
   */
  readonly lines?: readonly InterpretedLine[];
  /** Accessible label / heading for the feed region. */
  readonly label?: string;
}

/**
 * Best-effort run filter: does the event belong to the given run?
 *
 * Args:
 *   data: The opaque event payload.
 *   uid: The run identifier, or ``null``/``undefined`` to accept all.
 *
 * Returns:
 *   ``true`` when the event should be interpreted for this run.
 */
function eventMatchesRun(
  data: Record<string, unknown>,
  uid: string | null | undefined,
): boolean {
  if (uid == null) return true;
  const runUid = data.run_uid;
  if (typeof runUid === "string") return runUid === uid;
  const runId = data.run_id;
  if (typeof runId === "string") return runId === uid;
  return true;
}

/**
 * InterpretedRunFeed — interpreted run narrative (live or pre-computed).
 *
 * Args:
 *   runUid: Optional run identifier to filter the live stream.
 *   lines: Optional pre-computed lines (idle last-run summary path).
 *   label: Optional heading text.
 *
 * Returns:
 *   The interpreted-feed element.
 */
export function InterpretedRunFeed({
  runUid,
  lines: precomputed,
  label = "Résumé de l'exécution",
}: InterpretedRunFeedProps): ReactElement {
  const { events } = useEventStreamContext();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoFollow, setAutoFollow] = useState(true);

  // Live path: filter to the run and fold. When `precomputed` is supplied it
  // wins (idle summary from persisted history) and the live stream is ignored.
  const liveLines: InterpretedLine[] =
    precomputed !== undefined
      ? [...precomputed]
      : interpretRun(
          events.filter((e: EventMessage) => eventMatchesRun(e.data, runUid)),
        );

  useEffect(() => {
    if (autoFollow && liveLines.length > 0 && scrollRef.current) {
      const el = scrollRef.current;
      el.scrollTop = el.scrollHeight;
    }
  }, [autoFollow, liveLines.length]);

  const handleScroll = useCallback((event: UIEvent<HTMLDivElement>): void => {
    const el = event.currentTarget;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoFollow(distanceFromBottom <= FOLLOW_THRESHOLD);
  }, []);

  const isEmpty = liveLines.length === 0;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold tracking-tight">{label}</h2>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-label={label}
        className="h-80 overflow-y-auto rounded-lg border border-border bg-card p-3 md:h-[28rem]"
      >
        {isEmpty ? (
          <p className="flex h-full items-center justify-center text-xs text-muted-foreground">
            Aucune activité à afficher pour le moment.
          </p>
        ) : (
          <ol className="flex flex-col gap-1">
            {liveLines.map((line, index) => (
              <li
                key={`${String(index)}-${line.step}`}
                className={`text-sm leading-snug ${TONE_CLASS[line.tone]}`}
              >
                {line.text}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
