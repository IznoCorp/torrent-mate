// The unit suite speaks French whatever the machine it runs on speaks.
//
// WHAT MAKES THIS NON-VACUOUS. Node gives the suite a `navigator` whose
// `languages` is the HOST's locale (`LANG`, `LC_ALL`), and the interface's
// first language is the browser's (`browserLanguage()`): on a French
// workstation the suite heard French, on an English runner it heard English and
// 31 assertions failed there alone. This test runs a suite file that asserts
// French words in a CHILD process whose host locale is English — the runner's —
// so a suite that leans on the host's language falls here, on every machine.
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// JavaScript, not TypeScript: the typecheck carries no Node types.
const DESIGN = fileURLToPath(new URL("../..", import.meta.url));

describe("the unit suite's language", () => {
  it("is French under an English host locale", () => {
    const run = () =>
      execFileSync(
        process.execPath,
        [resolve(DESIGN, "node_modules/vitest/vitest.mjs"), "run", "src/lib/byte-size.test.ts"],
        {
          cwd: DESIGN,
          env: { ...process.env, LANG: "en_US.UTF-8", LC_ALL: "en_US.UTF-8", LANGUAGE: "en_US" },
          stdio: "pipe",
        },
      );
    expect(run).not.toThrow();
  }, 60_000);
});
