// The sign-in gate says why the session ended, in the interface's words, for the server's code.
//
// WHAT MAKES THIS NON-VACUOUS. The gate is driven over a stand-in form, the way gate.test.ts drives it:
// the line is read back by its part name and its text compared with `fr.json`'s sentence for the code —
// and a code that is no reason (an unknown e-mail, a wrong password), or none at all, leaves no line.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "i18next";
import FR from "../i18n/fr.json";

vi.mock("./frame-verbs", () => ({ landSignedIn: () => {} }));
vi.mock("./navigation", () => ({ entryPageFor: () => "" }));

type Line = { dataset: Record<string, string>; className: string; textContent: string; hidden: boolean; [key: string]: unknown };

let lines: Line[];
let subtitle: { after: (line: Line) => void };

beforeEach(async () => {
  lines = [];
  subtitle = { after: (line) => void lines.push(line) };
  const form = { querySelector: (selector: string) => (selector === ".loginsub" ? subtitle : null), prepend: (line: Line) => void lines.push(line) };
  vi.stubGlobal("document", {
    querySelector: (selector: string) =>
      selector === "#loginform" ? form : selector === '[data-part="login/reason"]' ? (lines[0] ?? null) : null,
    createElement: () => ({ dataset: {}, className: "", textContent: "", hidden: true, setAttribute: () => {}, remove: () => {} }),
  });
  await i18next.init({ lng: "fr", resources: { fr: { translation: FR } } });
});

describe("the reason line", () => {
  it("says the session expired for auth.required", async () => {
    const { sayReason } = await import("./gate");
    sayReason("auth.required");
    expect(lines).toHaveLength(1);
    expect(lines[0].dataset.part).toBe("login/reason");
    expect(lines[0].textContent).toBe(FR.screens.gate.reasonExpired);
    expect(lines[0].hidden).toBe(false);
  });

  it("says the access was disabled for auth.access_disabled", async () => {
    const { sayReason } = await import("./gate");
    sayReason("auth.access_disabled");
    expect(lines[0].textContent).toBe(FR.screens.gate.reasonDisabled);
  });

  it("shows no line for a plain visit or a code that tells nothing", async () => {
    const { sayReason } = await import("./gate");
    sayReason(undefined);
    sayReason("auth.refused");
    expect(lines).toHaveLength(0);
  });

  it("takes the line down when the gate is shown for no reason after one", async () => {
    const { sayReason } = await import("./gate");
    sayReason("auth.required");
    sayReason(undefined);
    expect(lines[0].hidden).toBe(true);
  });
});
