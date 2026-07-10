/**
 * Shared pipeline run-trigger label + tone + meaning maps.
 *
 * Mirrors {@link import("@/components/decisions/triggers")} (the decisions
 * trigger maps) so a raw ``pipeline_run.trigger`` value (free TEXT, no enum)
 * renders as a human French label with a semantic Badge tone and a one-line
 * meaning surfaced in a legend. The known values come from the run-journal /
 * watcher / web-runner sources (``cli``, ``web``, ``cron``, ``completion``,
 * ``safety_net``, ``manual``); an unknown value passes through verbatim
 * (webui-ux Phase 2.1).
 */

import type { BadgeProps } from "@/components/ui/badge";

/** Descriptor for one known trigger value. */
export interface TriggerInfo {
  /** Short French label shown in run tables + detail. */
  readonly label: string;
  /** Semantic DS Badge tone. */
  readonly tone: NonNullable<BadgeProps["tone"]>;
  /** One-line French explanation surfaced in the legend/caption. */
  readonly meaning: string;
}

/**
 * Known trigger → descriptor. The insertion order is the legend display order
 * (most operator-relevant automatic triggers first, manual/CLI last).
 */
export const TRIGGER_INFO: Record<string, TriggerInfo> = {
  completion: {
    label: "Fin de téléchargement",
    tone: "success",
    meaning: "Lancé automatiquement à la fin d'un téléchargement.",
  },
  safety_net: {
    label: "Filet de sécurité",
    tone: "warning",
    meaning: "Passage périodique de rattrapage (intervalle minimal).",
  },
  cron: {
    label: "Planifié",
    tone: "info",
    meaning: "Déclenché par une tâche planifiée (cron).",
  },
  web: {
    label: "Interface web",
    tone: "info",
    meaning: "Lancé manuellement depuis l'interface web.",
  },
  cli: {
    label: "Ligne de commande",
    tone: "neutral",
    meaning: "Lancé en ligne de commande.",
  },
  manual: {
    label: "Manuel",
    tone: "neutral",
    meaning: "Déclenché manuellement.",
  },
};

/**
 * Resolve a raw trigger string to its human label.
 *
 * Args:
 *   trigger: The raw ``pipeline_run.trigger`` value.
 *
 * Returns:
 *   The French label for a known trigger, or the raw value unchanged when the
 *   trigger is not in {@link TRIGGER_INFO} (passthrough).
 */
export function triggerLabel(trigger: string): string {
  return TRIGGER_INFO[trigger]?.label ?? trigger;
}

/**
 * Resolve a raw trigger string to its Badge tone.
 *
 * Args:
 *   trigger: The raw ``pipeline_run.trigger`` value.
 *
 * Returns:
 *   The tone for a known trigger, or ``"neutral"`` for an unknown value.
 */
export function triggerTone(trigger: string): NonNullable<BadgeProps["tone"]> {
  return TRIGGER_INFO[trigger]?.tone ?? "neutral";
}
