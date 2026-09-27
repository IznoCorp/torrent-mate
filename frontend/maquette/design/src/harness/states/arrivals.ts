// The named states of the arrivals page, « Arrivées ».
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

export function arrivalsStates(): NamedState[] {
  return [
    [
      "arr-idle",
      "Arrivées — état réel (2 blocages)",
      () =>
        applyState({
          page: "arr",
          scen: "real",
          phase: "ready",
          pipe: "idle",
        }),
    ],
    [
      "arr-running",
      "Arrivées — pipeline en cours",
      () =>
        applyState({
          page: "arr",
          scen: "real",
          phase: "ready",
          pipe: "running",
        }),
    ],
    [
      "arr-queued",
      "Arrivées — un passage demandé pendant une maintenance",
      () =>
        applyState({ page: "arr", scen: "real", phase: "ready", pipe: "queued" }),
    ],
    [
      "arr-loaded",
      "Arrivées — chargé",
      () =>
        applyState({
          page: "arr",
          scen: "loaded",
          phase: "ready",
          pipe: "idle",
        }),
    ],
    [
      "arr-loading",
      "Arrivées — chargement",
      () => applyState({ page: "arr", phase: "loading", pipe: "idle" }),
    ],
    [
      "arr-error",
      "Arrivées — erreur",
      () => applyState({ page: "arr", phase: "error", pipe: "idle" }),
    ],
  ];
}
