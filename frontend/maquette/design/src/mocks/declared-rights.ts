// WHAT EACH OPERATION ASKS FOR, read off the contract itself.
//
// THE CONTRACT IS WHAT A SERVER REFUSES BY. Its `x-rights` on every operation is
// what the backend builds its 403s on, so the layer refuses by the same words
// rather than by a table of its own: the day the two disagreed, the maquette
// would prove a refusal the server does not make. `OPERATION_RIGHTS` is where a
// right is decided and argued; `npm run stamp-operation-rights` writes it into
// the contract, and `operation-rights.test.ts` refuses a contract that drifts
// from it.
//
// BUILT ONCE, at module evaluation, as `declared-status.ts` builds its map, and
// for the same reason: the contract cannot change while the page is open.
import contract from "../../../contract/openapi.json";
import type { Asked } from "./operation-rights";

type Operation = { operationId?: string; "x-rights"?: Asked };

const PATHS = (contract as unknown as { paths: Record<string, Record<string, Operation>> }).paths;

const DECLARED = new Map<string, Asked>();

for (const methods of Object.values(PATHS)) {
  for (const operation of Object.values(methods)) {
    if (operation.operationId === undefined || !("x-rights" in operation)) continue;
    DECLARED.set(operation.operationId, operation["x-rights"] ?? null);
  }
}

/**
 * What one operation asks for, as the contract declares it.
 *
 * Args:
 *     operationId: The operation, as the contract names it.
 *
 * Returns:
 *     A right, any of several, or null — and null for an operation the contract
 *     does not carry, which `operation-rights.test.ts` makes unreachable.
 */
export function declaredRights(operationId: string): Asked {
  return DECLARED.get(operationId) ?? null;
}
