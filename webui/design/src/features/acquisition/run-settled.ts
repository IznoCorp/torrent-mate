// Following an asked acquisition run until it has settled.
//
// WHY THIS READS ON A CLOCK, where the cache otherwise never does. A search is queued (operator ruling
// O-6 B): its result is on the follow and in the release picker only once its run has ended, and no
// event says so. The run the 202 named is therefore read until it settles — BOUNDED, with a wait that
// grows, and only for an ask this interface made.
import { isRequestFailure, read } from "../../lib/query-client";
import type { AcquisitionStatus } from "./queries";

const FIRST_WAIT_MILLISECONDS = 1_000;
const LONGEST_WAIT_MILLISECONDS = 10_000;
/** How long a run is followed; past it, what the reads hold is shown as it stands. */
const FOLLOWED_FOR_MILLISECONDS = 5 * 60_000;
const NO_SESSION = 401;

/**
 * Waits until an acquisition run has settled, or until it has been followed long enough.
 *
 * @param runUid The run the ask was answered with.
 */
export async function runSettled(runUid: string): Promise<void> {
  const question = new URLSearchParams({ runUid });
  let wait = FIRST_WAIT_MILLISECONDS;
  for (let waited = 0; waited < FOLLOWED_FOR_MILLISECONDS; waited += wait, wait = Math.min(wait * 2, LONGEST_WAIT_MILLISECONDS)) {
    await new Promise((resume) => setTimeout(resume, wait));
    try {
      const { runState } = await read<AcquisitionStatus>("/api/v1/acquisition/status", question);
      // NULL: no run answers to that uid, so there is nothing left to wait for.
      if (runState === "settled" || runState === null) return;
    } catch (failure) {
      // THE SESSION IS GONE: every further read would be refused, and each refusal calls the sign-in gate.
      if (isRequestFailure(failure) && failure.status === NO_SESSION) return;
      // ANY OTHER FAILED READ SAYS NOTHING OF THE RUN: it is asked again, inside the same bound.
    }
  }
}
