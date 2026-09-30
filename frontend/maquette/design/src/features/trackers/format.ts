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

// THE UNITS A BYTE COUNT IS WRITTEN IN, each a thousand of the one before —
// the decimal units the client and the disks both count in.
const BYTE_UNITS = ["b", "kb", "mb", "gb", "tb"] as const;
const THOUSAND = 1000;

/**
 * A byte count in the largest unit that keeps it at one or more, and its unit's word.
 *
 * @param bytes The count.
 * @returns The figure written in the interface's language, and the unit's key.
 */
function scaled(bytes: number): { value: string; unit: string } {
  let unit = 0;
  let value = bytes;
  while (value >= THOUSAND && unit < BYTE_UNITS.length - 1) {
    value /= THOUSAND;
    unit += 1;
  }
  // A WHOLE NUMBER OF BYTES HAS NO DECIMAL; a figure under ten keeps one.
  const decimals = unit === 0 || value >= 10 ? 0 : 1;
  return { value: written(value, decimals), unit: i18next.t(`screens.torrents.units.${BYTE_UNITS[unit]}`) };
}

/**
 * A size, as the interface writes it: « 766 Mo ».
 *
 * @param bytes The size in bytes.
 * @returns The size in words.
 */
export function sizeOf(bytes: number): string {
  return i18next.t("screens.torrents.size", scaled(bytes));
}

/**
 * A rate, as the interface writes it: « 2,4 Mo/s ».
 *
 * @param bytesPerSecond The rate.
 * @returns The rate in words.
 */
export function rateOf(bytesPerSecond: number): string {
  return i18next.t("screens.torrents.rate", scaled(bytesPerSecond));
}
