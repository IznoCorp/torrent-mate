/**
 * The facts a decision row is built from, derived ONCE.
 *
 * Every surface that draws a decision — the queue, the journal, the deck —
 * asks the same three questions: which folder, why is it here, what became of
 * it. Deriving them per surface is how two of them end up disagreeing, and a
 * decision that reads « Réglée » on one screen and « Résolue » on another is
 * two answers to one question.
 *
 * Rule R57, `frontend/maquette/harness/decision.py`.
 */

import type { DecisionRowProps } from "@/components/ds/DecisionRow";
import {
  statusLabel,
  statusTone,
  statusTooltip,
  TRIGGER_LABEL,
  TRIGGER_TOOLTIP,
  TRIGGER_TONE,
  VIA_LABEL,
} from "@/components/decisions/triggers";

/** What the API returns about a decision, in the shape both surfaces share. */
export interface DecisionLike {
  readonly staging_path: string;
  readonly media_kind: string;
  readonly trigger: string;
  readonly status: string;
  readonly updated_at?: number | null;
  readonly created_at?: number | null;
  readonly resolved_at?: number | null;
  readonly resolution_json?: unknown;
}

/**
 * The last component of a staging path.
 *
 * A folder name is what the operator recognises; the absolute path is what the
 * tooltip carries. macOS staging roots contain spaces, which `split` handles.
 *
 * Args:
 *   path: The absolute staging path.
 *
 * Returns:
 *   The folder name.
 */
export function folderName(path: string): string {
  const parts = path.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

/**
 * A decision timestamp, written out in French.
 *
 * Args:
 *   epoch: Unix epoch seconds, or null.
 *
 * Returns:
 *   A readable date, or an explicit unknown — never an invented one (§14.3).
 */
export function decisionWhen(epoch: number | null | undefined): string {
  if (epoch == null) return "date inconnue";
  return new Date(epoch * 1000).toLocaleString("fr-FR", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Build the row facts of one decision.
 *
 * Args:
 *   decision: The API row.
 *
 * Returns:
 *   Everything {@link DecisionRow} needs except its handlers.
 */
export function decisionFacts(
  decision: DecisionLike,
): Omit<DecisionRowProps, "onOpen"> {
  const settled = decision.status !== "pending";
  const resolution = decision.resolution_json as {
    provider?: string;
    provider_id?: number;
    via?: string;
    title?: string;
    poster_url?: string | null;
  } | null;

  const chosen =
    resolution?.provider != null && resolution.provider_id != null
      ? {
          // The engine records the ids, not always the title it settled on. A
          // missing title is said, never guessed from the folder — the folder
          // name is precisely what could not be trusted.
          title: resolution.title ?? "Titre non enregistré",
          provider: resolution.provider,
          providerId: resolution.provider_id,
          how: VIA_LABEL[resolution.via ?? ""] ?? "choisi",
          posterUrl: resolution.poster_url ?? null,
        }
      : undefined;

  return {
    folder: folderName(decision.staging_path),
    path: decision.staging_path,
    kind: decision.media_kind === "movie" ? "movie" : "tvshow",
    when: decisionWhen(
      decision.resolved_at ?? decision.updated_at ?? decision.created_at ?? null,
    ),
    reason: {
      tone: TRIGGER_TONE[decision.trigger] ?? "neutral",
      label: TRIGGER_LABEL[decision.trigger] ?? decision.trigger,
      hint: TRIGGER_TOOLTIP[decision.trigger],
    },
    ...(settled
      ? {
          outcome: {
            tone: statusTone(decision.status),
            label: statusLabel(decision.status),
            hint: statusTooltip(decision.status),
          },
        }
      : {}),
    ...(chosen != null ? { chosen } : {}),
  };
}
