// A write that carries a PASSWORD is sent now or not at all — never through the
// outbox. Held while offline and replayed later, it would sit in the browser's
// storage and change a password nobody is watching change. A network that does
// not answer is said, and nothing is kept.
//
// Shared by the three acts that carry one: a local account's own password in
// Profil, and the provisional password « Comptes » gives at creation and on a
// reset (the operator, 2026-10-03: « A »).
//
// And by one act that carries none but must be answered before it shows: the
// account's own language, which the interface speaks only once the server holds
// it — held back, it would leave the interface in a language nobody chose.

/**
 * Sends one password-bearing write to an address the contract declares.
 *
 * @param method The method, upper case.
 * @param path The contract address, parameters already substituted.
 * @param body What to send.
 * @returns Null once accepted, the problem the server answered, or undefined
 *     when it did not answer at all.
 */
export async function sendNow(method: "POST" | "PUT", path: string, body: unknown): Promise<unknown> {
  const answer = await globalThis.fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => null);
  if (answer?.ok) return null;
  return answer ? answer.json().catch(() => undefined) : undefined;
}
