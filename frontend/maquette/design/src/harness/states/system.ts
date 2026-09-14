// The named states of the machine's page, « Système ».
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

// THE PIPELINE'S STATES JOIN THIS TABLE ONE SURFACE AT A TIME. The global
// levers, the veille, the locks, the passages and a passage's detail add their
// named states here in the commit that draws the surface behind each id —
// never earlier, because `harness/states.py` fails an id that renders nothing.
export function systemStates(): NamedState[] {
  return [
    [
      "system",
      "Système — la santé de la machine",
      () => applyState({ page: "sys", phase: "ready", fault: false }),
    ],
    [
      "system-outage",
      "Système — une panne (simulée)",
      () => applyState({ page: "sys", phase: "ready", fault: true }),
    ],
    [
      "system-loading",
      "Système — chargement",
      () => applyState({ page: "sys", phase: "loading", fault: false }),
    ],
    [
      "system-error",
      "Système — erreur",
      () => applyState({ page: "sys", phase: "error", fault: false }),
    ],
  ];
}
