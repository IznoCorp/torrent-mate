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

/** Where a medium stands: the index of its current rung, and that rung's state. */
export type Position = { current: number; state: RungState };

// The seed is ONE journey, followed from the wish to Plex; every ladder is laid
// on its rungs and takes its times from it.
const TEMPLATE = JOURNEY_STAGES as Rung[];

const DONE = "done";
const RUNNING_NOW = "now";
const BLOCKED = "blocked";
const PENDING = "pending";

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
 * @param position Its current rung and that rung's state.
 * @returns The eight rungs.
 */
function positioned(position: Position): Rung[] {
  return TEMPLATE.map((seeded, index) =>
    laid(seeded, index < position.current ? DONE : index === position.current ? position.state : PENDING));
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
 * @returns Its rungs.
 */
export function ladderOf(subject: string, position?: Position): Rung[] {
  const state = mockState();
  const held = state.journeyStages[subject];
  if (held !== undefined) return held;
  const fresh = position === undefined
    ? TEMPLATE.map((seeded) => laid(seeded, seeded.state))
    : positioned(position);
  state.journeyStages[subject] = fresh;
  return fresh;
}

/**
 * Forgets one medium's ladder, so the next read lays it where its card now stands.
 *
 * @param subject The medium.
 */
export function forgetLadder(subject: string): void {
  delete mockState().journeyStages[subject];
}
