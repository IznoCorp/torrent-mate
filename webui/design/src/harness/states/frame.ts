// The named states of the frame — the navigation drawer and the address nobody serves.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import i18next from "../../i18n";
import { applyState, poseTrail, type NamedState } from "../drive";
import { walk } from "../../app/page-switch";
import { toast } from "../../lib/shell-doors";
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
    [
      "bar-trackers-alert",
      "La barre — l'onglet Trackers porte le badge de l'alerte, hors de sa page, seuil POSÉ sur c411 (economy.alert_threshold : une demande, la clé manque au moteur)",
      () => {
        window.__mocks?.reset();
        window.__mocks?.poseAlertThreshold("c411", 1.5);
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
      },
    ],
    [
      "bar-trackers-refused",
      "La barre — l'onglet Trackers porte un badge que seuls les échecs de cross-seed justifient, hors de sa page (INVENTÉ ; les deux pannes de tracker levées, POSÉ)",
      () => {
        window.__mocks?.reset();
        // THE TWO TRACKERS A FAILURE SWITCHED OFF RECOVER, so only the cross-seed's failures count.
        window.__mocks?.poseRecovered("lacale");
        window.__mocks?.poseRecovered("digitalcore.club");
        for (const address of ["/api/v1/trackers", "/api/v1/acquisition/downloads", "/api/v1/acquisition/obligations"]) {
          window.__queries?.removeQueries({ queryKey: [address] });
        }
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
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
      "Bouton du menu — rien à dire (machine saine posée : disques avec de la place, index sans anomalie)",
      () => {
        // RE-AIMED OUT LOUD (L24, OPEN 2 = A): a disk nearly full and an index
        // anomaly count in the badge now, and the seed at rest is the operator's
        // real machine, which has both. A machine with nothing to say is POSED.
        window.__mocks?.setTmpOrphans(false);
        window.__mocks?.setMachineHealthy(true);
        applyState({ page: "lib", phase: "ready" });
      },
    ],
    [
      "system-disk-filling",
      "Bouton du menu — un disque bientôt plein et une anomalie d'index comptent",
      () => {
        window.__mocks?.reset();
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

/* THE NAVIGATION STATES: each lays the trail it shows under the page it draws,
   so Retour on tm-design replays the path (DESIGN maquette-navigation § 4). */
export function navigationStates(): NamedState[] {
  return [
    [
      "nav-exit-armed",
      "Navigation — Retour sur la page d'entrée : la garde de sortie armée",
      () => {
        applyState({ page: "acq", acqTab: "follows", phase: "ready" });
        poseTrail(["acq"]);
        walk.armedExit = Date.now();
        toast?.show({ message: i18next.t("message.oneMoreBack") });
      },
    ],
    [
      "nav-trail-settings",
      "Navigation — Réglages ouverts par Système, lui-même ouvert depuis la Médiathèque",
      () => {
        applyState({ page: "cfg", phase: "ready" });
        poseTrail(["acq", "lib", "sys", "cfg"]);
      },
    ],
    [
      "nav-trail-revisited",
      "Navigation — Acquisition → Système → Acquisition → Réglages → Système : Système remonte en haut de la piste, Retour ramène à Réglages puis à la page d'entrée",
      () => {
        applyState({ page: "sys", phase: "ready" });
        poseTrail(["acq", "cfg", "sys"]);
      },
    ],
  ];
}
