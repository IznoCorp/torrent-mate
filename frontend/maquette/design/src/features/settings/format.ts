// Saying a setting's value in the interface's own words.
//
// B-090 IS WHY THIS EXISTS. The contract carried `displayedValue` — the engine's
// `v` field, a French summary RENDERED for a screen — and 110 of the 159 fields
// differed from the value the setting actually holds. Two of them were LOSSY: a
// four-element list read « multi, vf, vostfr +1 » and an eighteen-file list read
// « paths.json5, disks.json5, categories.json5 +15 », so the fourth element and
// the last fifteen files could not be recovered by any reader of the contract.
//
// A PRE-FORMATTED FRENCH VALUE CANNOT FEED A CONTROL, which is what made this
// unavoidable rather than merely untidy: a panel with eight field kinds has to
// EDIT what it shows, and « 4 entrées » is not something an editor can open.
//
// EVERY RULE HERE IS READ OFF THE DATA, not invented. The tests assert against
// the 159 `displayedValue` strings still committed in the seed — extracted from
// `legacy.js` and held byte for byte against it — so this is the engine's own
// rendering reproduced, and it is checkable.
//
// WHAT IS NOT DERIVED, and it is named rather than guessed: seven number fields
// render a decimal the value does not carry (`4` shows as « 4.0 »). JSON has no
// float-ness to read, so the contract gains a PRECISION and the backend is asked
// for it (D7). Deriving it from the number would mean inventing it.

// THE WORDS ARE THE RESOURCES', not this file's. A formatter is as much a
// producer of interface copy as a component is, and CLAUDE.md's rule does not
// stop at the component boundary: « no UI string lives in the code ».
import i18next from "i18next";

/** How many members of a list are named before the rest are counted. */
const NAMED_MEMBERS = 3;

/**
 * One of the formatter's own words.
 *
 * @param key The key, under the `settingValue` namespace.
 * @param values What it interpolates, if anything.
 * @returns The word.
 */
function say(key: string, values?: Record<string, unknown>): string {
  return i18next.t(`settingValue.${key}`, values ?? {});
}

/**
 * Pads one number to two digits, the way a clock reads.
 *
 * @param value The number.
 * @returns Two digits.
 */
function twoDigits(value: number | string): string {
  return String(value).padStart(2, "0");
}

/**
 * Says one cron expression in words.
 *
 * FOUR SHAPES, AND THEY ARE THE ONES THE DATA HOLDS: every hour at a minute;
 * one or more hours every day; and one hour on one weekday. An expression
 * outside them answers with ITSELF rather than with a sentence — the engine's
 * own last resort, and the only honest one: a schedule nobody can read is not a
 * schedule that runs at midnight.
 *
 * @param expression The cron expression.
 * @returns The sentence, or the expression when it cannot be read.
 */
export function scheduleInWords(expression: string): string {
  const fields = expression.trim().split(/\s+/);
  if (fields.length !== 5) return expression;
  const [minute, hours, dayOfMonth, month, weekday] = fields;
  if (dayOfMonth !== "*" || month !== "*") return expression;
  if (!/^\d+$/.test(minute)) return expression;

  if (hours === "*" && weekday === "*") {
    return say("everyHourAtMinute", { minute: Number(minute) });
  }
  if (!/^\d+(,\d+)*$/.test(hours)) return expression;
  const said = hours
    .split(",")
    .map((hour) => `${twoDigits(hour)} h ${twoDigits(minute)}`);
  if (/^\d$/.test(weekday)) {
    if (said.length !== 1) return expression;
    return say("onDayAt", { day: say(`days.${weekday}`), time: said[0] });
  }
  if (weekday !== "*") return expression;
  if (said.length === 1) return say("everyDayAt", { time: said[0] });
  return say("atTimes", {
    first: said.slice(0, -1).join(", "),
    last: said[said.length - 1],
  });
}

/**
 * Says one setting's value in the interface's own words.
 *
 * @param kind The setting's kind, as the contract names it.
 * @param value What the setting holds.
 * @param precision How many decimals the value is written with, when it has one.
 * @returns What the panel shows for it.
 */
export function settingInWords(
  kind: string,
  value: unknown,
  precision?: number,
): string {
  if (value === null || value === undefined) return say("undefined");
  if (typeof value === "boolean") return say(value ? "yes" : "no");
  if (typeof value === "number") {
    // THE PRECISION IS THE CONTRACT'S, never derived. `4` and `4.0` are one
    // number in JSON and two different settings on screen — a size in whole
    // gigabytes and a ratio written to one decimal — and only the schema knows
    // which. Absent, the number says itself.
    return precision === undefined ? String(value) : value.toFixed(precision);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return say("none");
    // A LIST OF THINGS IS COUNTED, a list of words is named. The difference is
    // what the members ARE: a disk or a staging directory is an entry with
    // fields, and naming three of eight would say less than counting them.
    if (value.some((member) => typeof member === "object" && member !== null)) {
      return say("entries", { count: value.length });
    }
    const said = value.map(String);
    if (said.length <= NAMED_MEMBERS) return said.join(", ");
    return say("andMore", {
      named: said.slice(0, NAMED_MEMBERS).join(", "),
      rest: said.length - NAMED_MEMBERS,
    });
  }
  if (kind === "schedule") return scheduleInWords(String(value));
  return String(value);
}
