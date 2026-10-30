// The password policy every local door applies (the operator, 2026-10-04), as
// the interface says it before the server is asked.
//
// WHAT MAKES THIS NON-VACUOUS. Each case is one the server's own test reads
// (`tests/unit/app/accounts/test_passwords.py`): the same passwords, the same
// codes — the two checks are the same Unicode categories, so they never part.
import { describe, expect, it } from "vitest";
import ACCOUNTS from "../mocks/seeds/accounts.json";
import FR from "../i18n/fr.json";
import EN from "../i18n/en.json";
import { PASSWORD_MINIMUM, passwordShortfall } from "./password-policy";

describe("the password policy", () => {
  it("passes a password meeting every criterion", () => {
    expect(passwordShortfall("Correct-horse-9")).toBeUndefined();
  });

  it("says too short under the minimum, whatever else it holds", () => {
    for (const password of ["", "Ab1!", "Abcdefgh1!x"]) expect(passwordShortfall(password)).toBe("password.too_short");
  });

  it("says too weak when an uppercase letter, a digit or a special character is missing", () => {
    for (const password of ["correct-horse-9", "Correct-horse-x", "Correcthorse99"])
      expect(passwordShortfall(password)).toBe("password.too_weak");
  });

  it("reads the classes as Unicode categories: a Greek capital, a dash", () => {
    expect(passwordShortfall("Ωmega heights-9")).toBeUndefined();
  });

  it.each([
    ["space", "Abcdefghijk1 ", "password.too_weak"],
    ["control", "Abcdefghijk1\x00", "password.too_weak"],
    ["combining-mark", "Abcdefghijk1\u0301", "password.too_weak"],
    ["punctuation", "Abcdefghijk1!", undefined],
    ["symbol", "Abcdefghijk1€", undefined],
  ])("counts as special a punctuation or a symbol only, as the server does (%s)", (_case, password, code) => {
    expect(passwordShortfall(password)).toBe(code);
  });

  it("counts characters, not UTF-16 units, as the server does", () => {
    expect(passwordShortfall("A1!" + "\u{1F525}".repeat(8))).toBe("password.too_short");
  });

  it("names the minimum the layer's seeds name", () => {
    expect(PASSWORD_MINIMUM).toBe(ACCOUNTS.passwordMinimum);
  });
});

describe("the words of a password under the minimum", () => {
  // SHOWN AT EVERY DOOR, the provisional password at a creation included: they
  // say the whole rule, as the field's helper does, never « the new password ».
  it.each([["fr", FR], ["en", EN]] as const)("say the whole rule, and no « new » (%s)", (_language, catalogue) => {
    const rule = catalogue.common.passwordRule;
    const whole = rule.slice(rule.indexOf("{{minimum}}"), -1).toLowerCase();
    const said = catalogue.refusals.password.too_short.toLowerCase();
    expect(said).toContain(whole);
    expect(said).not.toMatch(/\bnouveau\b|\bnew\b/);
  });
});
