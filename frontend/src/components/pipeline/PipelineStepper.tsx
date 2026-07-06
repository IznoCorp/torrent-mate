/**
 * PipelineStepper — the 9-stage pipeline progress visualisation.
 *
 * Ported from the design-system ``PipelineStepper.jsx`` reference and re-implemented
 * as a shadcn/Tailwind component. Two modes:
 *
 * - **LIVE** — ``currentStep`` is provided (or omitted): the current step is
 *   ``"running"``, earlier steps ``"done"``, later steps ``"queued"``.
 * - **READ-ONLY** — ``steps`` is provided: each step's status + elapsed come
 *   directly from the API (used in Phase 5 history detail).
 *
 * When both are omitted, the stepper renders all 9 steps as ``"queued"``.
 */

import type { ReactElement } from "react";

import type { components } from "@/api/schema";
import { StatusDot, type PipelineStatus } from "@/components/ds/StatusDot";

import "./PipelineStepper.css";

/** A single step timing record from the API (Phase 5 history). */
type StepTiming = components["schemas"]["StepTiming"];

// ---------------------------------------------------------------------------
// Step catalog
// ---------------------------------------------------------------------------

/** The 9 pipeline steps in execution order (machine ids). */
const STEP_IDS = [
  "ingest",
  "sort",
  "clean",
  "scrape",
  "cleanup",
  "enforce",
  "verify",
  "trailers",
  "dispatch",
] as const;

/** Machine step id. */
type StepId = (typeof STEP_IDS)[number];

/** French display labels keyed by machine step id. */
const STEP_LABELS: Record<StepId, string> = {
  ingest: "Collecte",
  sort: "Tri",
  clean: "Nettoyage",
  scrape: "Scraping",
  cleanup: "Nettoyage final",
  enforce: "Conformité",
  verify: "Vérification",
  trailers: "Bandes-annonces",
  dispatch: "Dispatch",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map an API step status string to a {@link PipelineStatus}. */
function mapStatus(raw: string): PipelineStatus {
  switch (raw) {
    case "done":
      return "done";
    case "running":
      return "running";
    case "error":
    case "failed":
      return "error";
    case "skipped":
      return "skipped";
    case "queued":
    case "pending":
      return "queued";
    default:
      return "idle";
  }
}

/**
 * Format an elapsed duration in seconds to a compact, tabular string.
 *
 * Args:
 *   seconds: The duration in seconds.
 *
 * Returns:
 *   A human-readable elapsed string (e.g. ``"2.3s"``, ``"1m 05s"``).
 */
function formatElapsed(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins)}m ${String(secs).padStart(2, "0")}s`;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * Props for {@link PipelineStepper}.
 *
 * Two modes are supported via the presence of ``steps``:
 *
 * - **LIVE** — ``currentStep`` is provided (or omitted): the current step is
 *   ``"running"``, earlier steps ``"done"``, later steps ``"queued"``.
 * - **READ-ONLY** — ``steps`` is provided: each step's status + elapsed come
 *   directly from the API (used in Phase 5 history detail).
 *
 * When both are omitted, the stepper renders all 9 steps as ``"queued"``.
 */
export interface PipelineStepperProps {
  /**
   * The machine step id currently executing, or ``null`` when idle.
   *
   * Used in LIVE mode. Ignored when ``steps`` is provided.
   */
  readonly currentStep?: string | null;
  /**
   * The full list of step timing records from a pipeline run.
   *
   * When provided (READ-ONLY mode), ``currentStep`` is ignored and each
   * step's status is taken from its record.
   */
  readonly steps?: readonly StepTiming[];
  readonly className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Check whether a string is one of the known pipeline step ids.
 *
 * Args:
 *   name: The candidate step name.
 *
 * Returns:
 *   ``true`` when ``name`` is a valid {@link StepId}.
 */
function isStepId(name: string): name is StepId {
  return (STEP_IDS as readonly string[]).includes(name);
}

/**
 * PipelineStepper — the 9-stage pipeline status rail.
 *
 * In LIVE mode, each step's status is derived from its position relative to
 * ``currentStep``. In READ-ONLY mode, statuses come directly from the
 * ``StepTiming[]`` array.
 *
 * Args:
 *   props: The stepper props (``currentStep`` for LIVE, ``steps`` for
 *     READ-ONLY, or neither for all-queued).
 *
 * Returns:
 *   The stepper element.
 */
export function PipelineStepper(props: PipelineStepperProps): ReactElement {
  const isLive = props.steps == null || props.steps.length === 0;

  // Build the display list: one entry per step id.
  let rows: {
    id: StepId;
    label: string;
    status: PipelineStatus;
    elapsed: string | null;
  }[];

  if (isLive) {
    const currentIdx = STEP_IDS.indexOf((props.currentStep ?? "") as StepId);
    rows = STEP_IDS.map((id, idx) => {
      let status: PipelineStatus;
      if (currentIdx === -1) {
        // Idle pipeline — all steps are queued.
        status = "queued";
      } else if (idx < currentIdx) {
        status = "done";
      } else if (idx === currentIdx) {
        status = "running";
      } else {
        status = "queued";
      }
      return { id, label: STEP_LABELS[id], status, elapsed: null };
    });
  } else {
    const steps = props.steps;
    rows = steps.map((s) => {
      const name = s.name;
      const label = isStepId(name) ? STEP_LABELS[name] : name;
      const status = mapStatus(s.status);
      const elapsed =
        s.elapsed_s != null ? formatElapsed(s.elapsed_s) : null;
      // Use the machine name as the key; padding fills in missing known ids.
      return { id: name as StepId, label, status, elapsed };
    });

    // Pad to the full 9-step catalog if the API returned fewer steps.
    if (rows.length < STEP_IDS.length) {
      const present = new Set(rows.map((r) => r.id));
      for (const id of STEP_IDS) {
        if (!present.has(id)) {
          rows.push({
            id,
            label: STEP_LABELS[id],
            status: "idle",
            elapsed: null,
          });
        }
      }
    }
  }

  return (
    <div
      className={`ps-stepper ${props.className ?? ""}`}
      role="list"
      aria-label="Étapes du pipeline"
    >
      {rows.map((row, i) => (
        <div
          key={row.id}
          className={`ps-step ps-step--${row.status}`}
          role="listitem"
        >
          <div className="ps-step__top">
            <span className="ps-step__num">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="ps-step__dotwrap">
              <StatusDot status={row.status} showLabel={false} />
            </span>
          </div>
          <div className="ps-step__rail">
            <span className="ps-step__rail-fill" />
          </div>
          <div className="ps-step__body">
            <span className="ps-step__name">{row.label}</span>
            {row.elapsed !== null && (
              <span className="ps-step__meta">{row.elapsed}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
