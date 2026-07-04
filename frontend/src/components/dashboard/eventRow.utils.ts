/**
 * Pure utilities extracted from {@link EventRow} to satisfy the
 * ``react-refresh/only-export-components`` lint rule — the component file must
 * only export components; helper functions live here.
 */

/** The three severity buckets an event type maps to, before DS variant mapping. */
export type Severity = "danger" | "warning" | "neutral";

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
