// The named states of the entry — the install offers, the startup screen and the sign-in gate.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

// The entry's verbs, said the way the table says them. A named state only ever
// runs inside the driver, where no history is written, so the sign-in screen is
// raised silently: the address stays the one the state was driven from.
const showSignIn = (withError: boolean) => window.__entry?.showSignIn(withError, true);
const showStartup = () => window.__entry?.showStartup();
const showInstallation = (platform: "ios" | "android") => window.__entry?.showInstall(platform);

export function entryStates(): NamedState[] {
  return [
    [
      "pwa-android",
      "Installation — Android et bureau",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        showInstallation("android");
      },
    ],
    [
      "pwa-ios",
      "Installation — iOS, méthode manuelle",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        showInstallation("ios");
      },
    ],
    [
      "startup",
      "Démarrage — l'interface se charge",
      () => {
        applyState({ page: "acq", acqTab: "now", phase: "ready" });
        showStartup();
      },
    ],
    ["signin", "Connexion — écran d'entrée", () => showSignIn(false)],
    [
      "signin-error",
      "Connexion — identifiants refusés",
      () => showSignIn(true),
    ],
  ];
}
