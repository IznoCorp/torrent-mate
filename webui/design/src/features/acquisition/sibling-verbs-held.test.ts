// The Acquisition verbs built on `send()` say HELD, and a network error, in their own words.
//
// WHAT MAKES THIS NON-VACUOUS. `send()` answers the HELD sentinel when the network would not answer
// and the outbox keeps the write. A verb that read that as « done » announced a confirmed match, a
// reassignment or a pause that had not left the machine; and a verb that worded every throw as a
// refusal told the operator the layer decided what it never heard. Each verb is RUN as the tap runs it.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";

const said: string[] = [];
const verbs = new Map<string, (value: string) => void>();
const refetched: unknown[] = [];
const HELD_ANSWER = Symbol.for("test-held");
let refusal: unknown = null;
let answer: unknown;

vi.mock("../../lib/query-client", () => ({
  HELD: Symbol.for("test-held"),
  send: async () => {
    if (refusal !== null) throw refusal;
    return answer;
  },
  read: async () => [],
  isRequestFailure: (failure: unknown) => typeof failure === "object" && failure !== null && "status" in failure,
  sharedQueryClient: null,
}));
vi.mock("../../lib/shell-doors", () => ({
  toast: { show: ({ message }: { message: string }) => said.push(message) },
  panel: { close: () => undefined, redraw: () => undefined, produce: () => undefined },
  bridge: {},
  icons: {},
  dialog: undefined,
}));
vi.mock("../../lib/verbs", () => ({
  registerVerb: (name: string, run: (value: string) => void) => void verbs.set(name, run),
}));
vi.mock("../../lib/queue", () => ({
  queueNow: () => ({ settled: [{ title: "Lucky", ids: {}, plexMatch: null }] }),
  queueKey: () => [],
}));
vi.mock("../../ui/panel/contract", () => ({ registerProducer: () => undefined }));

const client = {
  getQueryData: () => undefined,
  refetchQueries: async (filters: unknown) => void refetched.push(filters),
  invalidateQueries: async (filters: unknown) => void refetched.push(filters),
} as never;

const { installPlexVerbs } = await import("./plex-verbs");
const { installReassignVerb } = await import("./reassign");
const { installAcquisitionSettingVerbs } = await import("./acquisition-settings");

/** Runs a registered verb and lets its detached promise settle. */
async function run(name: string, value: string): Promise<void> {
  verbs.get(name)?.(value);
  await new Promise((settle) => setTimeout(settle, 20));
}

describe("Acquisition verbs on send()", () => {
  beforeEach(() => {
    said.length = 0;
    refetched.length = 0;
    refusal = null;
    answer = undefined;
    installPlexVerbs(client);
    installReassignVerb(client);
    installAcquisitionSettingVerbs(client);
  });

  it("does not announce a held Plex confirmation as confirmed", async () => {
    answer = HELD_ANSWER;
    await run("plex-confirm", "Lucky");
    expect(said).toEqual([i18next.t("verbs.acquisition.held")]);
    expect(refetched).toEqual([]);
  });

  it("does not word a Plex network error as done", async () => {
    refusal = new TypeError("network down");
    await run("plex-confirm", "Lucky");
    expect(said).toEqual([i18next.t("verbs.acquisition.failed")]);
  });

  it("does not announce a held reassignment as done", async () => {
    answer = HELD_ANSWER;
    await run("reassign-to", "follow|Lucky|a|b");
    expect(said).toEqual([i18next.t("verbs.acquisition.held")]);
    expect(refetched).toEqual([]);
  });

  it("does not word a reassignment network error as a refusal", async () => {
    refusal = new TypeError("network down");
    await run("reassign-to", "follow|Lucky|a|b");
    expect(said).toEqual([i18next.t("verbs.acquisition.failed")]);
    expect(said[0]).not.toBe(i18next.t("verbs.reassign.refused"));
  });

  it("does not announce a held pause as noted", async () => {
    answer = HELD_ANSWER;
    await run("pause-own", "Lucky|true");
    expect(said).toEqual([i18next.t("verbs.acquisition.held")]);
    expect(refetched).toEqual([]);
  });

  it("keeps a pause refusal worded as a refusal", async () => {
    refusal = { status: 403, title: "no", code: "auth.forbidden" };
    await run("pause-own", "Lucky|true");
    expect(said).toEqual([i18next.t("verbs.acquisitionSettings.refused")]);
  });
});
