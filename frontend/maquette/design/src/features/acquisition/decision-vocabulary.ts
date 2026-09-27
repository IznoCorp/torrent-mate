// The arbitration VOCABULARY — how a scrape decision's reason, its state and
// the way its choice was reached are said.
//
// The server holds each as a TOKEN (the contract says so on `reason`, `state`
// and `via`); the word, the sentence explaining it and the chip's tone are this
// interface's. The words live in `i18n/fr.json` under `screens.resolution`.
// The reasons are said as the REASON a folder is here, never as a state nobody
// can act on, and `dismissed`/`superseded` are spelled out as what happened to
// the folder rather than what the code did.
import i18next from "i18next";

/** The tone of a reason's chip, by reason token. */
export const REASON_TONE: Record<string, string> = {
  below_threshold: "danger",
  mid_band: "warning",
  ambiguous: "info",
  manual: "neutral",
};

/** The tone of a settled decision's state chip, by state token. */
export const DECISION_STATE_TONE: Record<string, string> = {
  resolved: "success",
  dismissed: "neutral",
  superseded: "info",
};

/**
 * One word of a token-keyed group of the resources, or nothing when the token
 * has none.
 *
 * @param group The group's key under `screens.resolution`.
 * @param token The token.
 * @returns The word, or null for a token the interface has no word for.
 */
function wordFor(group: string, token: string): string | null {
  const key = `screens.resolution.${group}.${token}`;
  return i18next.exists(key) ? i18next.t(key) : null;
}

/**
 * The chip's word for why a decision could not be taken alone.
 *
 * @param reason The reason token.
 * @returns The word, or the token itself when the interface has none for it.
 */
export function reasonLabel(reason: string): string {
  return wordFor("reason", reason) ?? reason;
}

/**
 * The sentence explaining a reason.
 *
 * @param reason The reason token.
 * @returns The sentence, or an empty string when the interface has none.
 */
export function reasonDetail(reason: string): string {
  return wordFor("reasonDetail", reason) ?? "";
}

/**
 * A settled decision's state, as its chip says it.
 *
 * @param state The state token.
 * @returns The chip's tone and word, or null for a state the interface does not draw.
 */
export function decisionState(state: string): [string, string] | null {
  const label = wordFor("decisionState", state);
  return label === null ? null : [DECISION_STATE_TONE[state], label];
}

/**
 * The sentence explaining a settled decision's state.
 *
 * @param state The state token.
 * @returns The sentence, or an empty string when the interface has none.
 */
export function decisionStateDetail(state: string): string {
  return wordFor("decisionStateDetail", state) ?? "";
}

/**
 * How a decision's choice was reached, said in words.
 *
 * @param via The token.
 * @returns The words, or the token itself when the interface has none for it.
 */
export function viaLabel(via: string): string {
  return wordFor("via", via) ?? via;
}
