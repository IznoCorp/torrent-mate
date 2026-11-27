// A grab the server refuses is said, in the refusal's own words, and the card comes back.
//
// WHAT MAKES THIS NON-VACUOUS. The queue's `take` is installed and called as the picker calls it; the
// layer refuses with the code the contract declares for a pick its row cannot take. A take that only
// rolled the card back would say nothing, with « récupération lancée » still on screen.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import i18next from "./unit-words";

const said: string[] = [];
let refusal: unknown;

vi.mock("./query-client", () => ({
  HELD: Symbol.for("test-held"),
  isRequestFailure: (failure: unknown) => typeof failure === "object" && failure !== null && "status" in failure,
  send: async () => {
    throw refusal;
  },
  read: async () => [],
}));
vi.mock("./follow-key", () => ({
  followKeyOfTitle: async () => "tvdb:1",
  followSegment: encodeURIComponent,
}));
vi.mock("./shell-doors", () => ({
  toast: { show: ({ message }: { message: string }) => said.push(message) },
}));
vi.mock("./store-access", () => ({ store: { read: () => ({ state: {} }), touch: () => undefined } }));

const { installQueueActions, queueKey } = await import("./queue");
const held = { takeable: [{ title: "Lucky" }], blocked: [], inFlight: [], done: [] };

describe("a refused take", () => {
  let client: QueryClient;

  beforeEach(() => {
    said.length = 0;
    client = new QueryClient();
    client.setQueryData(queueKey(""), held);
    installQueueActions(client);
  });

  /** Takes the card and lets the refusal land. */
  async function take(): Promise<void> {
    const actions = (await import("./queue")).queueActions;
    actions?.take("Lucky", "7:abcdef");
    await new Promise((settle) => setTimeout(settle, 20));
  }

  it("says why the picked release cannot be taken, and puts the card back", async () => {
    refusal = { status: 409, title: "no", detail: "no", code: "acquisition.release_unavailable" };

    await take();

    expect(said).toEqual([i18next.t("refusals.acquisition.release_unavailable")]);
    expect(client.getQueryData(queueKey(""))).toEqual(held);
  });

  it("words a take the network lost as failed, not refused", async () => {
    refusal = new TypeError("network down");

    await take();

    expect(said).toEqual([i18next.t("verbs.acquisition.failed")]);
  });
});
