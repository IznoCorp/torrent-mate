// Today's date, as every surface that compares a date with it reads it.
//
// ONE CLOCK, AND IT CAN BE FROZEN. A season « à venir » and an episode « diffusé
// le » are both a comparison with today, and a prototype whose today moved with
// the wall clock would draw a different page every day it is opened — nothing
// could be compared with a recorded reference. So the boot may freeze it: with
// the mock layer built in, `app/shell.tsx` fills it with the layer's own frozen
// instant, and the dates the layer answers and the day the page compares them
// with are then one day. Without the layer it is the real date.
//
// A DOOR, not a constant, because what freezes it is the boot's business and
// `lib/` may not import the mock layer (only `app/` may).
import i18next from "i18next";

// The frozen day, once the boot has filled it; the real date until then.
let frozen: string | undefined;

/**
 * Freezes today's date, from the boot.
 *
 * @param date The day, as `YYYY-MM-DD`.
 */
export function freezeClock(date: string): void {
  frozen = date;
}

/**
 * Today's date.
 *
 * @returns The frozen day when the boot froze one, else the real date — both as
 *     `YYYY-MM-DD`, the form the dates it is compared with are written in.
 */
export function today(): string {
  return frozen ?? new Date().toISOString().slice(0, 10);
}

/**
 * The time of day an instant falls on, as a sentence names it.
 *
 * @param epoch The instant, epoch seconds.
 * @returns The hour and the minute, in the interface's language.
 */
export function timeOfDay(epoch: number): string {
  const instant = new Date(epoch * 1000);
  const two = (value: number) => String(value).padStart(2, "0");
  return i18next.t("surfaces.clock.timeOfDay", { hour: two(instant.getHours()), minute: two(instant.getMinutes()) });
}
