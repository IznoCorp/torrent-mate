/**
 * Shared trigger label + tone maps for the decision components.
 *
 * Single source of truth imported by {@link DecisionList} and
 * {@link DecisionDetail} so a new backend trigger only needs one edit
 * (coherence study F50 — the two components previously duplicated these maps
 * with a comment-enforced "keep in sync").
 */

/** Trigger reason → short French label (chips). */
export const TRIGGER_LABEL: Record<string, string> = {
  below_threshold: "Score faible",
  mid_band: "Zone grise",
  ambiguous: "Ambigu",
};

/** Trigger reason → DS Badge tone. */
export const TRIGGER_TONE: Record<string, "danger" | "warning" | "info"> = {
  below_threshold: "danger",
  mid_band: "warning",
  ambiguous: "info",
};

// ---------------------------------------------------------------------------
// Decision status presentation (§4.1 relabel).
//
// PRESENTATION ONLY — the backend ``status`` enum values
// (``pending``/``resolved``/``dismissed``/``superseded``) are UNCHANGED. The
// operator found ``dismissed``/``superseded`` confusing, so the two ambiguous
// states get an explicit, self-documenting French label + a ``title=`` tooltip
// explaining what actually happened to the folder.
// ---------------------------------------------------------------------------

/** The closed set of backend decision statuses (matches the API Literal). */
export type DecisionStatus =
  | "pending"
  | "resolved"
  | "dismissed"
  | "superseded";

/**
 * Status → full French label (row badges + detail).
 *
 * ``dismissed`` and ``superseded`` are spelled out because the raw words are
 * ambiguous to the operator.
 */
export const STATUS_LABEL: Record<DecisionStatus, string> = {
  pending: "En attente",
  resolved: "Résolue",
  dismissed: "Ignorée (laissée telle quelle)",
  superseded: "Remplacée (re-scrapée depuis)",
};

/**
 * Status → short French label (compact filter chips).
 *
 * The filter chips stay terse; the full disambiguating label lives on the row
 * badge and the chip ``title`` tooltip.
 */
export const STATUS_SHORT_LABEL: Record<DecisionStatus, string> = {
  pending: "En attente",
  resolved: "Résolues",
  dismissed: "Ignorées",
  superseded: "Remplacées",
};

/** Status → tooltip (``title=``) explaining what happened to the folder. */
export const STATUS_TOOLTIP: Record<DecisionStatus, string> = {
  pending: "En attente d'une décision de l'opérateur.",
  resolved: "Un candidat a été choisi et un re-scraping ciblé a été lancé.",
  dismissed:
    "Décision ignorée : le dossier a été laissé tel quel (résultat automatique conservé, aucun re-scraping).",
  superseded:
    "Décision remplacée : une version plus récente du dossier a été re-scrapée depuis, cette décision n'est plus pertinente.",
};

/** A DS Badge tone usable for a decision status. */
export type StatusTone = "warning" | "success" | "neutral" | "info";

/** Status → DS Badge tone for the per-row status badge. */
export const STATUS_TONE: Record<DecisionStatus, StatusTone> = {
  pending: "warning",
  resolved: "success",
  dismissed: "neutral",
  superseded: "info",
};

// ---------------------------------------------------------------------------
// Safe lookups for a RAW backend status string.
//
// The list rows carry ``status`` typed as ``string`` from the schema, so a
// value outside the known set is possible in theory. These accessors take the
// raw string, narrow it, and fall back to the raw value / a neutral tone —
// keeping the maps strictly ``Record<DecisionStatus, …>`` (so the compiler
// exhaustively checks them) while giving call sites a lint-clean lookup with a
// real fallback.
// ---------------------------------------------------------------------------

/** ``true`` when ``value`` is one of the known decision statuses. */
function isKnownStatus(value: string): value is DecisionStatus {
  return value in STATUS_LABEL;
}

/** Full status label for a raw status string (falls back to the raw value). */
export function statusLabel(status: string): string {
  return isKnownStatus(status) ? STATUS_LABEL[status] : status;
}

/** Status tooltip for a raw status string (falls back to the raw value). */
export function statusTooltip(status: string): string {
  return isKnownStatus(status) ? STATUS_TOOLTIP[status] : status;
}

/** Status badge tone for a raw status string (falls back to ``neutral``). */
export function statusTone(status: string): StatusTone {
  return isKnownStatus(status) ? STATUS_TONE[status] : "neutral";
}
