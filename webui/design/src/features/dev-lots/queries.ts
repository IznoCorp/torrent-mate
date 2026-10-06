// The lots progress, as the design host serves it.
//
// IT IS NO OPERATION OF THE CONTRACT. `/dev/lots.json` is a file the host
// serves beside the document — the work's progress, generated outside the
// repository on the host's schedule — so it is read through `askTheHost`, past
// the mock layer that answers the contract and 404s everything else on purpose.
//
// A 404 IS AN ANSWER, not a failure: the host was not given the file (every
// host but the design host), and the page says there is nothing to show.
import { askTheHost } from "../../lib/platform-network";

/** Where a phase stands, the furthest fact first. */
export type PhaseState = "planned" | "in-progress" | "pr-open" | "merged";

/** A pull request of a phase. */
export type LotPullRequest = {
  /** Its number on the repository. */
  number: number;
  /** Its page. */
  url: string;
  /** Open or merged; a closed one is never listed. */
  state: "open" | "merged";
};

/** One phase of a lot. */
export type LotPhase = {
  /** The plan's id for it. */
  id: string;
  /** The plan's title for it. */
  title: string;
  /** Where it stands. */
  state: PhaseState;
  /** The dispatch state of the work in progress on it, when there is one. */
  dispatch: string | null;
  /** What blocks it, in the definition's words. */
  blockedBy: string | null;
  /** Its pull requests, by number. */
  prs: LotPullRequest[];
};

/** One lot. */
export type Lot = {
  /** Its id. */
  id: string;
  /** Its name. */
  name: string;
  /** What blocks it, in the definition's words. */
  blockedBy: string | null;
  /** Its phases, in the definition's order. */
  phases: LotPhase[];
};

/** The generated document: available with its lots, or not available at all. */
export type LotsDocument =
  | { available: true; generatedAt: number; lots: Lot[] }
  | { available: false };

/** The address the host serves it at, and the key its read is cached under. */
export const LOTS_ADDRESS = "/dev/lots.json";
export const lotsKey = [LOTS_ADDRESS];

/** The answer a host without the file gives. */
const NOT_SERVED = 404;

/**
 * Reads the lots progress from the host.
 *
 * @param ask What reaches the host; the platform's own network by default.
 * @returns The document, or `{ available: false }` when the host serves none.
 * @throws Error naming the status when the host answered anything else.
 */
export async function readLots(ask: typeof askTheHost = askTheHost): Promise<LotsDocument> {
  const answer = await ask(LOTS_ADDRESS, { credentials: "same-origin" });
  if (answer.status === NOT_SERVED) return { available: false };
  if (!answer.ok) throw new Error(`${LOTS_ADDRESS} answered ${answer.status}`);
  return (await answer.json()) as LotsDocument;
}
