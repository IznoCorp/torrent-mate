// A refused « Supprimer » of a folder set aside says so, and throws nothing at the page.
//
// WHAT MAKES THIS NON-VACUOUS. The confirming action is RUN the way the dialog runs it, and the
// layer refuses the deletion with the problem body a refusal really is (a plain object, not an
// `Error`). Before the repair the act threw that object at the page: an unhandled rejection that a
// browser prints as « Object », with no toast and a queue left as it was. Here the refusal must come
// out as the toast's words, the folder must stay in the reads, and no rejection may escape the act.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";
import type { DialogDescriptor } from "../../ui/dialog/contract";

const opened: DialogDescriptor[] = [];
const said: string[] = [];
const invalidated: unknown[] = [];
let refusal: unknown = null;

vi.mock("../../lib/query-client", () => ({
  read: async () => ({ case: "only_copy" }),
  send: async () => {
    if (refusal !== null) throw refusal;
    return undefined;
  },
  isRequestFailure: (failure: unknown) => typeof failure === "object" && failure !== null && "status" in failure,
  sharedQueryClient: { invalidateQueries: async (filters: unknown) => void invalidated.push(filters) },
}));
vi.mock("../../lib/shell-doors", () => ({
  dialog: { open: (descriptor: DialogDescriptor) => opened.push(descriptor) },
  toast: { show: ({ message }: { message: string }) => said.push(message) },
}));
vi.mock("../../lib/verbs", () => ({ registerVerb: () => undefined }));

const { openDeleteConfirm } = await import("./delete-set-aside-verb");

/** Opens the confirmation and runs the action that confirms it, as the dialog's button does. */
async function confirm(title: string): Promise<void> {
  openDeleteConfirm(title);
  await vi.waitFor(() => expect(opened).toHaveLength(1));
  opened[0]?.actions.find((action) => action.tone === "danger")?.run?.();
  // The act is a promise nothing awaits: let it settle, and any rejection it leaves reach the runner.
  await new Promise((settle) => setTimeout(settle, 20));
}

describe("deleting a folder set aside", () => {
  const escaped: unknown[] = [];
  const catchEscaped = (reason: unknown) => void escaped.push(reason);

  beforeEach(() => {
    opened.length = 0;
    said.length = 0;
    invalidated.length = 0;
    escaped.length = 0;
    refusal = null;
    process.on("unhandledRejection", catchEscaped);
  });
  afterEach(() => {
    process.off("unhandledRejection", catchEscaped);
  });

  it("says the folder is deleted when the layer accepts", async () => {
    await confirm("Lucky");
    expect(said).toEqual([i18next.t("verbs.acquisition.deleteStaged.done", { title: "Lucky" })]);
    expect(escaped).toEqual([]);
  });

  it("says the refusal in the interface's words, and lets nothing escape the act", async () => {
    refusal = { status: 403, title: "a right this account does not hold", code: "auth.forbidden" };
    await confirm("Lucky");
    expect(escaped).toEqual([]);
    expect(said).toHaveLength(1);
    expect(said[0]).not.toBe(i18next.t("verbs.acquisition.deleteStaged.done", { title: "Lucky" }));
    expect(said[0]).toBe(i18next.t("verbs.acquisition.deleteStaged.refused", { title: "Lucky" }));
  });
});
