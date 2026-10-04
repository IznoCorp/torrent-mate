// B-676: one reading of « is it followed » — by the base title, never by being incomplete.
import { describe, expect, it } from "vitest";
import { followedAs } from "./titles";

describe("followedAs", () => {
  it("finds a follow recorded without the library's year (« Furious » follows « Furious (2026) »)", () => {
    expect(followedAs(["Silo", "Furious"], "Furious (2026)")).toBe("Furious");
  });

  it("finds a follow recorded with a year the library title does not carry", () => {
    expect(followedAs(["Silo (2023)"], "Silo")).toBe("Silo (2023)");
  });

  it("finds nothing for a title nobody follows (« Earl », incomplete and not followed)", () => {
    expect(followedAs(["Silo", "Furious"], "Earl")).toBeUndefined();
  });
});
