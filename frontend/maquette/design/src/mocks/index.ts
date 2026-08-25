// The seam: one `fetch`, and no service worker.
//
// WHY NOT A SERVICE WORKER (D-L08-2, arbitrated by the operator 2026-08-25).
// The oracle measures at first paint, and a worker's registration is
// asynchronous — a page can render once before the worker controls it, which is
// a race an oracle cannot be asked to absorb. L11 owns the real service worker
// and two contending for one scope is an arbitration nobody needs to hold for
// three lots. And the harness reads a MANUAL static copy served by one host
// while the design host is another; a worker script would have to be served
// correctly at the root by both.
//
// WHAT IT COSTS, and it is recorded rather than glossed: the browser's own
// network stack is not exercised, so what a real `fetch` does with caching,
// redirects and abort signals is not proved here. The seam is ONE module, and
// the switchover replaces its implementation rather than its call sites.
//
// A REQUEST NO ROUTE CLAIMS IS A FAILURE THAT NAMES ITSELF. Never a
// pass-through to the network, never a silent empty object: a mock that answers
// something to everything is a mock that hides a missing handler.
import { resolve, type MockRoute } from "./router";
import { outcomeFor, resetScenario, scenario } from "./scenario";
import { resetMockState } from "./state";
import { routes } from "./handlers";

/** The signature the seam replaces, kept so the original can be restored. */
type Fetch = typeof globalThis.fetch;

let original: Fetch | null = null;
let inFlight = 0;
let becameQuiet: (() => void)[] = [];

/**
 * Answers one request from the routing table.
 *
 * @param input What was asked for.
 * @param options The request options.
 * @returns The response the contract declares for it.
 */
async function answer(input: RequestInfo | URL, options?: RequestInit): Promise<Response> {
  const asked = new URL(
    typeof input === "string" ? input : input instanceof URL ? input.href : input.url,
    globalThis.location.origin,
  );
  const method = (options?.method ?? "GET").toUpperCase();
  const found = resolve(routes(), method, asked.pathname);
  if (found === null) {
    return problem(
      404,
      "no mock route",
      `${method} ${asked.pathname} is not an operation the maquette's contract declares`,
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
  if (options?.body !== undefined && typeof options.body === "string") {
    body = JSON.parse(options.body);
  }
  const payload = found.route.handle({
    path: asked.pathname,
    parameters: found.parameters,
    query: asked.searchParams,
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
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/**
 * Builds a failure that says what really went wrong.
 *
 * The constitution's NE-DOIT-PAS-4 and NE-DOIT-PAS-5 apply to a mock as much as
 * to the engine: an error carries its real reason, never a bare code.
 *
 * @param status The status.
 * @param title What went wrong, in one line.
 * @param detail The real reason.
 * @returns The response.
 */
function problem(status: number, title: string, detail: string): Response {
  return json(status, { status, title, detail });
}

/** Installs the seam, and returns nothing: the page fetches as it always did. */
export function installMockNetwork(): void {
  if (original !== null) return;
  original = globalThis.fetch;
  globalThis.fetch = ((input: RequestInfo | URL, options?: RequestInit) => {
    inFlight += 1;
    return answer(input, options).finally(() => {
      inFlight -= 1;
      if (inFlight === 0) {
        const waiting = becameQuiet;
        becameQuiet = [];
        for (const settle of waiting) settle();
      }
    });
  }) as Fetch;

  // THE DRIVING SURFACE. The harness and the oracle reach the layer through
  // this and through nothing else — the same arrangement `__go` and
  // `__referentiel` already use, for the same reason: a measurement that has to
  // reach inside a module is a measurement coupled to how the module is built.
  window.__mocks = {
    routes: () => routes().map((route) => `${route.method} ${route.template}`),
    scenario,
    outcomeFor,
    reset: () => {
      resetScenario();
      resetMockState();
    },
    inFlight: () => inFlight,
    quiet: () =>
      inFlight === 0
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
      scenario: typeof scenario;
      outcomeFor: typeof outcomeFor;
      reset: () => void;
      inFlight: () => number;
      quiet: () => Promise<void>;
    };
  }
}

export type { MockRoute };

declare global {
  /**
   * Whether the mock layer is built in. Replaced at build time by Vite's
   * `define`, so a false value makes its call site dead code and the bundler
   * drops this module — and its seeds — from the output.
   */
  const __MOCKS_BUILT_IN__: boolean;
}
