// The design host's way through to the real server, and the builds it stays out of.
//
// WHAT MAKES THIS NON-VACUOUS. The set is read off the served document and
// compared with the maquette's contract operation by operation — the same
// method and the same path — so an operation v1 serves at another address
// fails here rather than reaching a server that answers 404. Then the layer
// itself is installed over a recording network, and a call is made the way the
// interface makes it: on the design host a served operation reaches the
// network once and is recorded with the status the network gave; an unserved
// one, and every operation of any other build, is answered by the mocks and
// reaches nothing.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import V1 from "../../../../contract/openapi.generated.json";
import CONTRACT from "../../../../contract/openapi.json";
import { passesThrough, servedOperations } from "./passthrough";

type Document = { paths: Record<string, Record<string, { operationId?: string }>> };

/**
 * Every operation of one document, by id.
 *
 * @param document The OpenAPI document.
 * @returns Its method and path, by operation id.
 */
function operations(document: Document): Map<string, string> {
  const found = new Map<string, string>();
  for (const [path, verbs] of Object.entries(document.paths)) {
    for (const [method, operation] of Object.entries(verbs)) {
      if (operation.operationId) found.set(operation.operationId, `${method.toUpperCase()} ${path}`);
    }
  }
  return found;
}

// Read off the document, never typed here: an operation v1 starts serving joins
// the set by itself — and must then be the maquette's own, which the second
// test holds.
const SERVED = [...operations(V1 as Document).keys()].sort();

describe("the operations v1 serves", () => {
  it("are every operation id of the served document, the doors among them", () => {
    expect([...servedOperations(V1 as Document)].sort()).toEqual(SERVED);
    expect(SERVED).toEqual(expect.arrayContaining(["signIn", "signOut", "readAccount", "readVersion"]));
  });

  it("are each the maquette's own operation, at the same method and path", () => {
    const maquette = operations(CONTRACT as unknown as Document);
    for (const [id, address] of operations(V1 as Document)) expect([id, maquette.get(id)]).toEqual([id, address]);
  });

  it("pass through on the design host only", () => {
    for (const id of SERVED) expect(passesThrough(id, false)).toBe(false);
    expect(passesThrough("signIn", true)).toBe(true);
    expect(passesThrough("readFollows", true)).toBe(false);
  });

  it("stay on the mocks in every build but the design host's", () => {
    expect(passesThrough("signIn")).toBe(false);
  });
});

describe("the layer, installed", () => {
  let network: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.resetModules();
    network = vi.fn(async () => new Response(JSON.stringify({ version: "real" }), { status: 299 }));
    vi.stubGlobal("fetch", network);
    vi.stubGlobal("window", {});
    vi.stubGlobal("location", { origin: "https://tm-design.invalid" });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /**
   * Installs the layer and asks one address through it.
   *
   * @param path The address asked for.
   * @returns What the layer answered, and what it recorded.
   */
  async function ask(path: string): Promise<{ status: number; recorded: number | undefined }> {
    const { installMockNetwork, mockLayer } = await import("./index");
    installMockNetwork();
    const answer = await globalThis.fetch(path);
    const layer = mockLayer ?? (window as Window).__mocks;
    return { status: answer.status, recorded: layer?.answered().at(-1)?.status };
  }

  it("on the design host, sends a served operation to the network once, and records its real status", async () => {
    vi.stubGlobal("__DESIGN_HOST__", true);
    expect(await ask("/api/v1/version")).toEqual({ status: 299, recorded: 299 });
    expect(network).toHaveBeenCalledTimes(1);
  });

  it("on the design host, answers an unserved operation from the mocks", async () => {
    vi.stubGlobal("__DESIGN_HOST__", true);
    expect((await ask("/api/v1/acquisition/followed")).status).toBe(200);
    expect(network).not.toHaveBeenCalled();
  });

  it("anywhere else, answers a served operation from the mocks", async () => {
    vi.stubGlobal("__DESIGN_HOST__", false);
    expect((await ask("/api/v1/version")).status).toBe(200);
    expect(network).not.toHaveBeenCalled();
  });
});
