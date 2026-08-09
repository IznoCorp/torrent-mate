import { afterEach, describe, expect, it, vi } from "vitest";

import { isStaging } from "@/lib/env";

/** Point `window.location` at a given hostname/port for one assertion. */
function stubLocation(hostname: string, port = ""): void {
  vi.stubGlobal("location", { hostname, port });
}

describe("isStaging", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("is true on the staging host", () => {
    stubLocation("tm-staging.iznogoudatall.xyz");
    expect(isStaging()).toBe(true);
  });

  it("is true on the loopback staging port 8711", () => {
    stubLocation("127.0.0.1", "8711");
    expect(isStaging()).toBe(true);
  });

  it("is false on the production host", () => {
    stubLocation("tm.iznogoudatall.xyz");
    expect(isStaging()).toBe(false);
  });

  it("is false on the loopback prod port 8710", () => {
    stubLocation("127.0.0.1", "8710");
    expect(isStaging()).toBe(false);
  });
});

describe("BRAND_ICON", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // BRAND_ICON is a module-level const evaluated at import time, so each branch
  // must stub the location AND reset the module registry BEFORE the dynamic
  // import forces a fresh evaluation.
  it("resolves to the cyan-liseret staging icon on staging", async () => {
    stubLocation("tm-staging.iznogoudatall.xyz");
    vi.resetModules();
    const { BRAND_ICON } = await import("@/lib/env");
    expect(BRAND_ICON).toBe("/icon-staging.svg");
  });

  it("resolves to the production icon off staging", async () => {
    stubLocation("tm.iznogoudatall.xyz");
    vi.resetModules();
    const { BRAND_ICON } = await import("@/lib/env");
    expect(BRAND_ICON).toBe("/icon.svg");
  });
});

describe("env — l'identité staging après le retrait de la bannière (A17)", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

  async function loadEnvOn(hostname: string, port = "") {
    vi.stubGlobal("window", { location: { hostname, port } });
    vi.resetModules();
    return import("@/lib/env");
  }

  it("garde le logo staging comme signal survivant", async () => {
    const env = await loadEnvOn("tm-staging.iznogoudatall.xyz");
    expect(env.isStaging()).toBe(true);
    expect(env.BRAND_ICON).toBe("/icon-staging.svg");
  });

  it("garde le logo de prod ailleurs", async () => {
    const env = await loadEnvOn("tm.iznogoudatall.xyz");
    expect(env.isStaging()).toBe(false);
    expect(env.BRAND_ICON).toBe("/icon.svg");
  });

  it("plus aucun module n'importe StagingBanner", () => {
    const modules = import.meta.glob("/src/**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true });
    const offenders = Object.entries(modules)
      .filter(([, source]) => source.includes("StagingBanner"))
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });
});
