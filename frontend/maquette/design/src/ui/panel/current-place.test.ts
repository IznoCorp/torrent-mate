// B-675: a menu's entry in a sheet says « you are here » on the page it names, and only there.
import { describe, expect, it } from "vitest";
import { isCurrentPlace } from "./contract";

describe("a sheet's menu entry", () => {
  it("is the current place on the page it names", () => {
    expect(isCurrentPlace({ go: "profile", destination: "" }, "profile")).toBe(true);
  });

  it("is not the current place on another page", () => {
    expect(isCurrentPlace({ go: "profile", destination: "" }, "lib")).toBe(false);
  });

  it("is never a link that does not choose a destination (« Compléter » stacks a dial)", () => {
    expect(isCurrentPlace({ go: "lib" }, "lib")).toBe(false);
    expect(isCurrentPlace(undefined, "lib")).toBe(false);
  });
});
