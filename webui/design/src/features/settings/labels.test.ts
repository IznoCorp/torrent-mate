// A setting's subject: a tracker keyed by its domain is ONE subject (B-606).
import { describe, expect, it } from "vitest";
import { settingLabels } from "./labels";
import type { Setting } from "./types";

/**
 * A tracker setting, as the settings read answers one.
 *
 * @param key The setting's key.
 * @returns The setting.
 */
function trackerSetting(key: string): Setting {
  return { file: "tracker", key, name: key.split(".").pop() ?? key, type: "boolean", raw: true };
}

describe("a tracker's subject", () => {
  it("keeps a domain whole, on every field a tracker owns", () => {
    expect(settingLabels.subject(trackerSetting("tracker.providers.v3x.club.cross_seed"))).toBe("v3x.club");
    expect(settingLabels.subject(trackerSetting("tracker.providers.draupnirr.xyz.enabled"))).toBe("draupnirr.xyz");
    // « ACCEPTE LES UPLOADS » is a field a tracker owns too (L23, round 11 OPEN 2 = B).
    expect(settingLabels.subject(trackerSetting("tracker.providers.v3x.club.accepts_uploads"))).toBe("v3x.club");
    expect(settingLabels.subject(trackerSetting("tracker.providers.digitalcore.club.economy.min_ratio")))
      .toMatch(/^digitalcore\.club · /);
  });

  it("names a dotless tracker as before, and records no domain as unnamed", () => {
    expect(settingLabels.subject(trackerSetting("tracker.providers.tr4ker.cross_seed"))).toBe("Tr4ker");
    expect(settingLabels.subject(trackerSetting("tracker.providers.c411.economy.min_ratio"))).toMatch(/^C411 · /);
    expect([...settingLabels.unnamedSubjects].filter((segment) => ["v3x", "club", "xyz"].includes(segment))).toEqual([]);
  });
});
