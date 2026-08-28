// The seam: one network call site, and no service worker.
//
// WHY NOT A SERVICE WORKER. The oracle measures at first paint, and a worker's
// registration is asynchronous — a page can render once before the worker
// controls it, which is a race an oracle cannot be asked to absorb. The real
// service worker belongs to the offline lot, and two contending for one scope
// is an arbitration nobody should have to hold. The harness also reads a MANUAL
// static copy served by one host while the design host is another; a worker
// script would have to be served correctly at the root by both.
//
// WHAT IT COSTS, and it is recorded rather than glossed: the browser's own
// network stack is not exercised, so what a real request does with caching and
// redirects is not proved here. The seam is ONE module, and the switchover
// replaces its implementation rather than its call sites.
//
// A REQUEST THIS LAYER CANNOT ANSWER FAILS AND NAMES ITSELF — an unclaimed
// route, a foreign origin, a body it cannot read. Never a pass-through to the
// network, never a silent empty object, and never a rejected promise: a mock
// that answers something to everything hides a missing handler, and one that
// throws hides the reason.
import { resolve, type MockRoute } from "./router";
import {
  outcomeFor,
  resetScenario,
  scenario,
  setDefaultLatency,
  setOperationOutcome,
} from "./scenario";
import { resetMockState } from "./state";
import { installMockStream, resetStream, type StreamDriver } from "./stream";
import { routes } from "./handlers";

/** The signature this module replaces. */
type NetworkCall = typeof globalThis.fetch;

// Whether the seam is already in place. NOT the previous implementation: there
// is no uninstall, so keeping one would be a claim nothing honours.
let installed = false;
let inFlight = 0;
// Deliveries dispatched whose fan-out has not been issued yet. A SECOND
// COUNTER and not a second signal: `quiet()` is the one thing the oracle's
// settle reads, and a rule that had to await two signals would be a rule that
// can await the wrong one.
let delivering = 0;
let becameQuiet: (() => void)[] = [];

// The statuses that carry NO body. Building a response with one throws, so a
// scenario asking a DELETE to answer 204 — the obvious thing to ask of a
// DELETE — would make the request reject instead of answering.
const BODILESS_STATUSES = new Set([204, 205, 304]);

/**
 * Reads what a request is asking for, whatever shape it was written in.
 *
 * A REQUEST OBJECT IS THE NORMAL SHAPE for anything that builds a request
 * before dispatching it — an interceptor, a retry wrapper, most typed clients —
 * and reading the method off the options alone turned every one of those into a
 * GET, and then into a 404.
 *
 * @param input What was passed as the first argument.
 * @param options What was passed as the second, if anything.
 * @returns The address, the method, and the raw body.
 */
function asked(
  input: RequestInfo | URL,
  options?: RequestInit,
): { href: string; method: string; body: BodyInit | null | undefined } {
  if (typeof input === "string") {
    return { href: input, method: options?.method ?? "GET", body: options?.body };
  }
  if (input instanceof URL) {
    return { href: input.href, method: options?.method ?? "GET", body: options?.body };
  }
  return { href: input.url, method: options?.method ?? input.method, body: options?.body };
}

/**
 * Answers one request from the routing table.
 *
 * @param input What was asked for.
 * @param options The request options.
 * @returns The response the contract declares for it, or a named failure.
 */
async function answer(input: RequestInfo | URL, options?: RequestInit): Promise<Response> {
  const request = asked(input, options);
  const address = new URL(request.href, globalThis.location.origin);
  if (address.origin !== globalThis.location.origin) {
    // Matching a foreign address on its PATH alone would have this layer answer
    // for a server it knows nothing about, and would hide a call that was never
    // meant to come here at all.
    return problem(
      502,
      "a foreign origin",
      `${address.origin} is not this application's own origin, and the mock layer answers ` +
        "only for it",
    );
  }
  const method = request.method.toUpperCase();
  const found = resolve(routes(), method, address.pathname);
  if (found === null) {
    return problem(
      404,
      "no mock route",
      `${method} ${address.pathname} is not an operation the maquette's contract declares`,
    );
  }

  const outcome = outcomeFor(found.route.operationId);
  if (outcome.latencyMilliseconds > 0) {
    await new Promise((settle) => {
      globalThis.setTimeout(settle, outcome.latencyMilliseconds);
    });
  }
  if (outcome.status >= 400) {
    return problem(
      outcome.status,
      "the scenario asked for this to fail",
      `${found.route.operationId} is set to answer ${outcome.status}`,
    );
  }

  let body: unknown;
  if (request.body !== undefined && request.body !== null) {
    if (typeof request.body !== "string") {
      return problem(
        415,
        "a body this layer cannot read",
        "the mock layer reads a JSON string body, so a form, a blob or a stream reaches no " +
          "handler — and answering 200 over one would report a mutation that never happened",
      );
    }
    try {
      body = JSON.parse(request.body);
    } catch {
      return problem(
        400,
        "a body that is not JSON",
        `${found.route.operationId} was sent a body that does not parse`,
      );
    }
  }
  const payload = found.route.handle({
    path: address.pathname,
    parameters: found.parameters,
    query: address.searchParams,
    body,
  });
  return json(outcome.status, payload);
}

