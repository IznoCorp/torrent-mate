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
import { QueryClient, useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { holdBack, setDeparture } from "../app/outbox";
import type { paths } from "../contract/types";

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
 * What `send()` answers when a mutation was HELD rather than sent.
 *
 * WHY THE CALLER MUST BE ABLE TO TELL. Every mutation in this tree refreshes
 * its query when it settles, so the surface shows what the server holds. On the
 * held path there is nothing new to show and the refetch is actively harmful:
 * reads can work while a mutation's request does not — an aborted request, a
 * verb a proxy blocks — and the refetch then replaces the OPTIMISTIC write with
 * server state that does not contain the mutation. The operator's action snaps
 * back with no explanation, minutes before it actually applies. That is the
 * rollback-without-a-failure this lot exists to prevent, arriving through the
 * refresh instead of through the rejection.
 *
 * A SENTINEL AND NOT `undefined`, because `undefined` already means « a status
 * that carries no body » (204, 205, 304), and a caller cannot act on an answer
 * that means two things.
 */
export const HELD = Symbol("held");

/**
 * The title a failure carries when the layer answered something unreadable.
 *
 * It is a NAMED constant because two places must agree on it: the branch that
 * manufactures the failure, and the one that decides whether an answer is final
 * enough to drop a queued mutation over. A proxy's HTML 502 arrives here, and
 * discarding the operator's action over it would be the worst outcome of all.
 */
const UNREADABLE = "an answer this layer could not read";

/**
 * The answers that will not change however often the request is repeated.
 *
 * IT IS A LIST OF WHAT IS FINAL, NOT OF WHAT IS NOT, and that inversion is the
 * repair. The first version excluded 408, 429 and the 5xx and treated
 * everything else at or above 400 as settled — which made **401 final**, so an
 * expired session destroyed every queued mutation on the next `online` edge,
 * one after another, when a re-login would have made all of them succeed. That
 * is the exact harm the change was written to remove, surviving in the half of
 * the range nobody enumerated.
 *
 * A deny-list is wrong here by construction: the safe direction is to KEEP the
 * operator's action, so anything unlisted must be kept. Only a status that says
 * something about the REQUEST — its shape, its target, its conflict with the
 * world — belongs here. Nothing about the caller's identity does: 401 and 403
 * change when a session or a right changes, and 423 unlocks.
 */
const FINAL_STATUSES = new Set([
  400, // malformed — sending it again sends the same malformed thing
  404, // the target does not exist
  405, // the method is not one this address takes
  409, // a conflict with the world as it now is
  410, // gone, and stated as permanent
  415, // a body shape the layer will never read
  422, // understood, and refused on its content
]);

// A NUMBER THAT ONLY RISES, so two envelopes accepted inside one millisecond
// still replay in the order the operator made them.
let accepted = 0;

/**
 * A fresh identity for one mutation.
 *
 * @returns A key nothing else will produce. `randomUUID` needs a secure
 *     context, which `localhost` and the design host both are; the fallback
 *     exists so that a plain-HTTP preview degrades to a weaker key rather than
 *     throwing where a mutation would otherwise have worked.
 */
function newIdempotencyKey(): string {
  const source = globalThis.crypto;
  if (source && typeof source.randomUUID === "function") return source.randomUUID();
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

// THE REPLAY CALLS THE SAME FUNCTION THE FIRST ATTEMPT DID, with the same key
// and the same body — MODEL Part 13's « replay calls the same mutation
// function ». It is injected rather than imported by the outbox, because the
// outbox is imported HERE and a cycle between a queue and what it queues is the
// kind that survives review: both halves read naturally on their own.
setDeparture(
  async (envelope) => {
    await dispatch(envelope.method, envelope.path, envelope.body, envelope.key);
  },
  // WHETHER THE ANSWER IS FINAL — the only thing the queue needs to know, and
  // the only thing it may know.
  //
  // « DID THE LAYER ANSWER? » WAS TOO WIDE, and it destroyed the operator's
  // action in the very case the queue exists for: a 503 from a restarting
  // backend is an answer, and so is the named failure this module manufactures
  // for a body it could not read — which is what a proxy's HTML 502 looks like.
  // A 401 after a session expires would have taken every queued mutation with
  // it on the next `online` edge.
  isFinalAnswer,
);

/**
 * Tells whether re-sending would ever produce a different answer.
 *
 * @param failure What the departure threw.
 * @returns True only for a decision that is settled — a 4xx the client cannot
 *     retry its way out of. Anything unread, unreachable, overloaded or
 *     temporary is NOT final, and its envelope stays in the queue.
 */
function isFinalAnswer(failure: unknown): boolean {
  if (!isRequestFailure(failure)) return false;
  // A body this layer could not read is not a decision it can act on: the
  // status may be a proxy's, not the application's.
  if (failure.title === UNREADABLE) return false;
  return FINAL_STATUSES.has(failure.status);
}

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
): Promise<Result | undefined | typeof HELD> {
  const key = newIdempotencyKey();
  try {
    return await dispatch<Result>(method, path, body, key);
  } catch (refused) {
    // A REFUSAL AND AN OUTAGE ARE NOT THE SAME EVENT, and telling them apart is
    // the whole of this branch. A layer that ANSWERS — 404, 409, 500 — has made
    // a decision the operator must see, and it is re-thrown untouched so the
    // surface ROLLS BACK. Saying why is the surface's half and it is not built:
    // every call site rethrows into a `void`ed promise nobody handles, so a
    // refusal today is a row that snaps back with no reason given. Recorded
    // rather than claimed — this comment said « and says why », and that half
    // of the sentence had no implementation anywhere in the tree.
    // A network that does not answer at all
    // has decided nothing: the mutation has not failed, it has not departed,
    // and rolling it back would erase an action the operator made and that is
    // still going to happen.
    if (isRequestFailure(refused)) throw refused;
    accepted += 1;
    const held = await holdBack({
      key, method, path, body, accepted: Date.now(), order: accepted,
    });
    // COULD NOT EVEN BE KEPT — no storage at all, a private window. Then the
    // mutation really is lost, and the ONE thing that must not happen is
    // reporting it as accepted. It is re-thrown as what it is.
    if (!held) throw refused;
    // HELD, and said so. The optimistic write stands, the pending count the
    // outbox publishes tells the operator it has not left yet, and the caller
    // knows not to refetch over the top of its own optimistic write.
    return HELD;
  }
}

/**
 * Issues one mutation, with the identity a replay will re-use.
 *
 * SPLIT OUT OF `send()` BECAUSE THE REPLAY NEEDS EXACTLY THIS AND NOT THE REST.
 * Re-issuing an envelope through `send()` would generate a NEW key and enqueue
 * again on a second failure — a queue that grows a copy of itself every time
 * the network flickers.
 *
 * @param method The method, upper case.
 * @param path The contract address, parameters already substituted.
 * @param body What to send, if anything.
 * @param key The idempotency key the layer deduplicates on.
 * @returns The parsed answer, or undefined for a status that carries no body.
 * @throws RequestFailure When the layer refuses, carrying its real reason.
 */
async function dispatch<Result>(
  method: string,
  path: string,
  body: unknown,
  key: string,
): Promise<Result | undefined> {
  const answer = await globalThis.fetch(path, {
    method,
    // A body is sent as a JSON STRING and nothing else: the mock layer refuses
    // a form, a blob or a stream by name rather than answering 200 over a
    // mutation that never happened, and the real server will read the same.
    //
    // THE KEY TRAVELS ON EVERY MUTATION, not only on a replay. A key added only
    // when something is re-sent would be a key the layer had never seen the
    // first time, and « exactly once » would hold for everything except the one
    // case where a request departed and its answer was lost.
    headers: {
      "idempotency-key": key,
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  // 204, 205 and 304 carry no body at all, and asking one for JSON throws —
  // which would turn a mutation that SUCCEEDED into a rollback.
  if (answer.status === 204 || answer.status === 205 || answer.status === 304) {
    return undefined;
  }
  // A BODY THAT IS NOT JSON IS STILL AN ANSWER. `answer.json()` throws on an
  // HTML 502 from a proxy, on an auth redirect page, on an empty 200 — and a
  // `SyntaxError` carries no `status`, so the caller would read it as an
  // OUTAGE and queue a request the layer has already decided about, which jams
  // the queue behind it. The layer answered; what it answered is unreadable,
  // and that is what gets said.
  let parsed: unknown;
  try {
    parsed = await answer.json();
  } catch (unreadable) {
    const failure: RequestFailure = {
      status: answer.status,
      title: UNREADABLE,
      detail: `${method} ${path} answered ${answer.status} with a body that is not JSON`,
    };
    throw failure;
  }
  if (!answer.ok) throw parsed as RequestFailure;
  return parsed as Result;
}

/**
 * A number that changes whenever any server state does.
 *
 * WHY THE FRAME NEEDS ONE. A badge in the chrome is DERIVED from server state —
 * what is waiting to be taken, what is stuck — and a component that reads that
 * derivation synchronously is not subscribed to it. The tab bar re-rendered on
 * every store write and on nothing else, so a badge went on showing the
 * previous scenario's count until an unrelated interface change happened to
 * redraw it. The engine did not have this problem for the wrong reason: its bar
 * was rebuilt by `render()`, which the cache's own redraw hook calls — the same
 * mechanism that made the chrome's nodes disposable (B-231).
 *
 * IT NAMES NOTHING. The frame does not know WHICH query moved, and must not:
 * it re-derives its badges and lets React reconcile. What a badge counts is the
 * feature's, through the function the navigation table points at.
 *
 * The snapshot is a SUM OF INSTANTS rather than a counter, so it needs no
 * installer and no module state: two renders of an unchanged cache read the
 * same number, which is what `useSyncExternalStore` requires.
 *
 * @returns A value that differs after any query's data has been updated.
 */
export function useServerStateVersion(): number {
  const client = useQueryClient();
  return useSyncExternalStore(
    (onChange) => client.getQueryCache().subscribe(() => onChange()),
    () =>
      client
        .getQueryCache()
        .getAll()
        .reduce((total, query) => total + query.state.dataUpdatedAt, 0),
  );
}
