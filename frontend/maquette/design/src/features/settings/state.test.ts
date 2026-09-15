// The settings working state's three answers, held on every branch they have.
//
// WHAT MAKES THIS NON-VACUOUS. `fileName` is asserted on a file with and
// without an extension; `changedFiles` on two edits of one file and one of
// another, so a list that did not deduplicate, or kept the key's second half,
// fails; `typedValue` on a number field's four answers and a text field's two.
import { afterEach, describe, expect, it } from "vitest";
import { SETTINGS_STATE, changedFiles, fileName, typedValue } from "./state";
import type { Setting } from "./reference";

const field = (type: string, brut: unknown): Setting =>
  ({ f: "thresholds", c: "", type, brut, n: "", v: "", topic: {} }) as Setting;

afterEach(() => SETTINGS_STATE.modifs.clear());

describe("fileName", () => {
  it("adds the overlay extension, and leaves a file that has one", () => {
    expect(fileName("thresholds")).toBe("thresholds.json5");
    expect(fileName("ecosystem.config.js")).toBe("ecosystem.config.js");
  });
});

describe("changedFiles", () => {
  it("names each file the pending edits would write, once", () => {
    SETTINGS_STATE.modifs.set("thresholds:disk.minimum", 5);
    SETTINGS_STATE.modifs.set("thresholds:disk.warning", 9);
    SETTINGS_STATE.modifs.set("tracker:tracker.enabled", false);
    expect(changedFiles()).toEqual(["thresholds", "tracker"]);
  });
});

describe("typedValue", () => {
  it("gives a number field back a number, its file's value, or nothing", () => {
    expect(typedValue(field("number", 4), "12")).toBe(12);
    expect(typedValue(field("number", 4), "  ")).toBeNull();
    expect(typedValue(field("number", 4), "twelve")).toBe(4);
    expect(typedValue(field("number", 4), "0")).toBe(0);
  });

  it("gives a text field back its text, or nothing when emptied", () => {
    expect(typedValue(field("string", "a"), "b")).toBe("b");
    expect(typedValue(field("string", "a"), "")).toBeNull();
  });
});
