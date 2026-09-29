// A fact's state, said: ONE word and ONE tone per state code.
//
// The seeds carried the words themselves — « en ligne », « connecté »,
// « disponibles », « joignable » for one state — where no guard could see them.
// The data carry a CODE now; the word is the interface's (`states` in fr.json)
// and the tone is derived here, once, for the page and for the badge.
import type { FactRow } from "../../ui/fact-rows";
import type { Schemas } from "../../lib/contract-schemas";

type Fact = Schemas["Fact"];
type StateCode = NonNullable<Fact["state"]>;

/** The tone each state wears: what is fine is success, what needs doing warns, what is down alerts. */
const STATE_TONE: Record<StateCode, string> = {
  reachable: "success",
  on_time: "success",
  room: "success",
  succeeded: "success",
  none: "success",
  nearly_full: "warning",
  to_clean: "warning",
  offline: "alert",
  late: "alert",
};

/**
 * The tone a fact wears: its state's, or the one a quantity carries.
 *
 * @param fact The fact as the layer answers it.
 * @returns The operator's tone word, or none.
 */
export function factTone(fact: Fact): string | undefined {
  return fact.state ? STATE_TONE[fact.state] : fact.tone;
}

/**
 * A fact as a row: a state said in the interface's word, a quantity as it came.
 *
 * @param fact The fact as the layer answers it.
 * @param say The translator.
 * @returns The row the fact list draws.
 */
export function factRow(fact: Fact, say: (key: string) => string): FactRow {
  return {
    label: fact.label,
    value: fact.state ? say(`states.${fact.state}`) : (fact.value ?? ""),
    tone: factTone(fact),
    secondaryLine: fact.secondaryLine,
  };
}
