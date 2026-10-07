// « Abandonner » says what became of the quarantine — done, held, refused, or failed — and throws nothing.
//
// WHAT MAKES THIS NON-VACUOUS. The confirming action is RUN the way the dialog runs it. Before the
// repair a refusal escaped as an unhandled rejection (the runner's own hook catches it here), and a
// quarantine only HELD by the outbox was announced as done, with the reads invalidated over it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";
import type { DialogDescriptor } from "../../ui/dialog/contract";

// THE RUNNER'S OWN PROCESS, typed by what is used of it: the app's types carry no Node.
const runner = (globalThis as unknown as {
  process: { on: (event: string, listener: (reason: unknown) => void) => void; off: (event: string, listener: (reason: unknown) => void) => void };
}).process;

const opened: DialogDescriptor[] = [];
const said: string[] = [];
const invalidated: unknown[] = [];
let refusal: unknown = null;
let answer: unknown;

vi.mock("../../lib/query-client", () => ({
  HELD: Symbol.for("test-held"),
  send: async () => {
    if (refusal !== null) throw refusal;
    return answer;
  },
  isRequestFailure: (failure: unknown) => typeof failure === "object" && failure !== null && "status" in failure,
  sharedQueryClient: {
    getQueriesData: () => [],
    invalidateQueries: async (filters: unknown) => void invalidated.push(filters),
  },
}));
vi.mock("../../lib/shell-doors", () => ({
  dialog: { open: (descriptor: DialogDescriptor) => opened.push(descriptor) },
  toast: { show: ({ message }: { message: string }) => said.push(message) },
}));
vi.mock("../../lib/verbs", () => ({ registerVerb: () => undefined }));

const { openAbandonConfirm } = await import("./abandon-verb");

/** Opens the confirmation and runs the action that confirms it, as the dialog's button does. */
async function confirm(title: string): Promise<void> {
  openAbandonConfirm(title);
  opened[0]?.actions.find((action) => action.tone === "danger")?.run?.();
  await new Promise((settle) => setTimeout(settle, 20));
}

describe("abandoning a tunnel error", () => {
  const escaped: unknown[] = [];
  const catchEscaped = (reason: unknown) => void escaped.push(reason);

  beforeEach(() => {
    opened.length = 0;
    said.length = 0;
    invalidated.length = 0;
    escaped.length = 0;
    refusal = null;
    answer = { quarantine_path: "/q/Lucky" };
    runner.on("unhandledRejection", catchEscaped);
  });
  afterEach(() => {
    runner.off("unhandledRejection", catchEscaped);
  });

  it("says where the folder went when the layer accepts", async () => {
    await confirm("Lucky");
    expect(said).toEqual([i18next.t("verbs.acquisition.abandon.done", { title: "Lucky", path: "/q/Lucky" })]);
    expect(invalidated).toHaveLength(3);
  });

  it("says the refusal and lets nothing escape the act", async () => {
    refusal = { status: 403, title: "a right this account does not hold", code: "auth.forbidden" };
    await confirm("Lucky");
    expect(escaped).toEqual([]);
    expect(said).toEqual([i18next.t("verbs.acquisition.abandon.refused", { title: "Lucky" })]);
    expect(invalidated).toEqual([]);
  });

  it("says the quarantine is held, never done, when the outbox keeps it", async () => {
    answer = Symbol.for("test-held");
    await confirm("Lucky");
    expect(said).toEqual([i18next.t("verbs.acquisition.abandon.held", { title: "Lucky" })]);
    expect(invalidated).toEqual([]);
  });

  it("does not word a network error as a refusal", async () => {
    refusal = new TypeError("network down");
    await confirm("Lucky");
    expect(escaped).toEqual([]);
    expect(said).toEqual([i18next.t("verbs.acquisition.abandon.failed", { title: "Lucky" })]);
  });
});
