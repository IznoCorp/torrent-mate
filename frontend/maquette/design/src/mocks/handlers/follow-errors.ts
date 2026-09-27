// A follow's folder stopped on an error: posed for the harness, and abandoned
// without ending the follow.
import { mockState } from "../state";
import { forgetLadder } from "./ladder";
import { releasesFor } from "./releases-of";
import type { components } from "../../contract/types";

type QueueCard = components["schemas"]["QueueCard"];

// A strip's cell in motion, and the same cell stopped.
const RUNNING_NOW = "now";
const BLOCKED = "blocked";

/**
 * Poses a tunnel error on a follow's folder in flight, until the layer is next
 * reset — a derivation, shown as one (RULINGS 26): no seeded row of a follow
 * carries one; the backend reads the follow's own failed step.
 *
 * @param title The folder, one a follow asked for.
 * @param step The pipeline step it stopped at.
 */
export function poseTunnelError(title: string, step: NonNullable<QueueCard["failedStep"]>): void {
  const state = mockState();
  state.moving = state.moving.map((card) => {
    if (card.title !== title) return card;
    const strip = (card.strip ?? []).map((value) => (value === RUNNING_NOW ? BLOCKED : value));
    const { chip, ...stopped } = card;
    void chip;
    return { ...stopped, strip, failedStep: step };
  });
  // STOPPED, NOT IN FLIGHT: the medium's card in the queue's flight leaves
  // while its folder waits on the error, or the two would lay one ladder twice.
  state.inFlight = state.inFlight.filter((card) => card.title !== title);
  forgetLadder(title);
}

/**
 * « Abandonner » on a FOLLOW's folder: quarantined, and the follow goes on.
 *
 * The release it held joins the ones already tried, which the release read no
 * longer offers, and the medium is back in flight on « cherché » — another
 * release will be searched (§14.1). A one-off arrival's card closes instead.
 *

 * @param title The folder.
 * @param followed Whether a follow asked for a card — the staging area's own match.
 * @returns Whether the folder was a follow's, and was put back to be searched.
 */
export function backToSearch(title: string, followed: (card: QueueCard) => boolean): boolean {
  const state = mockState();
  const found = state.moving.find((card) => card.title === title);
  if (found === undefined || !followed(found)) return false;
  const [release] = releasesFor(title);
  if (release !== undefined) {
    state.triedReleases[title] = [...(state.triedReleases[title] ?? []), String(release.name ?? "")];
  }
  state.moving = state.moving.filter((card) => card !== found);
  forgetLadder(title);
  const { failedStep, chip, ...searched } = found;
  void failedStep;
  void chip;
  state.inFlight = [{ ...searched, strip: [0, 0, 0, 0, 0] }, ...state.inFlight];
  return true;
}
