// A held write replayed from the outbox refreshes every list its online path
// refreshes, not only the lists whose address is a prefix of the write's own.
//
// WHAT MAKES THIS NON-VACUOUS. The cache runs `staleTime: Infinity`, so a list a
// drain does not invalidate stays stale for the life of the process. Driven
// through the real `send()`, the real departure and the real wiring, over a
// recording `fetch` and an in-memory stand-in for the outbox's IndexedDB; each
// case seeds the lists the write's VERB invalidates online, drains, and reads
// which of them the cache now calls stale.
import { QueryClient } from "@tanstack/react-query";
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

const TO_HANDLE = "/api/v1/acquisition/to-handle";
const FOLLOWED = "/api/v1/acquisition/followed";
const STAGING = "/api/v1/staging/media";
const DECISIONS = "/api/v1/decisions/";
const EVERY_LIST = [TO_HANDLE, FOLLOWED, STAGING, DECISIONS];

let networkUp: boolean;

beforeEach(() => {
  held.clear();
  networkUp = false;
  vi.stubGlobal("window", { addEventListener: () => {}, location: { href: "http://localhost/" } });
  vi.stubGlobal("addEventListener", () => {});
  vi.stubGlobal("fetch", async () => {
    if (!networkUp) throw new TypeError("Failed to fetch");
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

/**
 * Holds one write, boots the wiring over a cache seeded with every list, drains.
 *
 * @param method The write's method.
 * @param path The write's address.
 * @returns The addresses of the lists the drain left stale.
 */
async function staleAfterReplayOf(method: "POST" | "DELETE", path: string): Promise<string[]> {
  const { send, HELD } = await import("../lib/query-client");
  const outbox = await import("./outbox");
  expect(await send(method, path, {})).toBe(HELD);

  const client = new QueryClient();
  EVERY_LIST.forEach((address) => client.setQueryData([address, ""], {}));
  const { installOutboxWiring } = await import("./outbox-wiring");
  installOutboxWiring(client);

  networkUp = true;
  await outbox.departAll();
  expect(held.size).toBe(0);
  return EVERY_LIST.filter((address) => client.getQueryState([address, ""])?.isInvalidated);
}

describe("a held write replayed from the outbox", () => {
  it("refreshes the queue and the follows after a reassign", async () => {
    const stale = await staleAfterReplayOf("POST", "/api/v1/acquisition/requesters/reassign");
    expect(stale).toEqual(expect.arrayContaining([TO_HANDLE, FOLLOWED]));
  });

  it("refreshes the queue after a Plex match answer", async () => {
    const stale = await staleAfterReplayOf("POST", "/api/v1/acquisition/journeys/Some%20Title/plex-match");
    expect(stale).toContain(TO_HANDLE);
  });

  it("refreshes the queue after a closure is marked seen", async () => {
    const stale = await staleAfterReplayOf("POST", "/api/v1/acquisition/journeys/Some%20Title/closure/seen");
    expect(stale).toContain(TO_HANDLE);
  });

  it("refreshes the decisions after a decision is reopened", async () => {
    const stale = await staleAfterReplayOf("POST", "/api/v1/decisions/decision-1/reopen");
    expect(stale).toContain(DECISIONS);
  });

  it("refreshes the decisions after a settled folder is enqueued again", async () => {
    const stale = await staleAfterReplayOf("POST", "/api/v1/staging/media/Some%20Title/enqueue");
    expect(stale).toContain(DECISIONS);
  });

  it("leaves unrelated lists alone after a reassign", async () => {
    const stale = await staleAfterReplayOf("POST", "/api/v1/acquisition/requesters/reassign");
    expect(stale).not.toContain(DECISIONS);
    expect(stale).not.toContain(STAGING);
  });
});
