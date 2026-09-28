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

export function menuStates(): NamedState[] {
  return [
    [
      "menu-system-badge",
      "Bouton du menu — Système a quelque chose à dire",
      () => {
        // A lock whose process is gone, over the seeded leftover entry: the
        // button reads two, from a page that draws nothing of Système.
        window.__mocks?.setLockStale(true);
        applyState({ page: "lib", phase: "ready" });
      },
    ],
    [
      "menu-clear",
      "Bouton du menu — rien à dire",
      () => {
        window.__mocks?.setTmpOrphans(false);
        applyState({ page: "lib", phase: "ready" });
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
