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

import {
  eventSummary,
  eventTypeLabel,
  formatEventTime,
  severityForEventType,
  type Severity,
} from "./eventRow.utils";

/** Max characters of the JSON payload preview before it is ellipsized. */
const PREVIEW_MAX_CHARS = 120;

/**
 * How each severity renders across the two DS primitives used by a row.
 *
 * ``dot`` drives the {@link StatusDot} colour; ``level`` drives the
 * {@link LogLine} level colour + code. A feed row is a *completed, historical*
 * event, so ``neutral`` (the vast majority) maps to the static ``idle`` dot
 * rather than the lifecycle ``queued`` — which reads as "pending" and is wrong
 * for a settled event (audit B9). ``warning`` maps to the static amber
 * ``warning`` dot (not the animated ``running`` amber) so it still draws the eye
 * without pulsing forever on a settled row.
 */
const SEVERITY_DISPLAY: Record<
  Severity,
  { readonly dot: PipelineStatus; readonly level: LogLevel }
> = {
  danger: { dot: "error", level: "error" },
  warning: { dot: "warning", level: "warn" },
  neutral: { dot: "idle", level: "info" },
};

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
        <span className="font-medium whitespace-nowrap" title={event.type}>
          {eventTypeLabel(event.type)}
        </span>
        <span
          className="min-w-0 flex-1 truncate text-muted-foreground"
          title={previewData(event.data)}
        >
          {eventSummary(event.data)}
        </span>
      </span>
    </LogLine>
  );
}
