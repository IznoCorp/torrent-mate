// How a passage ended: ONE word and ONE tone per outcome, for the list of
// passages and for a passage's own screen — the same run read « arrêté » on one
// and « interrompu » on the other while each drew its own.
import type { components } from "../../contract/types";

type RunOutcome = components["schemas"]["RunOutcome"];

/** The operator's tone word per outcome, as a fact row carries it: a failure is loud. */
export const OUTCOME_TONE: Record<RunOutcome, "success" | "alert" | "info" | "warning" | "neutral"> = {
  success: "success",
  error: "alert",
  killed: "alert",
  running: "info",
  paused: "warning",
};

/**
 * The key of the word an outcome is said in.
 *
 * @param outcome The outcome, or none for a run still going.
 * @returns The `fr.json` key.
 */
export function outcomeWord(outcome: RunOutcome | null | undefined): string {
  return `screens.run.outcome.${outcome ?? "running"}`;
}
