// The staging area's folders as the mock serves them: the three lists a
// folder is served from, taking one out, and whether it is the only copy.
//
// ITS OWN MODULE because the staging handlers are at their size ceiling; the
// lists are declared here so the handlers import them, never the reverse.
import { mockState } from "../state";

// Which of the staging worlds a card came from. Named because the pairing with
// the list it goes to is the decision, not the spelling.
export const FROM_REAL = "stuck";
export const FROM_DENSE = "stuckLoaded";
export const FROM_BLOCKED = "blocked";

// The lists a folder is served from, which every verb on a folder walks.
export const SOURCE_LISTS = [FROM_REAL, FROM_DENSE, FROM_BLOCKED] as const;

// A staged folder's three cases, the contract's own tokens.
const KEEPS_FILES = "keeps_files";
const ONLY_COPY = "only_copy";
const UNKNOWN = "unknown";

/**
 * Whether a staged folder is the only copy of its files.
 *
 * POSED, NOT READ (RULINGS 22): no fixture records a folder's ingest action or
 * its torrent, so « keeps its files » is only ever posed by the harness; a
 * folder dropped by hand has no torrent, so it is the only copy; any other
 * answers unknown — what the backend says when qBittorrent does not answer.
 *
 * @param title The folder.
 * @returns The case.
 */
export function copiesOf(title: string): string {
  const state = mockState();
  const posed = state.stagedCopies[title];
  if (posed !== undefined) return posed;
  const dropped = SOURCE_LISTS.some((list) => state[list].some((card) => card.title === title && card.droppedByHand));
  return dropped ? ONLY_COPY : UNKNOWN;
}

/**
 * Poses a folder's case until the layer is next reset — a derivation, shown as one (RULINGS 22).
 *
 * @param title The folder.
 */
export function poseKeepsItsFiles(title: string): void {
  mockState().stagedCopies[title] = KEEPS_FILES;
}

/**
 * Takes one folder out of the staging area, whichever list serves it.
 *
 * THE SAME THREE LISTS ITS SIBLINGS WALK. Filtering `stuck` alone once let a
 * card served from the DENSE world — or from « ça bloque » — be asked to go,
 * remove nothing and stay on screen: the list a card is IN is a fact about the
 * scenario in force, never about the operation asking.
 *
 * @param asked The folder.
 * @returns Whether a folder was taken out.
 */
export function takeOutOfStaging(asked: string): boolean {
  const state = mockState();
  for (const list of SOURCE_LISTS) {
    const before = state[list].length;
    state[list] = state[list].filter((card) => card.title !== asked);
    if (state[list].length !== before) return true;
  }
  return false;
}