/**
 * Builds a JSON response.
 *
 * @param status The status.
 * @param payload What it carries.
 * @returns The response.
 */
function json(status: number, payload: unknown): Response {
  const carries = !BODILESS_STATUSES.has(status);
  return new Response(carries ? JSON.stringify(payload) : null, {
    status,
    headers: carries ? { "content-type": "application/json" } : {},
  });
}

/**
 * Builds a failure that says what really went wrong.
 *
 * An error carries its real reason, never a bare code — the constitution's rule
 * applies to a mock as much as to the engine.
 *
 * @param status The status.
 * @param title What went wrong, in one line.
 * @param detail The real reason.
 * @returns The response.
 */
function problem(status: number, title: string, detail: string): Response {
  return json(status, { status, title, detail });
}

/**
 * Releases whatever is waiting on the quiet signal, one task later.
 *
 * A MACROTASK, AND THAT IS THE WHOLE OF IT. Waiters released inside the
 * settlement run BEFORE the application's own continuation on the same request,
 * so a waterfall — read, render, read again — reports quiet in the gap between
 * the two, while the second request has not been issued. One task's delay puts
 * the application's continuation first, so a request it is about to make is
 * already counted.
 */
function releaseWaiters(): void {
  globalThis.setTimeout(() => {
    if (inFlight !== 0 || delivering !== 0) return;
    const waiting = becameQuiet;
    becameQuiet = [];
    for (const settle of waiting) settle();
  }, 0);
}

/** Installs the seam. The page makes its network calls exactly as it did. */
export function installMockNetwork(): void {
  if (installed) return;
  installed = true;
  globalThis.fetch = ((input: RequestInfo | URL, options?: RequestInit) => {
    inFlight += 1;
    return answer(input, options).finally(() => {
      // FLOORED, NOT DECREMENTED. `reset()` zeroes the counters so a
      // desynchronised page has a way back — and a request already in flight
      // when it ran would then decrement past zero. At -1 both
      // `releaseWaiters` and `quiet()` are false FOR EVER: the repair for an
      // accidental desynchronisation would have made a deterministic and
      // unrecoverable one, on the signal all 2 871 oracle measurements rest on.
      inFlight = Math.max(0, inFlight - 1);
      if (inFlight === 0) releaseWaiters();
    });
  }) as NetworkCall;

  // THE DRIVING SURFACE. The harness and the oracle reach the layer through
  // this and through nothing else — the same arrangement the named-state driver
  // and the reference object already use, for the same reason: a measurement
  // that has to reach inside a module is a measurement coupled to how the
  // module is built.
  // THE STREAM IS INSTALLED WITH THE SEAM, not beside it. Both are the network
  // as far as the application is concerned, and a layer that lifted out in two
  // halves would leave a page with a socket and no requests.
  const stream = installMockStream({
    began: () => {
      delivering += 1;
    },
    ended: () => {
      // Floored for the reason the request counter is — a `reset()` between a
      // delivery and its release would otherwise take it below zero.
      delivering = Math.max(0, delivering - 1);
      if (inFlight === 0 && delivering === 0) releaseWaiters();
    },
  });

  window.__mocks = {
    routes: () => routes().map((route) => `${route.method} ${route.template}`),
    stream,
    scenario,
    outcomeFor,
    setOperationOutcome,
    setDefaultLatency,
    reset: () => {
      resetScenario();
      resetMockState();
      resetStream();
      // AND THE COUNTERS. `reset()` put the scenario, the state and the stream
      // back and left `inFlight`, `delivering` and the waiting list exactly as
      // they were — so a counter that had desynchronised had no way back at
      // all, and `quiet()` would never resolve again on that page.
      inFlight = 0;
      delivering = 0;
      const stranded = becameQuiet;
      becameQuiet = [];
      for (const settle of stranded) settle();
    },
    inFlight: () => inFlight + delivering,
    quiet: () =>
      inFlight === 0 && delivering === 0
        ? Promise.resolve()
        : new Promise<void>((settle) => {
            becameQuiet.push(settle);
          }),
  };
}

declare global {
  interface Window {
    /**
     * The mock layer's driving surface, present only when the layer is built
     * in. Optional, so a document served without it fails visibly at the call
     * site rather than here.
     */
    __mocks?: {
      routes: () => string[];
      /** The event stream's driving surface — emit, drop, refuse, replay. */
      stream: StreamDriver;
      scenario: typeof scenario;
      outcomeFor: typeof outcomeFor;
      setOperationOutcome: typeof setOperationOutcome;
      setDefaultLatency: typeof setDefaultLatency;
      reset: () => void;
      /** Requests in flight PLUS deliveries whose fan-out is not yet issued. */
      inFlight: () => number;
      quiet: () => Promise<void>;
    };
  }

  /**
   * Whether the mock layer is built in. Replaced at build time, so a false
   * value makes its call site dead code and the bundler drops this module — and
   * its seeds — from the output.
   */
  const __MOCKS_BUILT_IN__: boolean;
}

export type { MockRoute };
