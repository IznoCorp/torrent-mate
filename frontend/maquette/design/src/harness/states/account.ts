// The named states of the account page.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label is what the ≡ panel shows, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

export function accountStates(): NamedState[] {
  return [
    [
      "profile",
      "Profil et préférences",
      () => applyState({ page: "profile", phase: "ready" }),
    ],
  ];
}
