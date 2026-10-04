// What a maintenance command RISKS, and how the interface says it.
//
// The engine carried this as `RISQUES`, a three-entry table of a label and a
// pip colour, and the register classes it `interface`: what a risk level is
// CALLED is the operator's words and what colour says so is a drawing decision
// — neither is an answer a server sends, so routing it through a mock would
// have the interface asking for its own vocabulary.
//
// SPLIT IN TWO ON THE SAME LINE THE LANGUAGE RULE DRAWS. The label is interface
// text and lives in `fr.json`; the pip is a token name and is code. They were
// one object in the engine because the engine had no i18n layer at all.
//
// It lives with Maintenance because that is the only feature that has risks:
// the panel producer and the page both read it, which is one derivation for one
// question (§13) rather than the two copies that would follow from each holding
// its own.
import i18next from "i18next";

/** Which pip colour says a risk level, by the key the actions declare. */
const PIP: Record<string, string> = {
  ro: "success",
  write: "info",
  destructive: "danger",
};

/**
 * What a risk level is called, in the reader's own language.
 *
 * Args:
 *     level: The action's `r`, as the maintenance actions declare it.
 *
 * Returns:
 *     The label. An unknown level answers the key itself rather than an empty
 *     string — a blank fact row says the command is harmless, which is the one
 *     wrong thing it could say.
 */
export function riskLabel(level: string): string {
  const key = `panels.risks.${level}`;
  const said = i18next.t(key);
  return said === key ? level : said;
}

/**
 * Which pip colour says a risk level.
 *
 * Args:
 *     level: The action's `r`.
 *
 * Returns:
 *     The token name, or the muted one for a level nobody declared — never a
 *     colour that would read as reassuring.
 */
export function riskPip(level: string): string {
  return PIP[level] ?? "muted";
}
