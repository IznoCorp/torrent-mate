// The password policy every local door applies (the operator, 2026-10-04): at
// least twelve characters, one uppercase letter, one digit and one special
// character — the owner's fallback password and every local account's.
//
// THE SERVER'S RULE, READ THE SAME WAY (`personalscraper/app/accounts/passwords.py`
// `policy_refusal`): characters are code points, and the classes are Unicode
// categories — uppercase `Lu`, digit `Nd`, special anything that is neither a
// letter nor a number. The layer refuses by this check, and the forms say the
// rule — and a password that breaks it — before anything is asked.

/** The shortest password a local door accepts, in characters. */
export const PASSWORD_MINIMUM = 12;

/** Why a password breaks the policy: the refusal code the server answers. */
export type PasswordShortfall = "password.too_short" | "password.too_weak";

/**
 * Why a password breaks the policy, if it does.
 *
 * @param password The password typed.
 * @returns `password.too_short` under the minimum, `password.too_weak` when a
 *   class is missing, or undefined when it meets the policy.
 */
export function passwordShortfall(password: string): PasswordShortfall | undefined {
  if ([...password].length < PASSWORD_MINIMUM) return "password.too_short";
  const upper = /\p{Lu}/u.test(password);
  const digit = /\p{Nd}/u.test(password);
  const special = /[^\p{L}\p{N}]/u.test(password);
  return upper && digit && special ? undefined : "password.too_weak";
}
