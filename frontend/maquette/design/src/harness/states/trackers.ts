// The named states of the « Trackers » page.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { openRemoveConfirm } from "../../features/trackers/remove-verb";

// How long a fold waits for the entry it sits in to be drawn before a finger opens it.
const OPEN_AFTER = 300;
// Long enough that a read held back is still in flight when the state is measured.
const HELD_BACK = 60000;
// The page's three reads, by operation and by the address its cache keys on.
const PAGE_READS: [string, string][] = [
  ["readTrackers", "/api/trackers"],
  ["readDownloads", "/api/acquisition/downloads"],
  ["readObligations", "/api/acquisition/obligations"],
];

/**
 * Sets every read of the page to one outcome, its cached answer dropped so the
 * page asks again.
 *
 * @param outcome Held back, or answered with a failure.
 */
function poseReads(outcome: { latencyMilliseconds: number } | { status: number }): void {
  window.__mocks?.reset();
  for (const [operation, address] of PAGE_READS) {
    window.__mocks?.setOperationOutcome(operation, outcome);
    window.__queries?.removeQueries({ queryKey: [address] });
  }
}

// THE ENTRIES THE CARD'S STATES ARE POSED ON, each a real seed entry.
const SEEDING_ENTRY = "66e23ab395c438b7db4f7c855bd451d8bb1f0046";
const SEASON_ENTRY = "e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb";
const NO_ARTWORK_ENTRY = "0ff265e478d97d9eae4d1cabd13748e23b9e6cba";
const DOWNLOADING_ENTRY = "c44e8cd75bec37a8337175c6580e85d4e2079da3";
const CROSS_SEED = "7c1e0b2f95c438b7db4f7c855bd451d8bb1f0046";
// The longest release name `acquire.db` holds (132 characters), a real name.
const LONG_NAME =
  "Stuart.Fails.to.Save.the.Universe.S01E07.Spoiler.Dexys.Midnight.Runners.Get.a.Royalty.Payment.MULTi.1080p.WEB.SDR.EAC3.5.1.x265-BYOR";
// A seconds' day, to date what the client added.
const DAY = 86400;
// THE CLIENT'S FIGURES, COMPOSED: its one read was never taken, so a state that
// needs them poses them — President Curtis complete, sent at its own ratio.
const SEEDING_SIZE = 803859794;
const FIGURES = {
  addedAt: 1790860805 - 7 * DAY,
  swarmSeeds: 12,
  swarmLeechers: 3,
  downloadedBytes: SEEDING_SIZE,
  uploadedBytes: Math.round(SEEDING_SIZE * 0.42),
  downloadRate: 0,
  uploadRate: 0,
};
// An upload under way: 310 Ko/s.
const UPLOAD_RATE = 310000;
// Les Zinzins de l'Espace downloading, a third received, at 2,4 Mo/s — composed.
const DOWNLOADING_SIZE = 1200000000;
const DOWNLOADING = {
  addedAt: 1790860805 - DAY,
  swarmSeeds: 8,
  swarmLeechers: 14,
  downloadedBytes: Math.round(DOWNLOADING_SIZE * 0.34),
  uploadedBytes: 0,
  downloadRate: 2400000,
  uploadRate: 0,
};
// A film's entry, posed on a real entry: a film of the library, its sheet and its
// poster real, its release name composed.
const FILM = {
  kind: "movie" as const,
  title: "On l'appelait Robin des Bois",
  name: "On.l.appelait.Robin.des.Bois.2026.MULTi.1080p.WEB.H264",
  season: null,
  episode: null,
  ids: { tmdb: "1284465", imdb: "tt32273171" },
  poster: "assets/posters/91d3af04.webp",
};
// AN UNLINKED ENTRY, posed on a real one: the real undecided folder the
// arbitration queue holds, no medium linked, its folder the path to resolution.
const UNLINKED_FOLDER = "Backrooms.2026.MULTi.2160p.WEB-DL";
const UNLINKED = {
  kind: "movie" as const,
  title: "Backrooms",
  name: UNLINKED_FOLDER,
  season: null,
  episode: null,
  ids: null,
  poster: null,
  folder: UNLINKED_FOLDER,
};
// How far a finger drags a card to rest it open on its right drawer.
const SWIPE_TRAVEL = 160;

