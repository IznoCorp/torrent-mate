// A held write departs with the key it first carried, and a write still running
// on the server stays held.
//
// WHAT MAKES THIS NON-VACUOUS. The server answers a key it has already applied
// with its first answer, so a write may be re-sent as often as the network
// fails — creations included — PROVIDED the re-send carries the SAME key: a new
// key is a new write. And a duplicate that arrives while the first send is still
// running is refused 409 `request.in_progress`: a 409 that is NOT a decision about
// the write, so a queue that dropped it as final would lose the operator's
// action. Driven through the real `send()` and the real departure, over a
// recording `fetch` and an in-memory stand-in for the outbox's IndexedDB.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Envelope } from "./outbox-store";

const held = vi.hoisted(() => new Map<string, Envelope>());

// THE STORAGE IS NOT WHAT IS READ HERE: the stand-in document holds no IndexedDB.
vi.mock("./outbox-store", () => ({
  keep: async (envelope: Envelope) => {
    held.set(envelope.key, envelope);
    return true;
  },
  waiting: async () => [...held.values()].sort((left, right) => left.order - right.order),
  forget: async (key: string) => {
    held.delete(key);
  },
  forgetEverything: async () => {
    held.clear();
  },
}));

type Sent = { method: string; path: string; key: string | null; body: string | undefined };

let sent: Sent[];
let answer: () => Promise<Response>;

/** A Problem answer, as v1 refuses. */
function refusal(status: number, code: string): Promise<Response> {
  return Promise.resolve(new Response(
    JSON.stringify({ status, title: code, detail: code, code, params: {} }),
    { status, headers: { "content-type": "application/json" } },
  ));
}

beforeEach(() => {
  held.clear();
  sent = [];
  answer = () => Promise.reject(new TypeError("Failed to fetch"));
  vi.stubGlobal("window", { addEventListener: () => {} });
  vi.stubGlobal("fetch", async (path: string, options: RequestInit = {}) => {
    sent.push({
      method: options.method ?? "GET",
      path,
      key: new Headers(options.headers).get("idempotency-key"),
      body: options.body as string | undefined,
    });
    return answer();
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

/** Creates a role while the network takes nothing, so the creation is held. */
async function holdACreation() {
  const { send, HELD } = await import("../lib/query-client");
  const outbox = await import("./outbox");
  const result = await send("POST", "/api/v1/roles", { name: "Friends", rights: ["library.read"] });
  expect(result).toBe(HELD);
  return outbox;
}

describe("the outbox's replay", () => {
  it("holds a creation and re-sends it with the key and the body it first carried", async () => {
    const outbox = await holdACreation();
    answer = () => Promise.resolve(new Response(JSON.stringify({ id: "role-1" }), { status: 201 }));
    await outbox.departAll();

    expect(sent).toHaveLength(2);
    const [first, replay] = sent;
    expect(first.key).toMatch(/\S/);
    expect(replay).toEqual(first);
    expect(held.size).toBe(0);
    expect(outbox.refusedDepartures()).toEqual([]);
  });

  it("keeps a write the server is still running, and sends it again with its key", async () => {
    const outbox = await holdACreation();
    answer = () => refusal(409, "request.in_progress");
    await outbox.departAll();

    expect(held.size).toBe(1);
    expect(outbox.refusedDepartures()).toEqual([]);

    answer = () => Promise.resolve(new Response(JSON.stringify({ id: "role-1" }), { status: 201 }));
    await outbox.departAll();
    expect(held.size).toBe(0);
    expect(new Set(sent.map((request) => request.key)).size).toBe(1);
  });

  it("drops and remembers a write whose key the server says another request used", async () => {
    const outbox = await holdACreation();
    answer = () => refusal(409, "request.key_reused");
    await outbox.departAll();

    expect(held.size).toBe(0);
    expect(outbox.refusedDepartures()).toHaveLength(1);
  });

  it("drops and remembers a write refused on the world as it now is", async () => {
    const outbox = await holdACreation();
    answer = () => refusal(409, "role.name_taken");
    await outbox.departAll();

    expect(held.size).toBe(0);
    expect(outbox.refusedDepartures()).toHaveLength(1);
  });
});
