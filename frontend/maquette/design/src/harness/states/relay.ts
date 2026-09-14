// The named states of the live relay's three conditions.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

export function relayStates(): NamedState[] {
  return [
    [
      "relay-reconnecting",
      "Temps réel — la connexion a été perdue",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        window.__relay.force("reconnecting");
      },
    ],
    [
      "relay-lost",
      "Temps réel — cet écran ne se met plus à jour",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        window.__relay.force("lost");
      },
    ],
    [
      "relay-refused",
      "Temps réel — session expirée",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        window.__relay.force("refused");
      },
    ],
  ];
}
