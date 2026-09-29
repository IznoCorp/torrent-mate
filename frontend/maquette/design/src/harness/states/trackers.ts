// The named states of the « Trackers » page.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { openRemoveConfirm } from "../../features/trackers/remove-verb";

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
    [
      "trackers-entry-open",
      "Trackers — une entrée ouverte sur sa politique",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "trackers", trackersFilter: "c411", phase: "ready" });
      },
    ],
    [
      "trackers-policy-unset",
      "Trackers — une entrée sans politique",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "trackers", trackersFilter: "tr4ker", phase: "ready" });
      },
    ],
    [
      "torrents-list",
      "Torrents — une ligne par entrée, tous trackers",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
    [
      "torrents-list-filtered",
      "Torrents — filtrés sur un tracker",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "torrents", trackersFilter: "c411", phase: "ready" });
      },
    ],
    [
      "torrents-empty",
      "Torrents — rien en cours nulle part",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setDownloadsEmpty(true);
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
    [
      "torrents-empty-filtered",
      "Torrents — rien en cours sur le tracker filtré",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setTrackerIdle("tr4ker");
        applyState({ page: "trackers", trackersTab: "torrents", trackersFilter: "tr4ker", phase: "ready" });
      },
    ],
    [
      "torrents-obligation-done",
      "Torrents — une obligation terminée, le torrent toujours en seed",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setObligationSatisfied("e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb");
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
    [
      "torrent-remove-confirm",
      "Torrents — « Retirer de qBittorrent » sur un torrent qui ne doit plus rien",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setObligationSatisfied("e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb");
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
        openRemoveConfirm("e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb", "c411");
      },
    ],
    [
      "torrent-remove-confirm-obligation",
      "Torrents — « Retirer de qBittorrent » sur un torrent qui doit une obligation",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
        openRemoveConfirm("66e23ab395c438b7db4f7c855bd451d8bb1f0046", "c411");
      },
    ],
    [
      "torrent-remove-confirm-shared",
      "Torrents — « Retirer de qBittorrent » sur une entrée dont un autre tracker partage les fichiers, sous obligation",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
        openRemoveConfirm("7c1e0b2f95c438b7db4f7c855bd451d8bb1f0046", "tr4ker");
      },
    ],
    [
      "torrents-external-removal",
      "Torrents — une entrée retirée À LA MAIN dans qBittorrent, son obligation libérée, POSÉ sur Ted Lasso (le back-end lira la libération)",
      () => {
        // A DERIVATION, SHOWN AS ONE: no real obligation has been released, so
        // a removal by hand is posed on a real entry.
        window.__mocks?.reset();
        window.__mocks?.poseExternalRemoval("e1af6819d9e3159e0aa191b534b6a66af4344788");
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
    [
      "tracker-alert-active",
      "Trackers — un tracker sous son propre seuil d'alerte, le seuil saisi par l'opérateur",
      () => {
        window.__mocks?.reset();
        window.__mocks?.poseAlertThreshold("c411", 1.5);
        applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
      },
    ],
    [
      "tracker-identifier-refused",
      "Trackers — un tracker qui refuse l'identifiant configuré, POSÉ sur tr4ker (le back-end lira le refus)",
      () => {
        // A DERIVATION, SHOWN AS ONE: no real tracker refuses its identifier.
        window.__mocks?.reset();
        window.__mocks?.poseIdentifierRefused("tr4ker");
        applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
      },
    ],
    [
      "torrent-obligation-breached",
      "Torrents — une obligation rompue, le torrent toujours actif, POSÉE sur Star Trek: Strange New Worlds (le back-end lira la rupture)",
      () => {
        // A DERIVATION, SHOWN AS ONE: no real obligation has been broken.
        window.__mocks?.reset();
        window.__mocks?.setObligationBreached("8d51568b1a4f46e1fb7e7b535b52a5203312fc28");
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
  ];
}
