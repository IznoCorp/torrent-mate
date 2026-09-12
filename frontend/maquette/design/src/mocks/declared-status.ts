// WHAT SUCCESS MEANS FOR ONE OPERATION, read off the contract itself.
//
// THE DEFECT THIS ENDS (B-379). `scenario.ts` answered every unarmed call with
// a literal 200, whatever the contract declared for it. Three operations
// declare something else — `grabSeasonForFollow` a 201, `requeueJourney` and
// `rescrapeJourney` a 202 — so no rule could hold a declared success code, and
// a sentence saying the layer « answers 201 » was false ON THE CODE while the
// payload beside it was right. Measured by R158 on its first run: four season
// grabs, four `status: 200` in `window.__mocks.answered()`.
//
// IT READS THE CONTRACT AND NEVER A TABLE. A hand-written map from operation to
// status is a second declaration of something the contract already says, and
// the day the contract gains an operation that answers 201 the map stays right
// about everything it already knew — which is the shape of every drift this
// repository has paid for. The artefact imported here IS the one
// `contract/README.md` calls the maquette's own data contract, the same file
// `contract-conformance.test.ts` reads.
//
// WHAT IT COSTS, said rather than glossed: the contract travels in the bundle.
// It is 144 KB beside the 2.1 MB of seeds this layer already carries, and the
// whole module is dropped with the layer when `__MOCKS_BUILT_IN__` is false —
// so it weighs nothing at all in a build that ships.
import contract from "../../../contract/openapi.json";

/** The status an operation answers when the contract declares none. */
const PLAIN_SUCCESS = 200;

/** The band a success lives in. */
const FIRST_SUCCESS = 200;
const FIRST_REDIRECT = 300;

type Operation = { operationId?: string };

const PATHS = (contract as unknown as {
  paths: Record<string, Record<string, Operation & {
    responses?: Record<string, unknown>;
  }>>;
}).paths;

/**
 * The success code each operation declares, keyed by its operationId.
 *
 * BUILT ONCE, at module evaluation, because the contract cannot change while
 * the page is open — and a reader that walked the whole document on every
 * answered call would put the contract's size on the hot path of every request
 * the layer serves.
 *
 * THE LOWEST DECLARED 2xx WINS where an operation declares several. None does
 * today (58 operations, one code each), and picking the lowest rather than the
 * first is what makes that stay true of a JSON object whose key order nobody
 * should have to depend on.
 */
const DECLARED = new Map<string, number>();

for (const methods of Object.values(PATHS)) {
  for (const operation of Object.values(methods)) {
    const operationId = operation.operationId;
    if (operationId === undefined) continue;
    const codes = Object.keys(operation.responses ?? {})
      .map((code) => Number(code))
      .filter((code) =>
        Number.isInteger(code) && code >= FIRST_SUCCESS && code < FIRST_REDIRECT);
    if (codes.length === 0) continue;
    DECLARED.set(operationId, Math.min(...codes));
  }
}

/**
 * The status one operation answers when nothing has asked it to fail.
 *
 * AN OPERATION THE CONTRACT DOES NOT DECLARE ANSWERS 200 rather than throwing,
 * and the choice is deliberate: this function runs inside the answer path of
 * every request, so raising here would turn a table/contract drift into a page
 * that cannot load, hiding the drift behind a symptom. The drift itself is held
 * by R85, which refuses a route the contract does not declare, and by
 * `declaredSuccessStatuses()` below, which lets a rule read the whole map.
 *
 * Args:
 *     operationId: The operation, as the contract names it.
 *
 * Returns:
 *     Its declared success status, or 200.
 */
export function declaredSuccessStatus(operationId: string): number {
  return DECLARED.get(operationId) ?? PLAIN_SUCCESS;
}

/**
 * Every declared success status, by operation.
 *
 * Published so a rule can read what the contract says WITHOUT re-implementing
 * the walk above — a rule that parsed the contract itself would be a second
 * reader that can agree with a broken one.
 *
 * Returns:
 *     A copy, so a reader cannot edit the map it is reading.
 */
export function declaredSuccessStatuses(): Record<string, number> {
  return Object.fromEntries(DECLARED);
}
