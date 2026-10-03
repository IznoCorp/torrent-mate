// The refusal side's table is WHOLE: every operation the layer answers names
// what it asks for, and every write names one right the ceiling can subtract.
import { describe, expect, it } from "vitest";
import { routes } from "./handlers";
import { OPERATION_RIGHTS } from "./operation-rights";

// The session's own acts: every identity, under any ceiling (F28). The two notification writes
// join them (the operator, 2026-10-03): an account's own settings, not a delegable capability.
const SESSION = new Set([
  "signIn", "signOut", "signInWithPlex", "updateNotificationPreference", "registerPushDevice",
]);

describe("every operation names the right it asks for", () => {
  const table = routes();

  it("names every route the layer answers", () => {
    const unnamed = table.map((route) => route.operationId).filter((id) => !(id in OPERATION_RIGHTS));
    expect(unnamed).toEqual([]);
  });

  it("names no operation the layer does not answer", () => {
    const answered = new Set(table.map((route) => route.operationId));
    expect(Object.keys(OPERATION_RIGHTS).filter((id) => !answered.has(id))).toEqual([]);
  });

  it("gates every write but the session's own acts", () => {
    const loose = table
      .filter((route) => route.method !== "GET" && !SESSION.has(route.operationId))
      .filter((route) => OPERATION_RIGHTS[route.operationId] === null)
      .map((route) => route.operationId);
    expect(loose).toEqual([]);
  });
});
