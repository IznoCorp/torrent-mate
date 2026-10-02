// How the « Trackers » page writes its dates (its figures and sizes are
// `lib/byte-size.ts`'s, shared with the acquisition card).
import i18next from "i18next";

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
