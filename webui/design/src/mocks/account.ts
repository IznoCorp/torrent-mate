// Who the mock's single account is — the Plex owner by construction (§17).
//
// Its NAME CAN BE CHANGED for the life of the layer's state, which is how a rule
// proves that a line naming the account reads the answer rather than printing a
// constant: the seed renamed, every reader must follow.
import ACCOUNT from "./seeds/account.json";
import { mockState } from "./state";

// Keyed by the state object, so a reset of the layer forgets the rename with
// everything else.
const renamed = new WeakMap<object, string>();

/**
 * The account's name, as the layer answers it now.
 *
 * @returns The seeded name, or the one it was renamed to.
 */
export function accountName(): string {
  return renamed.get(mockState()) ?? ACCOUNT.name;
}

/**
 * Renames the account until the layer is next reset.
 *
 * @param name The new name.
 */
export function renameAccount(name: string): void {
  renamed.set(mockState(), name);
}
