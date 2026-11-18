// The development pages are in the design host's builds and under its quality control, never in production.
import { describe, expect, it } from "vitest";
import { carriesDevPages } from "./dev-pages";

describe("carriesDevPages", () => {
  it.each([
    [true, false, true],
    [false, true, true],
    [true, true, true],
    [false, false, false],
  ])("design host %s, mock layer %s: %s", (designHost, mocksBuiltIn, expected) => {
    expect(carriesDevPages(designHost, mocksBuiltIn)).toBe(expected);
  });
});
