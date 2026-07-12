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
 * French labels for the well-known live-event classes. Anything unmapped falls
 * back to a de-prefixed, spaced form of the PascalCase class name — never raw
 * JSON or a bare class name (F4).
 */
const EVENT_TYPE_LABEL: Record<string, string> = {
  PipelineStarted: "Pipeline démarré",
  PipelineCompleted: "Pipeline terminé",
  PipelineStepStarted: "Étape démarrée",
  PipelineStepCompleted: "Étape terminée",
  PipelineStepErrored: "Étape en erreur",
  StepStarted: "Étape démarrée",
  StepCompleted: "Étape terminée",
  StepErrored: "Étape en erreur",
  ItemProgressed: "Élément traité",
  CircuitBreakerOpened: "Circuit ouvert",
  CircuitBreakerClosed: "Circuit rétabli",
  CircuitBreakerHalfOpened: "Circuit en test",
  RegistryFanOutCompleted: "Interrogation des fournisseurs",
};

/**
 * Resolve a human-readable French label for an event class — never the raw
 * JSON or a bare ``PascalCase`` class name (F4).
 *
 * Args:
 *   type: The event class name (``EventMessage.type``).
 *
 * Returns:
 *   A curated French label, or a de-prefixed spaced form of the class name.
 */
export function eventTypeLabel(type: string): string {
  const mapped = EVENT_TYPE_LABEL[type];
  if (mapped != null) return mapped;
  const spaced = type
    .replace(/^Pipeline/, "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim();
  return spaced === "" ? type : spaced;
}

/**
 * Salient payload fields, in display priority. The event feed condenses a
 * payload to the first few of these rather than dumping raw JSON.
 */
const SUMMARY_KEYS = [
  "step",
  "item",
  "title",
  "name",
  "status",
  "provider",
  "provider_name",
  "dest",
  "disk",
  "reason",
  "detail",
  "error",
  "count",
];

/**
 * Condense an event payload into a short, human-readable summary instead of raw
 * JSON: the first few salient fields joined by " · " (F4). Falls back to a
 * compact ``key: value`` of the first primitive fields, then ``"—"``.
 *
 * Args:
 *   data: The event payload object.
 *
 * Returns:
 *   A short summary string (never raw JSON).
 */
export function eventSummary(data: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const key of SUMMARY_KEYS) {
    const value = data[key];
    if (typeof value === "string" && value.trim() !== "") parts.push(value);
    else if (typeof value === "number") parts.push(String(value));
    if (parts.length >= 3) break;
  }
  if (parts.length > 0) return parts.join(" · ");
  const entries = Object.entries(data)
    .filter(([, v]) => typeof v === "string" || typeof v === "number")
    .slice(0, 2)
    .map(([k, v]) => `${k}: ${String(v)}`);
  return entries.length > 0 ? entries.join(" · ") : "—";
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
