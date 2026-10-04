// THE DESIGN HOST'S WAY THROUGH (the operator, 2026-10-04; Q1 = A — hybrid).
//
// tm-design is where the interface is developed against the real server: an
// operation v1 serves is sent to it, and every other one stays answered by this
// layer until v1 serves it too. WHICH OPERATIONS is read off the served
// document, `frontend/openapi-v1.json`, by operation id — its paths carry no
// server URL, and the id is what the maquette's routes are keyed by.
//
// THE DESIGN HOST ONLY. `__DESIGN_HOST__` is true in the `--mode design-host`
// build alone; the harness, the unit suite and continuous integration build
// without it, so the branch that calls this is dead there and the bundler drops
// this module and the document with it — nothing they read can reach a network.
import V1 from "../../../../openapi-v1.json";
import { recordAnswered } from "./answered";

/** The part of an OpenAPI document this reads: its operations, by path then method. */
type ServedDocument = { paths: Record<string, Record<string, { operationId?: string }>> };

/**
 * Every operation one document serves.
 *
 * @param document The OpenAPI document.
 * @returns Its operation ids.
 * @throws Error When it declares none — a set read empty would send nothing
 *     through and look exactly like a layer working as built.
 */
export function servedOperations(document: ServedDocument): ReadonlySet<string> {
  const served = new Set<string>();
  for (const verbs of Object.values(document.paths)) {
    for (const operation of Object.values(verbs)) {
      if (operation.operationId) served.add(operation.operationId);
    }
  }
  if (served.size === 0) throw new Error("the design host's passthrough: openapi-v1.json declares no operation");
  return served;
}

// Read once, on the first call that asks.
let served: ReadonlySet<string> | undefined;

/**
 * Whether one operation goes to the real server rather than to the mocks.
 *
 * @param operationId The operation, as the contract names it.
 * @param designHost Whether this is the design host's build.
 * @returns True on the design host for an operation v1 serves.
 */
export function passesThrough(operationId: string, designHost: boolean = __DESIGN_HOST__): boolean {
  if (!designHost) return false;
  served ??= servedOperations(V1 as ServedDocument);
  return served.has(operationId);
}

/**
 * Sends one request to the real server, and records it as the layer records
 * every call it answers — with the status the server gave.
 *
 * @param network The browser's own `fetch`, as it was before the layer replaced it.
 * @param call The operation, its method and its path.
 * @param input What was asked for.
 * @param options The request options, untouched.
 * @returns The server's answer, as it came.
 */
export async function throughNetwork(
  network: typeof globalThis.fetch,
  call: { operationId: string; method: string; path: string },
  input: RequestInfo | URL,
  options?: RequestInit,
): Promise<Response> {
  const answer = await network(input, options);
  recordAnswered({ ...call, status: answer.status });
  return answer;
}

declare global {
  /**
   * Whether this is the design host's build (`--mode design-host`). Replaced at
   * build time, so a false value makes the passthrough's call site dead code.
   */
  const __DESIGN_HOST__: boolean;
}
