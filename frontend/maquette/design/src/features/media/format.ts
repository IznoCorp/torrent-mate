// How the media sheet writes a date and a list of episode numbers.
//
// PURE: the words a date is written with are the interface's, and they are read
// from `fr.json` like every other word, so this only decides their order.
import i18next from "i18next";

/**
 * A calendar date as the sheet writes it: the day, the month's short name, the year.
 *
 * @param iso The date, as `YYYY-MM-DD`.
 * @returns The written date, or null when there is none — an announced episode
 *     often has no air date yet, and the caller decides what to show instead.
 */
export function dateLabel(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const [year, month, day] = iso.split("-").map(Number);
  const names = i18next.t("common.monthsShort", { returnObjects: true }) as string[];
  return `${day} ${names[month - 1]} ${year}`;
}

/**
 * An episode's state, said as the sheet, the season legend and the popover say it.
 *
 * @param state The episode state token (`in_library`, `announced`, …).
 * @returns The words, or an empty string for a state the interface has none for.
 */
export function episodeStateLabel(state: string): string {
  const key = `screens.media.episodeState.${state}`;
  return i18next.exists(key) ? i18next.t(key) : "";
}

/**
 * Episodes by their codes with their runs folded: « E03, E07, E12, E13, E14 »
 * reads badly, « E03, E07, E12–E14 » reads. A CODE and not a bare number:
 * « Manquants : 7 » read as seven missing (the reader of the train, 2026-09-30).
 *
 * @param numbers The episode numbers, in any order.
 * @returns The codes, sorted, each run of three or more written as a range.
 */
export function episodeRanges(numbers: number[]): string {
  const code = (number: number) => `E${String(number).padStart(2, "0")}`;
  const sorted = [...numbers].sort((left, right) => left - right);
  const written: string[] = [];
  for (let start = 0; start < sorted.length; ) {
    let end = start;
    while (end + 1 < sorted.length && sorted[end + 1] === sorted[end] + 1) end++;
    written.push(end > start + 1 ? `${code(sorted[start])}–${code(sorted[end])}` : sorted.slice(start, end + 1).map(code).join(", "));
    start = end + 1;
  }
  return written.join(", ");
}
