// The client addresses the server where the contract says it is served.
import { describe, expect, it } from "vitest";
import contract from "../../../../../contract/openapi.json";
import { SERVER_BASE } from "./server-base";

describe("the client's base", () => {
  it("is the contract's server URL", () => {
    expect(contract.servers.map((server) => server.url)).toEqual([SERVER_BASE]);
  });

  it("carries paths relative to it", () => {
    expect(Object.keys(contract.paths).filter((path) => path.startsWith(SERVER_BASE))).toEqual([]);
  });
});
