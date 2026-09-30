// One medium's ladder, from the wish to Plex — the ONE list the card's strip
// and the journey sheet both read.
//
// THREE LISTS USED TO ANSWER « WHERE IS THIS MEDIUM »: the card's five-position
// strip, the journey's five stages and the pipeline's nine steps. The ladder is
// one list of eight rungs, held per medium in the layer's state, so the queue's
// card and `readJourney` answer the SAME array — and a verb that moves the
// journey moves the card with it.
import JOURNEY_STAGES from "../seeds/journey-stages.json";
import { mockState } from "../state";
import type { components } from "../../contract/types";

type Rung = components["schemas"]["JourneyStage"];
type RungState = Rung["state"];

/**
 * Where a medium stands: the index of its current rung, that rung's state, and
 * — when it waits or is blocked for a reason the layer knows — the reason.
 */
export type Position = { current: number; state: RungState; reason?: string };

/**
 * What of the ladder a medium's OWN row lived. A rung before it is not drawn
 * as passed: a folder dropped by hand was never asked for, searched, taken or
 * downloaded, and a rung is « done » only with the date its row carries.
 */
export type Origin = {
  /** The first rung the row lived — « attrapé » unless said otherwise. */
  from?: Rung["rung"];
  /** When it was asked for, where the row carries it: a follow's own date. */
  asked?: string;
  /** Added by hand in the download client: nothing before « arrivé » was lived. */
  direct?: boolean;
};

// The seed is ONE journey, followed from the wish to Plex; every ladder is laid
// on its rungs and takes its times from it.
const TEMPLATE = JOURNEY_STAGES as Rung[];

const DONE = "done";
const RUNNING_NOW = "now";
const BLOCKED = "blocked";
const PENDING = "pending";
const SKIPPED = "skipped";

// The words a rung not reached is drawn with — read off the seed's last rung,
// which no journey of the seed has reached.
const UPCOMING_WHEN = TEMPLATE[TEMPLATE.length - 1].when;

// The card strip's five positions stand on the ladder's third to seventh rungs:
// the wish and the search come before anything is taken.
const STRIP_OFFSET = TEMPLATE.findIndex((rung) => rung.rung === "grabbed");

/**
 * The time a rung is drawn with, at the state it is laid in.
 *
 * A rung the seed's own journey passed carries that journey's time; a rung not
 * reached says so; any other carries nothing rather than a borrowed time.
 *
 * @param seeded The seed's rung.
 * @param state The state it is laid in.
 * @returns The time, as carried.
 */
function timeOf(seeded: Rung, state: RungState): string {
  if (state === PENDING) return UPCOMING_WHEN;
  // A RUNG LAID DONE keeps only a DONE rung's time: the template's running rung
  // carries « en cours depuis 4 min », which is no date an ended rung can wear.
  if (state === DONE) return seeded.state === DONE ? seeded.when : "";
  return seeded.state === DONE || seeded.state === RUNNING_NOW ? seeded.when : "";
}

/**
 * Lays one rung at a state — and, for the rung that merges several steps, its
 * steps: all passed when it is, the first at its state when it is current.
 *
 * @param seeded The seed's rung.
 * @param state The state it is laid in.
 * @returns The rung.
 */
function laid(seeded: Rung, state: RungState): Rung {
  const rung: Rung = { rung: seeded.rung, state, when: timeOf(seeded, state) };
  if (seeded.steps !== undefined) {
    rung.steps = seeded.steps.map((step, index) => {
      const stepState = state === DONE ? DONE : index === 0 && state !== PENDING ? state : PENDING;
      return { rung: step.rung, state: stepState, when: timeOf(step, stepState) };
    });
  }
  return rung;
}

/**
 * The ladder of a medium standing at one position.
 *
 * A RUNG ITS ROW NEVER LIVED IS NOT PASSED: before the row's first rung it is
 * not reached, and drawn with no time — « demandé » is passed only on the date
 * a follow carries, and « cherché » on none the seeds hold.
 *
 * @param position Its current rung and that rung's state.
 * @param origin What its own row lived.
 * @returns The eight rungs.
 */
