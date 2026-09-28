// The named states of the « Trackers » page.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

export function trackersStates(): NamedState[] {
  return [
    [
      "trackers-page",
      "Trackers — la page",
      () => applyState({ page: "trackers", phase: "ready" }),
    ],
    [
      "trackers-roster",
      "Trackers — un par tracker",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
      },
    ],
    [
      "trackers-roster-empty",
      "Trackers — aucun tracker configuré",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setTrackersEmpty(true);
        applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
      },
    ],
  ];
}
