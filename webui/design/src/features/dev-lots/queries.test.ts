// The lots progress read: a 404 is « nothing published », any other refusal a failure.
import { describe, expect, it } from "vitest";
import { LOTS_ADDRESS, readLots } from "./queries";

/**
 * A host that answers one status, with a body.
 *
 * @param status The status.
 * @param body What it sends.
 * @returns The stand-in for `askTheHost`, and the addresses it was asked.
 */
function host(status: number, body: unknown = {}) {
  const asked: string[] = [];
  const ask = async (address: string) => {
    asked.push(address);
    return new Response(JSON.stringify(body), { status });
  };
  return { ask, asked };
}

describe("readLots", () => {
  it("returns what the host generated, asked at its one address", async () => {
    const document = { available: true, generatedAt: 1, lots: [] };
    const { ask, asked } = host(200, document);
    await expect(readLots(ask)).resolves.toEqual(document);
    expect(asked).toEqual([LOTS_ADDRESS]);
  });

  it("says nothing is published when the host serves no file", async () => {
    await expect(readLots(host(404).ask)).resolves.toEqual({ available: false });
  });

  it.each([401, 500, 503])("fails, naming the status, on a %i", async (status) => {
    await expect(readLots(host(status).ask)).rejects.toThrow(String(status));
  });
});
