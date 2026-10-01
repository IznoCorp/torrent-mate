// A running passage's second line says how long it has been going (B-538).
//
// WHAT MAKES THIS NON-VACUOUS. The ended row's line is held beside it, so a
// running row reading empty — the defect, one text line shorter than the same
// row once ended — fails by the empty string, and the elapsed words are the
// committed resource's, read through the translator the page uses.
import { describe, expect, it } from "vitest";
import i18next from "../../lib/unit-words";
import { whatItDid } from "./run-list";

const STARTED = "2026-08-14T05:08:22+00:00";
const run = (extra: object) => ({
  runUid: "a", trigger: "completion", dryRun: false, startedAt: STARTED, endedAt: null,
  outcome: "running", durationS: null, kind: "pipeline", command: null, steps: [], ...extra,
}) as unknown as Parameters<typeof whatItDid>[0];
const say = i18next.t.bind(i18next) as unknown as Parameters<typeof whatItDid>[1];

describe("whatItDid", () => {
  it("says a running passage's elapsed minutes on its second line", () => {
    const now = Date.parse(STARTED) + 7 * 60_000 + 30_000;
    expect(whatItDid(run({}), say, now)).toBe(i18next.t("screens.system.runRunningSince", { count: 7 }));
  });

  it("says under a minute in words, never « 0 min »", () => {
    const now = Date.parse(STARTED) + 20_000;
    expect(whatItDid(run({}), say, now)).toBe(i18next.t("screens.system.runRunningJustNow"));
  });

  it("keeps the ended passage's report", () => {
    const ended = run({ outcome: "success", durationS: 104, endedAt: STARTED });
    expect(whatItDid(ended, say)).toBe("rien de nouveau · 1 min 44"); // french-ok: the rendered line, asserted
  });
});
