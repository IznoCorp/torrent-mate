// An arrival in flight whose identity is not known yet: posed for the harness.
import { mockState } from "../state";
import { forgetLadder } from "./ladder";

// The staging strip's cells: done, in motion, pending.
const DONE = 1;
const RUNNING_NOW = "now";
const PENDING = 0;
// Where identifying stands on the staging strip: after the arrival and the sort.
const IDENTIFYING = 2;

/**
 * Poses an arrival in flight the sort has not identified yet, until the layer
 * is next reset — a derivation, shown as one: every seeded arrival in flight is
 * already identified; the backend reads the « identifié » rung in progress.
 *
 * The card loses its identifiers and stands on the identifying step; its chip
 * goes rather than carrying a word no row says.
 *
 * @param title The folder, one of the staging area's arrivals in flight.
 */
export function poseUnknownIdentity(title: string): void {
  const state = mockState();
  state.moving = state.moving.map((card) => {
    if (card.title !== title) return card;
    const strip = (card.strip ?? []).map((_value, index) =>
      index < IDENTIFYING ? DONE : index === IDENTIFYING ? RUNNING_NOW : PENDING);
    const { chip, ...unknown } = card;
    void chip;
    // NO IDENTITY: the contract's own « no sheet identifies it yet ».
    return { ...unknown, ids: null, strip };
  });
  forgetLadder(title);
}
