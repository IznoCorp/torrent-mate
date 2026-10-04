// A request answered 401 lands the interface on the sign-in gate AND says why, in the server's code.
//
// WHAT MAKES THIS NON-VACUOUS. The seam is driven by a real `read` over a stand-in `fetch` that answers
// 401 with a problem body: the entry's two callbacks are what a surface would install, and what is read is
// what they were told — the landing at once (the gate never waits on a body), then the code once it is
// read, and nothing for an answer that carries none.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../app/outbox", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/outbox")>()),
}));

let lost: ReturnType<typeof vi.fn<() => void>>;
let why: ReturnType<typeof vi.fn<(code: string | undefined) => void>>;

beforeEach(async () => {
  lost = vi.fn<() => void>();
  why = vi.fn<(code: string | undefined) => void>();
  const client = await import("./query-client");
  client.onSessionLost(lost);
  client.onSessionLostBecause(why);
});

afterEach(() => vi.unstubAllGlobals());

/** Reads one address that answers `status` with `body`. */
async function readAnswering(status: number, body: unknown): Promise<void> {
  vi.stubGlobal("fetch", async () => new Response(JSON.stringify(body), { status }));
  const { read } = await import("./query-client");
  await read("/api/v1/auth/me").catch(() => undefined);
  await new Promise((settle) => setTimeout(settle, 0));
}

describe("a session gone under the interface", () => {
  it("lands on the gate and says the server's code", async () => {
    await readAnswering(401, { code: "auth.required" });
    expect(lost).toHaveBeenCalledTimes(1);
    expect(why).toHaveBeenCalledWith("auth.required");
  });

  it("lands on the gate and says nothing for an answer that carries no code", async () => {
    await readAnswering(401, {});
    expect(lost).toHaveBeenCalledTimes(1);
    expect(why).toHaveBeenCalledWith(undefined);
  });

  it("does neither for any other refusal", async () => {
    await readAnswering(403, { code: "right.missing" });
    expect(lost).not.toHaveBeenCalled();
    expect(why).not.toHaveBeenCalled();
  });
});
