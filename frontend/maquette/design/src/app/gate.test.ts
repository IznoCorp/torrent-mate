// The gate's two doors send JSON the server can read.
//
// WHAT MAKES THIS NON-VACUOUS. The real v1 reads a sign-in's body as JSON only
// when it is DECLARED JSON; a POST with no `content-type` is a body it refuses.
// Each leg drives the gate the way a person does — the password form submitted,
// Plex's button tapped — over a stand-in document and a recording `fetch`, and
// reads the request that left: its declared type, its body parsed, and that it
// carries no idempotency key (a sign-in is no mutation, and never enters the
// outbox, where its password would be stored and replayed).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// THE FRAME IS NOT WHAT IS READ HERE: landing after a sign-in moves pages the
// stand-in document does not hold, and loading the frame loads every surface.
vi.mock("./frame-verbs", () => ({ landSignedIn: () => {} }));
vi.mock("./navigation", () => ({ entryPageFor: () => "" }));

/** One request the stand-in network saw. */
type Sent = { path: string; method: string; headers: Headers; body: unknown };

/** One element of the stand-in document: what the gate reads and writes. */
type FakeElement = {
  dataset: Record<string, string>;
  hidden: boolean;
  listeners: Record<string, (event: unknown) => void>;
  [key: string]: unknown;
};

/**
 * An element the gate can build, fill and listen on.
 *
 * @returns The element.
 */
function element(): FakeElement {
  const made: FakeElement = {
    dataset: {},
    hidden: false,
    listeners: {},
    setAttribute: () => {},
    append: () => {},
    insertBefore: () => {},
    closest: () => null,
    querySelector: () => null,
    addEventListener: (type: string, listener: (event: unknown) => void) => {
      made.listeners[type] = listener;
    },
  };
  return made;
}

let sent: Sent[];
let created: FakeElement[];
let form: FakeElement;
let fields: Record<string, string>;

/**
 * Answers every request with one status, and records it.
 *
 * @param answers The answer for a path, by its path; 401 when unnamed.
 */
function network(answers: Record<string, { status: number; body: unknown }>): void {
  vi.stubGlobal("fetch", async (path: string, options: RequestInit = {}) => {
    const raw = options.body;
    sent.push({
      path,
      method: options.method ?? "GET",
      headers: new Headers(options.headers),
      body: typeof raw === "string" ? JSON.parse(raw) : raw,
    });
    const found = answers[path] ?? { status: 401, body: { code: "auth.refused" } };
    return new Response(JSON.stringify(found.body), { status: found.status });
  });
}

/** Waits until every promise the gate chained has run. */
async function settle(): Promise<void> {
  for (let turn = 0; turn < 20; turn += 1) await new Promise((done) => setTimeout(done, 0));
}

beforeEach(() => {
  vi.resetModules();
  sent = [];
  created = [];
  form = element();
  fields = {};
  const login = element();
  vi.stubGlobal("document", {
    createElement: () => {
      const made = element();
      created.push(made);
      return made;
    },
    querySelector: (selector: string) =>
      selector === "#loginform" ? form : selector === "#login" ? login : null,
  });
  vi.stubGlobal("FormData", class {
    get(name: string): string | null {
      return fields[name] ?? null;
    }
  });
  // The modules the gate imports listen on the window as they load.
  vi.stubGlobal("window", {
    open: () => ({ location: { href: "" }, close: () => {} }),
    addEventListener: () => {},
    removeEventListener: () => {},
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the password door", () => {
  it("posts the e-mail and the password as declared JSON, with no idempotency key", async () => {
    network({});
    const { installGate } = await import("./gate");
    installGate(() => {});
    fields = { username: " owner@example.invalid ", password: "a password" };
    form.listeners.submit({ preventDefault: () => {}, currentTarget: form });
    await settle();
    const login = sent.find((one) => one.path === "/api/v1/auth/login");
    expect(login?.method).toBe("POST");
    expect(login?.headers.get("content-type")).toBe("application/json");
    expect(login?.headers.get("idempotency-key")).toBeNull();
    expect(login?.body).toEqual({ email: "owner@example.invalid", password: "a password" });
  });
});

describe("the Plex door", () => {
  it("asks about its PIN as declared JSON, with no idempotency key", async () => {
    network({
      "/api/v1/auth/plex/start": { status: 200, body: { pinId: 42, signInUrl: "https://plex.invalid/pin" } },
      "/api/v1/auth/plex": { status: 401, body: { code: "auth.refused" } },
    });
    const { restGate } = await import("./gate");
    restGate(false);
    created.find((one) => one.dataset.part === "login/plex-submit")?.listeners.click(undefined);
    await settle();
    const claim = sent.find((one) => one.path === "/api/v1/auth/plex");
    expect(claim?.method).toBe("POST");
    expect(claim?.headers.get("content-type")).toBe("application/json");
    expect(claim?.headers.get("idempotency-key")).toBeNull();
    expect(claim?.body).toEqual({ pinId: 42 });
  });
});
