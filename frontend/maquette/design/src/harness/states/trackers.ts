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
      "torrent-remove-confirm-obligation",
      "Torrents — « Retirer de qBittorrent » sur un torrent qui doit une obligation",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
        openRemoveConfirm("66e23ab395c438b7db4f7c855bd451d8bb1f0046", "c411");
      },
    ],
  ];
}
