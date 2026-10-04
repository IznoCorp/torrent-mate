// The password policy every local door applies (the operator, 2026-10-04), as
// the interface says it before the server is asked.
//
// WHAT MAKES THIS NON-VACUOUS. Each case is one the server's own test reads
// (`tests/unit/app/accounts/test_passwords.py`): the same passwords, the same
// codes — the two checks are the same Unicode categories, so they never part.
import { describe, expect, it } from "vitest";
import ACCOUNTS from "../mocks/seeds/accounts.json";
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

  it("reads the classes as Unicode categories: a Greek capital, a space", () => {
    expect(passwordShortfall("Ωmega heights 9")).toBeUndefined();
  });

  it("counts characters, not UTF-16 units, as the server does", () => {
    expect(passwordShortfall("A1!" + "\u{1F525}".repeat(8))).toBe("password.too_short");
  });

  it("names the minimum the layer's seeds name", () => {
    expect(PASSWORD_MINIMUM).toBe(ACCOUNTS.passwordMinimum);
  });
});
