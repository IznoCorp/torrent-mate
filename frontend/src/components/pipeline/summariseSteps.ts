/**
 * summariseSteps — build interpreted summary lines from a persisted run.
 *
 * The live interpreted feed folds WS ``ItemProgressed`` events, which are gone
 * once a run finishes. For the idle "last run" view (webui-ux Phase 2.4) the
 * narrative is instead reconstructed from the per-step summary counts persisted
 * into ``steps_json`` at Phase 2.2 (``success_count`` / ``skip_count`` /
 * ``error_count`` / ``unmatched_count``), exposed on the run-detail
 * ``StepTiming`` model. This module turns those counts into one plain-French
 * line per step. Pure + fail-soft: a legacy step (all counts ``null``) yields a
 * bare "terminée / échec" line, never throwing.
 */

import type { components } from "@/api/schema";
import type { InterpretedLine, LineTone } from "@/components/pipeline/interpretRun";

/** A persisted per-step timing+summary record from the run detail. */
type StepTiming = components["schemas"]["StepTiming"];

/** Human step names (French) — mirrors the live reducer's STEP_LABEL. */
export const STEP_LABEL: Record<string, string> = {
  ingest: "Récupération des téléchargements",
  sort: "Tri vers la zone de préparation",
  clean: "Nettoyage des fichiers parasites",
  scrape: "Recherche des métadonnées",
  cleanup: "Suppression des dossiers vides",
  enforce: "Mise en conformité des noms",
  verify: "Vérification finale",
  trailers: "Bandes-annonces",
  dispatch: "Rangement vers le stockage",
};

/**
 * Compose the count fragment for a step (e.g. "3 traités, 1 ignoré").
 *
 * Only non-null, non-zero counters appear. ``unmatched_count`` is surfaced as
 * "en attente de décision" because those are the scrape items awaiting an
 * operator decision.
 *
 * Args:
 *   step: The step summary record.
 *
 * Returns:
 *   The joined fragment, or ``""`` when no counter is populated.
 */
function countFragment(step: StepTiming): string {
  const parts: string[] = [];
  if (step.success_count != null && step.success_count > 0) {
    parts.push(`${String(step.success_count)} traité${step.success_count > 1 ? "s" : ""}`);
  }
  if (step.skip_count != null && step.skip_count > 0) {
    parts.push(`${String(step.skip_count)} ignoré${step.skip_count > 1 ? "s" : ""}`);
  }
  if (step.error_count != null && step.error_count > 0) {
    parts.push(`${String(step.error_count)} en erreur`);
  }
  if (step.unmatched_count != null && step.unmatched_count > 0) {
    parts.push(
      `${String(step.unmatched_count)} en attente de décision`,
    );
  }
  return parts.join(", ");
}

/**
 * Pick the tone for a step summary line from its counts + status.
 *
 * Args:
 *   step: The step summary record.
 *
 * Returns:
 *   ``danger`` on any error, ``warning`` on pending decisions, else ``success``
 *   when work was done, else ``info``.
 */
function toneFor(step: StepTiming): LineTone {
  if (step.status === "error" || (step.error_count != null && step.error_count > 0)) {
    return "danger";
  }
  if (step.unmatched_count != null && step.unmatched_count > 0) {
    return "warning";
  }
  if (step.success_count != null && step.success_count > 0) {
    return "success";
  }
  return "info";
}

/**
 * Turn a persisted run's steps into interpreted summary lines.
 *
 * Args:
 *   steps: The run-detail ``steps`` array (may be empty / legacy-shaped).
 *
 * Returns:
 *   One interpreted line per known step, in order. Unknown step names are
 *   skipped so a future step never renders a raw identifier.
 */
export function summariseSteps(
  steps: readonly StepTiming[],
): InterpretedLine[] {
  const lines: InterpretedLine[] = [];
  for (const step of steps) {
    const label = STEP_LABEL[step.name];
    if (label === undefined) continue;

    const fragment = countFragment(step);
    const tone = toneFor(step);

    let text: string;
    if (step.status === "error") {
      text = `${label} — échec`;
    } else if (step.status === "skipped" && fragment === "") {
      text = `${label} — ignorée`;
    } else if (fragment === "") {
      text = `${label} — terminée`;
    } else {
      text = `${label} — ${fragment}`;
    }

    lines.push({ step: step.name, text, tone });
  }
  return lines;
}
