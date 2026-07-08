/**
 * Unit tests for the adaptive Go/To size formatter (U1).
 */

import { describe, expect, it } from "vitest";

import { formatGb } from "./format";

describe("formatGb (U1)", () => {
  it("keeps sub-terabyte values in Go with one decimal", () => {
    expect(formatGb(238.5)).toBe("238.5 Go");
  });

  it("strips the trailing .0 on round Go values", () => {
    expect(formatGb(12)).toBe("12 Go");
  });

  it("switches to To at 1024 Go with one decimal", () => {
    // The operator-reported case: 20658.0 Go rendered raw.
    expect(formatGb(20658.0)).toBe("20.2 To");
  });

  it("strips the trailing .0 on round To values", () => {
    expect(formatGb(2048)).toBe("2 To");
  });

  it("renders zero as 0 Go", () => {
    expect(formatGb(0)).toBe("0 Go");
  });
});
