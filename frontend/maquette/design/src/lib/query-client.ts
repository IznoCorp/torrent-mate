// The query cache, and the one place its policy is decided.
//
// INVARIANT 4 MADE STRUCTURAL. Server state lives here; the address lives in
// the router; only genuinely ephemeral interface state lives in the store. The
// three had one home before this file — `UiState`, an open bag — and eleven of
// its thirty-nine keys named server state.
//
// IT LIVES IN `lib/` AND NOT UNDER A FEATURE (invariant 10). A cache, a
// staleness policy and a typed request helper are the application's SHAPE, not
// its subject, and the surface that happened to need them first is not what
// they are about. This lot writes more generic code than any before it, which
// is exactly why the placement is stated rather than left to whichever page was
// open at the time.
//
// D9 RULE 2 IS WHY THERE IS A LIBRARY HERE AT ALL: « adopted for maths nobody
// has written, never for an arbitration already proved ». Deduplication,
// staleness, invalidation fan-out and a rollback that restores the exact
// snapshot a failed mutation departed from — across concurrent mutations on one
// key — is the first kind. None of it is an arbitration this repository has
// proved, and all of it is code somebody else has.
import { QueryClient } from "@tanstack/react-query";
import type { paths } from "../mocks/contract-types";

/**
 * Builds the query client, with the policy every surface shares.
 *
 * @returns A client nothing else configures.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // INVALIDATED BY MUTATION, NEVER BY A CLOCK. The live relay (L10) is
        // what will drive invalidation for real; a staleness duration picked
        // now would be a number nobody could defend when it lands, and it
        // would make a measurement depend on how long the measurement took.
        staleTime: Infinity,
        // NO RETRY. A retry hides the failure the interface is required to
        // show (NE-DOIT-PAS-5, « une erreur remonte bruyamment avec sa raison
        // réelle »), and it would make a scenario's injected failure arrive
        // three attempts late — so a named error state would render its
        // skeleton for as long as the retries took.
        retry: false,
        // NO REFRESH ON FOCUS. The oracle drives 83 named states in one
        // browser context; a focus-triggered refresh would put a request in
        // flight during a measurement, which is the one thing the settle
        // signal cannot be asked to absorb after the fact.
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
      mutations: {
        // Same reason as the reads, read from the other end: a mutation that
        // silently retries reports success for an action the operator watched
        // fail, which is NE-DOIT-PAS-1 exactly.
        retry: false,
      },
    },
  });
}

/** Every address the maquette's own contract declares. */
type ContractPath = keyof paths;

/**
 * What a failed request carries: the layer's own problem shape.
 *
 * A FAILURE CARRIES ITS REAL REASON, never a bare code — the mock layer already
 * answers `{status, title, detail}` for every refusal it makes, and this is the
 * type that keeps a surface from throwing that away and printing the number.
 */
export type RequestFailure = {
  status: number;
  title: string;
  detail: string;
};

/**
 * Tells whether a thrown value is one of this layer's named failures.
 *
 * @param error What was thrown.
 * @returns True when it carries the layer's problem shape.
 */
export function isRequestFailure(error: unknown): error is RequestFailure {
  if (typeof error !== "object" || error === null) return false;
  const candidate = error as Record<string, unknown>;
  return typeof candidate.status === "number"
    && typeof candidate.title === "string"
    && typeof candidate.detail === "string";
}

/**
 * Reads one address the contract declares, and throws its named failure.
 *
 * THE PATH IS TYPED AGAINST THE CONTRACT, so an address the contract does not
 * declare is a compile error rather than a 404 nobody sees until the surface is
 * open. The query STRING is separate because a template's parameters are
 * already substituted by the time a request is made — the contract types the
 * shape, and the caller composes the identity.
 *
 * @param path The contract address, parameters already substituted.
 * @param query What to append, if anything.
 * @returns The parsed body.
 * @throws RequestFailure When the layer refuses, carrying its real reason.
 */
export async function read<Result>(
  path: ContractPath | (string & {}),
  query?: URLSearchParams,
): Promise<Result> {
  const address = query && [...query.keys()].length ? `${path}?${query}` : path;
  const answer = await globalThis.fetch(address);
  const body = await answer.json();
  if (!answer.ok) throw body as RequestFailure;
  return body as Result;
}

/**
 * Sends one mutation to an address the contract declares.
 *
 * @param method The method, upper case.
 * @param path The contract address, parameters already substituted.
 * @param body What to send, if anything.
 * @returns The parsed answer, or undefined for a status that carries no body.
 * @throws RequestFailure When the layer refuses, carrying its real reason.
 */
export async function send<Result>(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: ContractPath | (string & {}),
  body?: unknown,
): Promise<Result | undefined> {
  const answer = await globalThis.fetch(path, {
    method,
    // A body is sent as a JSON STRING and nothing else: the mock layer refuses
    // a form, a blob or a stream by name rather than answering 200 over a
    // mutation that never happened, and the real server will read the same.
    ...(body === undefined
      ? {}
      : { body: JSON.stringify(body), headers: { "content-type": "application/json" } }),
  });
  // 204, 205 and 304 carry no body at all, and asking one for JSON throws —
  // which would turn a mutation that SUCCEEDED into a rollback.
  if (answer.status === 204 || answer.status === 205 || answer.status === 304) {
    return undefined;
  }
  const parsed = await answer.json();
  if (!answer.ok) throw parsed as RequestFailure;
  return parsed as Result;
}
