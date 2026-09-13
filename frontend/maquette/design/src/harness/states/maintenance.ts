// The named states of the maintenance page.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label is what the ≡ panel shows, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

export function maintenanceStates(): NamedState[] {
  return [
    [
      "maintenance",
      "Maintenance — les rubriques de commandes",
      () => applyState({ page: "maint", phase: "ready", maintTopic: null }),
    ],
    [
      "maintenance-topic",
      "Maintenance — une rubrique et ses commandes",
      () => applyState({ page: "maint", phase: "ready", maintTopic: "fix" }),
    ],
    [
      "maintenance-delete",
      "Maintenance — une commande qui supprime",
      () => {
        applyState({ page: "maint", phase: "ready", maintTopic: "clean" });
        window.__panel.produce("action", "library-clean");
      },
    ],
    [
      "maintenance-loading",
      "Maintenance — chargement",
      () => applyState({ page: "maint", phase: "loading" }),
    ],
  ];
}
