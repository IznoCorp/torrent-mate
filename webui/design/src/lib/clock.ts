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
 * Sets the page's clock at boot: frozen on the layer's day, or left real.
 *
 * THE DESIGN HOST READS THE REAL CLOCK (the operator, 2026-10-04; Q6 = B): it
 * is where the interface is developed against the real server, whose dates are
 * today's. Every other build freezes it, so a recorded reference stays
 * comparable — the harness and the unit suite among them.
 *
 * @param designHost Whether this is the design host's build.
 * @param frozenDay The layer's frozen day, as `YYYY-MM-DD`.
 */
export function bootClock(designHost: boolean, frozenDay: string): void {
  if (!designHost) freezeClock(frozenDay);
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

/**
 * The moment an instant falls on, as « depuis … » names it: its time alone on
 * the day it is read, the day and the time before it — « 02 h 00 » about a
 * tracker down since 12 September read as this morning (M4 of the lot's
 * reading).
 *
 * READ AGAINST THE WALL CLOCK, not the frozen day: what « since » names — a
 * block, a service down — is posed and served against the instant it is read
 * at, never against the layer's frozen catalogue day.
 *
 * @param epoch The instant, epoch seconds.
 * @param now The moment it is read at.
 * @returns The moment, in the interface's language.
 */
export function momentOf(epoch: number, now: Date = new Date()): string {
  const instant = new Date(epoch * 1000);
  if (instant.toDateString() === now.toDateString()) return timeOfDay(epoch);
  const date = new Intl.DateTimeFormat(i18next.language, { day: "numeric", month: "long" }).format(instant);
  return i18next.t("surfaces.clock.dayAndTime", { day: date, time: timeOfDay(epoch) });
}
