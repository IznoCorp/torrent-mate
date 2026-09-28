// How the « Trackers » page writes its numbers and its dates.
//
// ONE WRITER FOR BOTH TABS: a ratio written « 1,42 » on one tab and « 1.42 » on
// the other would be two readings of the same figure.
import i18next from "i18next";

/**
 * A number as the interface writes it, with fixed decimals.
 *
 * @param value The number.
 * @param decimals How many decimals it carries.
 * @returns The number, written in the interface's language.
 */
export function written(value: number, decimals: number): string {
  return new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * A moment, as a sentence says it: the day and the month.
 *
 * @param epochSeconds The moment, Unix-epoch seconds.
 * @returns The day in the interface's language.
 */
export function dayOf(epochSeconds: number): string {
  return new Intl.DateTimeFormat(i18next.language, { day: "numeric", month: "long" }).format(
    new Date(epochSeconds * 1000),
  );
}
