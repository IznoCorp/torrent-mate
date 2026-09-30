// The byte counts the « Torrents » tab writes: a size and a rate, in decimal units.
import { describe, expect, it } from "vitest";
import "../../lib/unit-words";
import { rateOf, sizeOf } from "./format";

describe("sizeOf", () => {
  it("writes a size in the largest unit that keeps it at one or more", () => {
    expect(sizeOf(803859794)).toBe("804 Mo");
    expect(sizeOf(9040170236)).toBe("9,0 Go");
    expect(sizeOf(512)).toBe("512 o");
  });
});

describe("rateOf", () => {
  it("writes a rate per second, one decimal under ten", () => {
    expect(rateOf(2400000)).toBe("2,4 Mo/s");
    expect(rateOf(310000)).toBe("310 Ko/s");
  });
});
