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
