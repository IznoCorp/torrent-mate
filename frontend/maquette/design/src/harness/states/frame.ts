// The named states of the frame — the navigation drawer and the address nobody serves.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { openDrawer } from "../../app/frame-verbs";

export function drawerStates(): NamedState[] {
  return [
    [
      "drawer-navigation",
      "Tiroir de navigation (hamburger)",
      () => {
        // THE TAB IS PINNED: the driver's reset leaves `acqTab`, so an
        // unpinned tab is whatever the state before left.
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        openDrawer();
      },
    ],
  ];
}

export function notFoundStates(): NamedState[] {
  return [
    [
      "not-found",
      "Une adresse qui n'existe pas",
      () => applyState({ page: "une-page-qui-n-existe-pas", phase: "ready" }),
    ],
  ];
}
