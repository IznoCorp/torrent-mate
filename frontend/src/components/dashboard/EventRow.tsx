/**
 * A single live-event row for the dashboard feed (tm-shell §5.3).
 *
 * Renders one {@link EventMessage} as a design-system {@link LogLine}: a
 * monospace, tabular-numeral timestamp, the level short-code, and — inside the
 * message slot — a {@link StatusDot} severity signal, the event-type label, and
 * a truncated JSON preview of the payload. The row is a fixed single line so the
 * virtualized feed can measure it with a constant height.
 */

import type { ReactElement } from "react";

import type { EventMessage } from "@/api/events";
import { LogLine, type LogLevel } from "@/components/ds/LogLine";
import { StatusDot, type PipelineStatus } from "@/components/ds/StatusDot";

/** Max characters of the JSON payload preview before it is ellipsized. */
const PREVIEW_MAX_CHARS = 120;

/** The three severity buckets an event type maps to, before DS variant mapping. */
type Severity = "danger" | "warning" | "neutral";

/**
 * How each severity renders across the two DS primitives used by a row.
 *
 * ``dot`` drives the {@link StatusDot} colour (danger→red, warning→amber,
 * neutral→info blue); ``level`` drives the {@link LogLine} level colour + code.
 */
const SEVERITY_DISPLAY: Record<
  Severity,
  { readonly dot: PipelineStatus; readonly level: LogLevel }
> = {
  danger: { dot: "error", level: "error" },
  warning: { dot: "running", level: "warn" },
  neutral: { dot: "queued", level: "info" },
};

/**
 * Classify an event type into a severity bucket by name convention.
 *
 * The engine's event classes are ``PascalCase`` (e.g. ``PipelineStepStarted``,
 * ``PipelineStepErrored``). Anything naming a failure/error is ``danger``, a
 * warning is ``warning``, everything else is ``neutral`` (informational).
 *
 * Args:
 *   type: The event class name (``EventMessage.type``).
 *
 * Returns:
 *   The severity bucket for the type.
 */
export function severityForEventType(type: string): Severity {
  if (/error|errored|failed|failure/i.test(type)) {
    return "danger";
  }
  if (/warn|warning/i.test(type)) {
    return "warning";
  }
  return "neutral";
}

/**
 * Format the Redis-stream cursor id as a wall-clock ``HH:MM:SS`` timestamp.
 *
 * A stream id is ``"<unix-ms>-<seq>"``; the millisecond prefix is the event's
 * ingestion time, so we derive the row timestamp from it (no separate field to
 * trust). A malformed id degrades to ``"--:--:--"``.
 *
 * Args:
 *   id: The stream cursor id (``EventMessage.id``).
 *
 * Returns:
 *   The 24-hour ``HH:MM:SS`` time string, or ``"--:--:--"`` when unparseable.
 */
export function formatEventTime(id: string): string {
  const [msPart] = id.split("-");
  const ms = Number(msPart);
  if (!Number.isFinite(ms)) {
    return "--:--:--";
  }
  return new Date(ms).toLocaleTimeString("fr-FR", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Serialize the payload to a compact, length-capped preview string. */
function previewData(data: Record<string, unknown>): string {
  const json = JSON.stringify(data);
  if (json.length <= PREVIEW_MAX_CHARS) {
    return json;
  }
  return `${json.slice(0, PREVIEW_MAX_CHARS)}…`;
}

/** Props for {@link EventRow}. */
export interface EventRowProps {
  /** The event to render as one feed row. */
  readonly event: EventMessage;
}

/**
 * EventRow — one {@link LogLine} row for a live domain event.
 *
 * Args:
 *   event: The {@link EventMessage} to render.
 *
 * Returns:
 *   The single-line feed row element.
 */
export function EventRow({ event }: EventRowProps): ReactElement {
  const severity = severityForEventType(event.type);
  const display = SEVERITY_DISPLAY[severity];

  return (
    <LogLine level={display.level} time={formatEventTime(event.id)}>
      <span className="flex min-w-0 items-center gap-2">
        <StatusDot status={display.dot} showLabel={false} />
        <span className="font-medium whitespace-nowrap">{event.type}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground">
          {previewData(event.data)}
        </span>
      </span>
    </LogLine>
  );
}