/**
 * Poses what one entry shows and leaves it alone in the client, then lands on
 * the « Torrents » tab: the card IS the state.
 *
 * @param infoHash The entry.
 * @param fields What the entry is given, beyond its seed.
 */
function oneCard(infoHash: string, fields: Parameters<NonNullable<typeof window.__mocks>["poseEntry"]>[1]): void {
  window.__mocks?.reset();
  dropReads();
  window.__mocks?.poseEntry(infoHash, fields);
  window.__mocks?.poseOneEntry(infoHash);
  applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
}

/**
 * Opens one entry's panel, as a tap on its card's body does.
 *
 * @param infoHash The entry.
 * @param tracker The tracker it runs on.
 */
function openTorrentPanel(infoHash: string, tracker: string): void {
  window.__panel.produce("torrent", `${infoHash}:${tracker}`);
}

/** The page's reads, forgotten: the next render asks again and reads what is posed. */
function dropReads(): void {
  for (const [, address] of PAGE_READS) window.__queries?.removeQueries({ queryKey: [address] });
}

/** Drags the first card left by a finger's travel, once drawn, so its right drawer rests open. */
function swipeFirstCardOpen(): void {
  window.setTimeout(() => {
    const card = document.querySelector<HTMLElement>('#view [data-part="torrents/row"] [data-part="card"]');
    if (card === null) return;
    const box = card.getBoundingClientRect();
    const y = box.top + box.height / 2;
    const at = (type: string, x: number) =>
      card.dispatchEvent(new PointerEvent(type, { bubbles: true, isPrimary: true, clientX: x, clientY: y, pointerId: 1 }));
    at("pointerdown", box.right - 20);
    at("pointermove", box.right - 40);
    at("pointermove", box.right - 20 - SWIPE_TRAVEL);
    at("pointerup", box.right - 20 - SWIPE_TRAVEL);
  }, OPEN_AFTER);
}

/** Poses two broken obligations on c411 whose torrents are gone: a derivation, shown as one. */
function poseTwoBrokenObligations(): void {
  window.__mocks?.reset();
  window.__mocks?.poseBrokenObligation("0ff265e478d97d9eae4d1cabd13748e23b9e6cba");
  window.__mocks?.poseBrokenObligation("e1af6819d9e3159e0aa191b534b6a66af4344788");
}

