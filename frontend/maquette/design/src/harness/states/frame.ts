// The named states of the frame — the navigation drawer and the address nobody serves.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label is what the ≡ panel shows, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { openDrawer } from "../../engine/legacy.js";

export function drawerStates(): NamedState[] {
  return [
    [
      "drawer-navigation",
      "Tiroir de navigation (hamburger)",
      () => {
        applyState({ page: "acq", phase: "ready" });
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
