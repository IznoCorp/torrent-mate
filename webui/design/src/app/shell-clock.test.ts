// The page's clock at boot: frozen on the layer's instant everywhere but the
// design host, which reads the real one (the operator, 2026-10-04; Q6 = B).
//
// WHAT MAKES THIS NON-VACUOUS. The frozen day is one no real clock reads
// (2001-02-03), so a frozen boot and a real one cannot answer the same `today`.
import { beforeEach, describe, expect, it, vi } from "vitest";

const FROZEN = "2001-02-03";

beforeEach(() => {
  vi.resetModules();
});

describe("the boot's clock", () => {
  it("is frozen on the layer's day outside the design host", async () => {
    const clock = await import("../lib/clock");
    clock.bootClock(false, FROZEN);
    expect(clock.today()).toBe(FROZEN);
  });

  it("is the real clock on the design host", async () => {
    const clock = await import("../lib/clock");
    clock.bootClock(true, FROZEN);
    expect(clock.today()).toBe(new Date().toISOString().slice(0, 10));
  });
});
