/**
 * StalledPanel — shared warning card for per-step skip/defer/error reasons.
 *
 * Extracted from RunDetail's inline block during Phase 5.1 (control-medias
 * rebuild) so the Contrôle station dashboard can reuse the exact same markup,
 * tones, and labels when displaying why items did not advance during the last
 * pipeline run.  This is §8 promoted from a run-detail-only concern to a
 * first-class dashboard widget.
 *
 * The component is defensive: it returns ``null`` when ``stepReasons`` is empty
 * so callers never need to guard with ``length > 0`` themselves.
 */

import type { ReactElement } from "react";

import { STEP_LABEL } from "@/components/pipeline/summariseSteps";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A single pipeline step with its human-readable skip/defer/error reasons. */
export interface StepReasonsEntry {
  /**
   * The step identifier (e.g. ``"ingest"``, ``"scrape"``).
   *
   * Used as the lookup key into {@link STEP_LABEL} for French display names
   * and as a React ``key`` fallback.
   */
  readonly step: string;
  /**
   * One or more human-readable reasons why items were skipped, deferred, or
   * errored during this step (already localised to French by the backend).
   */
  readonly reasons: readonly string[];
}

/** Props for {@link StalledPanel}. */
export interface StalledPanelProps {
  /**
   * Per-step reasons why items did not advance through the pipeline.
   *
   * Derived from a pipeline run's ``steps`` array by filtering:
   *
   * 1. Exclude the ``"queue"`` pseudo-step (it has its own banner).
   * 2. Drop any step whose ``reasons`` array is absent or empty.
   * 3. Map each remaining step to ``{step: s.name, reasons: s.reasons}``.
   */
  readonly stepReasons: readonly StepReasonsEntry[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * StalledPanel — « Ce qui n'a pas avancé » warning card.
 *
 * Renders a warning-styled card listing per-step reasons (skip, defer, error)
 * so the operator understands WHY pipeline items did not advance.  Used by
 * {@link RunDetail} (run-history inspection) and the Contrôle station dashboard
 * (§8 — promoted from run-detail-only to first-class dashboard widget).
 *
 * Args:
 *   stepReasons: Per-step reasons to display.  Empty array → renders nothing.
 *
 * Returns:
 *   A warning card, or ``null`` when there are no reasons to show.
 */
export function StalledPanel({
  stepReasons,
}: StalledPanelProps): ReactElement | null {
  if (stepReasons.length === 0) return null;

  return (
    <div className="rounded-lg border border-[var(--warning)]/30 bg-[var(--warning)]/10 p-4">
      <p className="mb-2 text-xs font-semibold text-[var(--warning)]">
        Ce qui n'a pas avancé
      </p>
      <div className="flex flex-col gap-2">
        {stepReasons.map(({ step, reasons }) => (
          <div key={step}>
            <span className="text-xs text-muted-foreground">
              {STEP_LABEL[step] ?? step}
            </span>
            <ul className="mt-0.5 flex flex-col gap-0.5 text-xs">
              {reasons.map((reason, i) => (
                <li key={`${step}-${String(i)}`} className="text-foreground/90">
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