export function trackersStates(): NamedState[] {
  return [
    [
      "trackers-page",
      "Trackers — la page, ouverte sur « Torrents » la première fois",
      () => applyState({ page: "trackers", phase: "ready" }),
    ],
    [
      "trackers-page-remembered",
      "Trackers — une seconde visite, « Trackers » ouvert en dernier sur cet appareil",
      () => {
        window.__mocks?.reset();
        try {
          window.localStorage.setItem("trackers-tab", "trackers");
        } catch {
          // Storage refused: the state still lands on the tab it names.
        }
        applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
      },
    ],
    [
      "trackers-landing-named",
      "Trackers — « Voir le tracker » d'une carte différée, qui nomme trackers:c411",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "trackers", trackersFilter: "c411", phase: "ready" });
      },
    ],
    [
      "torrents-selector",
      "Torrents — le sélecteur de tracker en tête de liste, sans filtre : « Tous les trackers »",
      () => {
        window.__mocks?.reset();
        dropReads();
        applyState({ page: "trackers", trackersTab: "torrents", trackersFilter: "", phase: "ready" });
      },
    ],
    [
      "torrents-selector-open",
      "Torrents — le panneau du sélecteur : « Tous les trackers » puis chaque tracker, avec son nombre de torrents",
      () => {
        window.__mocks?.reset();
        dropReads();
        applyState({ page: "trackers", trackersTab: "torrents", trackersFilter: "", phase: "ready" });
        window.setTimeout(() => window.__panel.produce("trackers-selector"), OPEN_AFTER);
      },
    ],
    [
      "torrents-legend",
      "Torrents — la légende de chaque code présent : états, origines, obligations (états et obligations POSÉS)",
      () => {
        window.__mocks?.reset();
        dropReads();
        window.__mocks?.setObligationSatisfied(SEASON_ENTRY);
        window.__mocks?.setObligationBreached("8d51568b1a4f46e1fb7e7b535b52a5203312fc28");
        window.__mocks?.poseEntry("e1af6819d9e3159e0aa191b534b6a66af4344788", { state: "paused" });
        window.__mocks?.poseEntry(NO_ARTWORK_ENTRY, { state: "stalled" });
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
    [
      "torrents-legend-partial",
      "Torrents — filtrés sur tr4ker : la légende ne dit que les codes de ce qui est affiché",
      () => {
        window.__mocks?.reset();
        dropReads();
        applyState({ page: "trackers", trackersTab: "torrents", trackersFilter: "tr4ker", phase: "ready" });
      },
    ],
    [
      "trackers-loading",
      "Trackers — la page, ses lectures en cours",
      () => {
        poseReads({ latencyMilliseconds: HELD_BACK });
        applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
      },
    ],
    [
      "trackers-error",
      "Trackers — la page, ses lectures en échec",
      () => {
        poseReads({ status: 500 });
        applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
      },
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
      "torrents-one",
      "Torrents — une seule entrée dans le client (les autres retirées, POSÉ)",
      () => oneCard(SEEDING_ENTRY, {}),
    ],
    [
      "torrents-loading",
      "Torrents — les lectures en cours",
      () => {
        poseReads({ latencyMilliseconds: HELD_BACK });
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
    [
      "torrents-error",
      "Torrents — les lectures en échec",
      () => {
        poseReads({ status: 500 });
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
    [
      "torrent-card-long-name",
      "Torrents — un nom de 132 caractères, le plus long d'acquire.db, POSÉ sur President Curtis : entier, jamais coupé",
      () => oneCard(SEEDING_ENTRY, { name: LONG_NAME }),
    ],
    [
      "torrent-card-unlinked",
      "Torrents — une entrée sans média lié, POSÉE (le dossier réel Backrooms en attente d'arbitrage) : le dossier à la place de l'affiche",
      () => oneCard(SEEDING_ENTRY, UNLINKED),
    ],
    [
      "torrent-card-no-artwork",
      "Torrents — Lanterns, lié mais sans affiche : ses initiales mènent à sa fiche",
      () => oneCard(NO_ARTWORK_ENTRY, {}),
    ],
    [
      "torrent-card-no-popularity",
      "Torrents — le client ne dit pas les sources (chiffres COMPOSÉS, sources nulles) : « Sources inconnues », jamais 0",
      () => oneCard(SEEDING_ENTRY, { ...FIGURES, swarmSeeds: null, swarmLeechers: null }),
    ],
    [
      "torrent-card-downloading",
      "Torrents — Les Zinzins de l'Espace en téléchargement (réel, 34 %), débit inconnu",
      () => oneCard(DOWNLOADING_ENTRY, {}),
    ],
    [
      "torrent-card-stalled",
      "Torrents — une entrée bloquée, état POSÉ sur President Curtis",
      () => oneCard(SEEDING_ENTRY, { state: "stalled" }),
    ],
    [
      "torrent-card-paused",
      "Torrents — une entrée en pause, état POSÉ sur President Curtis",
      () => oneCard(SEEDING_ENTRY, { state: "paused" }),
    ],
    [
      "torrent-card-queued",
      "Torrents — une entrée en file d'attente, état POSÉ sur President Curtis",
      () => oneCard(SEEDING_ENTRY, { state: "queued" }),
    ],
    [
      "torrent-card-errored",
      "Torrents — une entrée en erreur et sa raison, POSÉES sur President Curtis",
      () => oneCard(SEEDING_ENTRY, { state: "errored", errorReason: "No space left on device" }),
    ],
    [
      "torrent-card-missing",
      "Torrents — une entrée dont les fichiers sont introuvables, état POSÉ sur President Curtis",
      () => oneCard(SEEDING_ENTRY, { state: "missing" }),
    ],
    [
      "torrent-card-cross-seed",
      "Torrents — le cross-seed de President Curtis sur tr4ker, son point d'origine",
      () => oneCard(CROSS_SEED, {}),
    ],
    [
      "torrent-card-volumes",
      "Torrents — au repos : reçu et envoyé (chiffres du client COMPOSÉS sur President Curtis)",
      () => oneCard(SEEDING_ENTRY, FIGURES),
    ],
    [
      "torrent-card-downloading-progress",
      "Torrents — en téléchargement : la barre et le débit de réception (débit COMPOSÉ sur Les Zinzins de l'Espace)",
      () => oneCard(DOWNLOADING_ENTRY, DOWNLOADING),
    ],
    [
      "torrent-card-uploading-rate",
      "Torrents — en envoi : le débit d'envoi seul, sans barre (COMPOSÉ sur President Curtis)",
      () => oneCard(SEEDING_ENTRY, { ...FIGURES, uploadRate: UPLOAD_RATE }),
    ],
    [
      "torrent-card-film",
      "Torrents — l'entrée d'un film, POSÉE (On l'appelait Robin des Bois, nom de release composé) : l'affiche ouvre la fiche du film",
      () => oneCard(SEEDING_ENTRY, FILM),
    ],
    [
      "torrent-panel",
      "Torrents — le panneau d'une entrée liée, la saison 22 d'American Dad! (chiffres COMPOSÉS)",
      () => {
        oneCard(SEASON_ENTRY, { ...FIGURES, downloadedBytes: 9040170236, uploadedBytes: 11842622909 });
        openTorrentPanel(SEASON_ENTRY, "c411");
      },
    ],
    [
      "torrent-panel-episode",
      "Torrents — le panneau d'un épisode : le média nomme la série et S01E10 (chiffres COMPOSÉS)",
      () => {
        oneCard(SEEDING_ENTRY, FIGURES);
        openTorrentPanel(SEEDING_ENTRY, "c411");
      },
    ],
    [
      "torrent-panel-unlinked",
      "Torrents — le panneau d'une entrée sans média, POSÉE : « Identifier » mène au dossier Backrooms",
      () => {
        oneCard(SEEDING_ENTRY, UNLINKED);
        openTorrentPanel(SEEDING_ENTRY, "c411");
      },
    ],
    [
      "torrent-panel-unlinked-no-folder",
      "Torrents — le panneau d'une entrée sans média ni dossier, POSÉE : « Aucun dossier à identifier. »",
      () => {
        oneCard(SEEDING_ENTRY, { ...UNLINKED, folder: null });
        openTorrentPanel(SEEDING_ENTRY, "c411");
      },
    ],
    [
      "torrent-panel-partial",
      "Torrents — le panneau quand le client ne dit rien de plus : chaque chiffre « inconnu »",
      () => {
        oneCard(SEEDING_ENTRY, {});
        openTorrentPanel(SEEDING_ENTRY, "c411");
      },
    ],
    [
      "torrent-swipe-remove",
      "Torrents — une carte glissée à gauche, son tiroir « Retirer » ouvert",
      () => {
        window.__mocks?.reset();
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
        swipeFirstCardOpen();
      },
    ],
    [
      "torrents-obligation-done",
      "Torrents — une obligation terminée, POSÉE sur American Dad! (le back-end lira satisfied_at), le torrent toujours en seed",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setObligationSatisfied("e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb");
        applyState({ page: "trackers", trackersTab: "torrents", phase: "ready" });
      },
    ],
    [
      "torrent-remove-confirm",
      "Torrents — « Retirer de qBittorrent » sur un torrent qui ne doit plus rien, son obligation terminée POSÉE (le back-end lira satisfied_at)",
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
      "Trackers — un tracker sous son propre seuil d'alerte, seuil POSÉ sur c411 (economy.alert_threshold : une demande, la clé manque au moteur)",
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
    [
      "tracker-broken-obligations",
      "Trackers — deux obligations rompues, leur torrent parti, POSÉES sur Lanterns et Ted Lasso (le back-end lira la rupture)",
      () => {
        // A DERIVATION, SHOWN AS ONE: no real obligation has been broken.
        poseTwoBrokenObligations();
        applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
      },
    ],
    [
      "tracker-broken-obligations-open",
      "Trackers — les obligations rompues de c411 dépliées, chacune avec « Vu »",
      () => {
        poseTwoBrokenObligations();
        applyState({ page: "trackers", trackersTab: "trackers", trackersFilter: "c411", phase: "ready" });
        // THE FOLD OPENED THE WAY A FINGER OPENS IT, once the entry is drawn.
        window.setTimeout(() => {
          document.querySelector<HTMLElement>('[data-part="trackers/broken-obligations-toggle"]')?.click();
        }, OPEN_AFTER);
      },
    ],
  ];
}