function positioned(position: Position, origin: Origin): Rung[] {
  const from = rungIndex(origin.from ?? "grabbed");
  const asked = rungIndex("requested");
  // A DIRECT ADD BEGINS AT « ARRIVÉ » (ruling 4) once it has arrived: the wish,
  // the search, the grab and the download were nobody's here, so they are drawn
  // never lived and carry no time — a time would be the template's, borrowed.
  const arrived = rungIndex("arrived");
  const arrivedDirect = origin.direct === true && position.current >= arrived;
  return TEMPLATE.map((seeded, index) => {
    if (arrivedDirect && index < arrived) return { rung: seeded.rung, state: SKIPPED, when: "" };
    if (index < position.current && index === asked && origin.asked !== undefined && from > asked)
      return { rung: seeded.rung, state: DONE, when: origin.asked };
    if (index < position.current && index < from) return { rung: seeded.rung, state: PENDING, when: "" };
    const rung = laid(seeded, index < position.current ? DONE : index === position.current ? position.state : PENDING);
    if (index === position.current && position.reason !== undefined) rung.reason = position.reason;
    return rung;
  });
}

/**
 * Where a card's seeded strip puts it on the ladder.
 *
 * @param strip The five positions: `1` passed, a state token where it stands, `0` not reached.
 * @returns The position, or undefined for a card that carries no strip.
 */
export function stripPosition(strip: (number | string)[] | undefined): Position | undefined {
  if (strip === undefined) return undefined;
  const standing = strip.findIndex((value) => value !== 1);
  if (standing === -1) return { current: STRIP_OFFSET + strip.length - 1, state: DONE };
  const value = strip[standing];
  const state: RungState = value === RUNNING_NOW ? RUNNING_NOW : value === BLOCKED ? BLOCKED : PENDING;
  return { current: STRIP_OFFSET + standing, state };
}

/**
 * The index of a rung on the ladder.
 *
 * @param token The rung's token.
 * @returns Its index.
 */
export function rungIndex(token: Rung["rung"]): number {
  return TEMPLATE.findIndex((rung) => rung.rung === token);
}

/**
 * One medium's ladder, laid the first time it is asked for and held after.
 *
 * THE SAME ARRAY ON EVERY CALL, so a verb that moves it moves what the card and
 * the sheet both read next. A medium no card has positioned follows the seed's
 * own journey.
 *
 * @param subject The medium.
 * @param position Where its card puts it, when a card does.
 * @param origin What its own row lived.
 * @returns Its rungs.
 */
export function ladderOf(subject: string, position?: Position, origin: Origin = {}): Rung[] {
  const state = mockState();
  const held = state.journeyStages[subject];
  if (held !== undefined) return held;
  const fresh = position === undefined
    ? TEMPLATE.map((seeded) => laid(seeded, seeded.state))
    : positioned(position, origin);
  state.journeyStages[subject] = fresh;
  return fresh;
}

/**
 * Whether a medium is confirmed in the library: its last rung, « vérifié dans
 * Plex », done (ruling 3).
 *
 * @param subject The medium.
 * @returns True once that rung is done on the ladder the layer holds.
 */
export function isVerifiedInPlex(subject: string): boolean {
  const held = mockState().journeyStages[subject];
  return held !== undefined && held[held.length - 1].state === DONE;
}

/**
 * Lays one medium's ladder again, one event away from the last rung: every rung
 * before « vérifié dans Plex » done, that one pending.
 *
 * @param subject The medium.
 */
export function placeAtPlexCheck(subject: string): void {
  delete mockState().journeyStages[subject];
  ladderOf(subject, { current: TEMPLATE.length - 1, state: PENDING });
}

/**
 * Marks the last rung done — the medium confirmed in the library.
 *
 * @param subject The medium.
 */
export function confirmInPlex(subject: string): void {
  const ladder = ladderOf(subject);
  // IN PLACE: the array the card and the sheet read is the one that moves.
  TEMPLATE.forEach((seeded, index) => { ladder[index] = laid(seeded, DONE); });
}

/**
 * Forgets one medium's ladder, so the next read lays it where its card now stands.
 *
 * @param subject The medium.
 */
export function forgetLadder(subject: string): void {
  delete mockState().journeyStages[subject];
}
