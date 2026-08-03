/**
 * meta — the acquisition five-state vocabulary (acq-states phase 8).
 *
 * One test per state: every server state must map to a French label, a DS tone
 * and a disambiguating hint — a raw slug reaching the operator is a NE-DOIT-PAS-4
 * violation. The « En attente » / « Non vérifié » pair gets its own guard: same
 * tone, so the wording is the ONLY thing keeping them apart.
 */

import { describe, expect, it } from "vitest";

import type { EpisodeCompleteness } from "@/api/acquisition";

import {
  DEFERRED_REASON_LABEL,
  EPISODE_STATE_HINT,
  EPISODE_STATE_LABEL,
  EPISODE_STATE_TONE,
  FOLLOW_STATUS_HINT,
  FOLLOW_STATUS_LABEL,
  FOLLOW_STATUS_TONE,
  OBLIGATION_STATUS_OPTIONS,
  RUN_OUTCOME_LABEL,
  RUN_OUTCOME_TONE,
  STATUS_LABEL,
  STATUS_TONE,
  WANTED_STATUS_OPTIONS,
  followStatusHint,
  followStatusLabel,
  searchOutcomeReason,
  waitingGroups,
  type EpisodeState,
  type FollowStatus,
} from "./meta";

/** The seven card statuses the backend serves (schema.d.ts truth). */
const FOLLOW_STATUSES: readonly FollowStatus[] = [
  "disabled",
  "verification_en_cours",
  "a_recuperer",
  "en_acquisition",
  "en_attente",
  "non_verifie",
  "a_jour",
];

/** The per-episode states the backend serves (schema.d.ts truth). */
const EPISODE_STATES: readonly EpisodeState[] = [
  "annonce",
  "en_mediatheque",
  "a_recuperer",
  "en_acquisition",
  "en_attente",
  "non_verifie",
  "absorbed",
];

describe("FOLLOW status vocabulary", () => {
  it.each([
    ["disabled", "En pause", "neutral"],
    ["verification_en_cours", "Vérification en cours", "info"],
    ["a_recuperer", "À récupérer", "warning"],
    ["en_acquisition", "En cours d'acquisition", "info"],
    ["en_attente", "En attente de torrent", "waiting"],
    ["non_verifie", "Non vérifié", "muted"],
    ["a_jour", "À jour", "success"],
  ])("maps %s to its série label and tone", (status, label, tone) => {
    expect(FOLLOW_STATUS_LABEL[status as FollowStatus]).toBe(label);
    expect(FOLLOW_STATUS_TONE[status as FollowStatus]).toBe(tone);
  });

  it("covers every served status — no state can render as a raw slug", () => {
    for (const status of FOLLOW_STATUSES) {
      expect(FOLLOW_STATUS_LABEL[status]).toBeTruthy();
      expect(FOLLOW_STATUS_TONE[status]).toBeTruthy();
      expect(FOLLOW_STATUS_HINT[status]).toBeTruthy();
      // The label is French prose, never the machine token (NE-DOIT-PAS-4).
      expect(FOLLOW_STATUS_LABEL[status]).not.toBe(status);
    }
    expect(Object.keys(FOLLOW_STATUS_LABEL).sort()).toEqual(
      [...FOLLOW_STATUSES].sort(),
    );
  });

  it("carries no dead literal from the pre-split vocabulary", () => {
    for (const dead of ["pending", "acquiring", "incomplete", "up_to_date"]) {
      expect(Object.keys(FOLLOW_STATUS_LABEL)).not.toContain(dead);
      expect(Object.keys(FOLLOW_STATUS_TONE)).not.toContain(dead);
    }
  });
});

describe("followStatusLabel / followStatusHint (film vs série)", () => {
  it("reads « Acquis » for an owned film and « À jour » for a série", () => {
    expect(followStatusLabel("a_jour", "movie")).toBe("Acquis");
    expect(followStatusLabel("a_jour", "show")).toBe("À jour");
    expect(followStatusHint("a_jour", "movie")).toBe(
      "Le film est en médiathèque.",
    );
  });

  it("shares the série wording for every non-overridden state", () => {
    for (const status of FOLLOW_STATUSES) {
      if (status === "a_jour") continue;
      expect(followStatusLabel(status, "movie")).toBe(
        FOLLOW_STATUS_LABEL[status],
      );
      expect(followStatusHint(status, "movie")).toBe(FOLLOW_STATUS_HINT[status]);
    }
  });
});

describe("EPISODE state vocabulary", () => {
  it.each([
    ["en_mediatheque", "En médiathèque", "success"],
    ["a_recuperer", "À récupérer", "warning"],
    ["en_acquisition", "En cours d'acquisition", "info"],
    ["en_attente", "En attente de torrent", "waiting"],
    ["non_verifie", "Non vérifié", "muted"],
    ["annonce", "Annoncé", "upcoming"],
  ])("maps %s to its label and tone", (state, label, tone) => {
    expect(EPISODE_STATE_LABEL[state as EpisodeState]).toBe(label);
    expect(EPISODE_STATE_TONE[state as EpisodeState]).toBe(tone);
  });

  it("covers every served episode state", () => {
    for (const state of EPISODE_STATES) {
      expect(EPISODE_STATE_LABEL[state]).toBeTruthy();
      expect(EPISODE_STATE_HINT[state]).toBeTruthy();
      expect(EPISODE_STATE_LABEL[state]).not.toBe(state);
    }
    expect(Object.keys(EPISODE_STATE_LABEL).sort()).toEqual(
      [...EPISODE_STATES].sort(),
    );
  });

  it("carries no dead literal from the three-value vocabulary", () => {
    for (const dead of ["en_file", "en_cours", "manquant"]) {
      expect(Object.keys(EPISODE_STATE_LABEL)).not.toContain(dead);
      expect(Object.keys(EPISODE_STATE_TONE)).not.toContain(dead);
    }
  });

  it("gives each of the six live-flow states a DISTINCT tone (operator #9)", () => {
    // « Une couleur par statut »: no two LIVE-FLOW episode states may share a
    // BadgeTone, else the matrix would paint two states the same colour. This
    // is the regression guard for the two collisions that existed at phase-1
    // end (annonce=en_acquisition=info, en_attente=non_verifie=neutral).
    // "absorbed" is excluded on purpose: it is not a state of its own for the
    // operator — it renders EXACTLY like en_acquisition (same tone, same
    // label), because an absorbed episode is simply being acquired inside a
    // season pack.
    const liveFlow = EPISODE_STATES.filter((s) => s !== "absorbed");
    const tones = liveFlow.map((s) => EPISODE_STATE_TONE[s]);
    expect(new Set(tones).size).toBe(liveFlow.length);
  });
});

describe("WANTED-QUEUE status vocabulary (review F8)", () => {
  /** Every wanted-row status the backend can serve to the queue panel. */
  const WANTED_STATUSES: readonly string[] = [
    "pending",
    "searching",
    "grabbed",
    "done",
    "abandoned",
    "absorbed",
    "fallback_episodes",
  ];

  it("maps every served queue status to a French label and a tone", () => {
    for (const status of WANTED_STATUSES) {
      expect(STATUS_LABEL[status], `label for ${status}`).toBeTruthy();
      expect(STATUS_TONE[status], `tone for ${status}`).toBeTruthy();
      // Never the raw machine token in the queue (NE-DOIT-PAS-4).
      expect(STATUS_LABEL[status]).not.toBe(status);
    }
  });

  it.each([
    ["absorbed", "En cours d'acquisition", "info"],
    ["fallback_episodes", "Reporté en épisodes", "warning"],
  ])("maps the season-grab status %s", (status, label, tone) => {
    expect(STATUS_LABEL[status]).toBe(label);
    expect(STATUS_TONE[status]).toBe(tone);
  });

  it("lets the queue filter select the season-grab statuses", () => {
    const values = WANTED_STATUS_OPTIONS.map((o) => o.value);
    // `absorbed` is deliberately NOT offered: an absorbed row simply reads
    // « En cours d'acquisition », so a filter on it would ask the operator to
    // reason about plumbing (season pack vs episode) that changes nothing.
    expect(values).not.toContain("absorbed");
    expect(values).toContain("fallback_episodes");
    // Every option carries French wording, never the raw slug.
    for (const opt of WANTED_STATUS_OPTIONS) {
      expect(opt.label).toBeTruthy();
      expect(opt.label).not.toBe(opt.value);
    }
  });
});

describe("searchOutcomeReason — le motif d'attente en français", () => {
  it.each([
    ["no_candidates", "aucun résultat"],
    ["no_matching_episode", "pas d'épisode exact"],
    ["all_filtered", "rien de conforme au profil"],
  ])("traduit %s en « %s » pour un épisode en attente", (outcome, reason) => {
    expect(searchOutcomeReason("en_attente", outcome)).toBe(reason);
  });

  it.each([
    ["trackers_unavailable", "trackers injoignables"],
    ["circuit_open", "recherche suspendue après trop d'échecs"],
    ["search_api_error", "erreur de recherche côté tracker"],
    ["no_seeders", "aucune source active"],
  ])("explique un non vérifié par %s", (outcome, reason) => {
    expect(searchOutcomeReason("non_verifie", outcome)).toBe(reason);
  });

  it("ne rend JAMAIS le jeton machine, même inconnu (NE-DOIT-PAS-4)", () => {
    const reason = searchOutcomeReason("en_attente", "brand_new_verdict");
    expect(reason).toBe("rien de prenable au dernier passage");
    expect(reason).not.toContain("brand_new_verdict");
  });

  it("se tait quand l'unité n'attend pas ou n'a aucun verdict", () => {
    expect(searchOutcomeReason("en_mediatheque", "no_candidates")).toBeNull();
    expect(searchOutcomeReason("a_recuperer", "no_candidates")).toBeNull();
    expect(searchOutcomeReason("en_acquisition", "all_filtered")).toBeNull();
    expect(searchOutcomeReason("non_verifie", null)).toBeNull();
    expect(searchOutcomeReason("en_attente", undefined)).toBeNull();
  });
});

describe("waitingGroups — un motif, les épisodes qui le partagent", () => {
  const ep = (
    episode: number,
    state: EpisodeCompleteness["state"],
    outcome: string | null,
  ): EpisodeCompleteness => ({
    episode,
    state,
    title: null,
    air_date: null,
    last_search_outcome: outcome,
  });

  it("regroupe les épisodes par motif, numéros triés", () => {
    const groups = waitingGroups([
      ep(3, "en_attente", "all_filtered"),
      ep(1, "en_attente", "all_filtered"),
      ep(2, "en_attente", "no_candidates"),
      ep(4, "en_mediatheque", null),
    ]);

    expect(groups).toEqual([
      { reason: "rien de conforme au profil", episodes: [1, 3] },
      { reason: "aucun résultat", episodes: [2] },
    ]);
  });

  it("ne dit rien quand rien n'attend", () => {
    expect(
      waitingGroups([ep(1, "en_mediatheque", null), ep(2, "a_recuperer", null)]),
    ).toEqual([]);
  });
});

describe("« En attente » vs « Non vérifié » (must not be confusable)", () => {
  it("gives the two states DISTINCT tones, labels AND hints (#24)", () => {
    // #24 — they no longer share a colour: en_attente = solid neutral grey,
    // non_verifie = the muted (dashed info-blue) idle tone, in BOTH maps.
    expect(FOLLOW_STATUS_TONE.en_attente).not.toBe(
      FOLLOW_STATUS_TONE.non_verifie,
    );
    expect(EPISODE_STATE_TONE.en_attente).not.toBe(
      EPISODE_STATE_TONE.non_verifie,
    );
    expect(FOLLOW_STATUS_LABEL.en_attente).not.toBe(
      FOLLOW_STATUS_LABEL.non_verifie,
    );
    expect(FOLLOW_STATUS_HINT.en_attente).not.toBe(
      FOLLOW_STATUS_HINT.non_verifie,
    );
    expect(EPISODE_STATE_LABEL.en_attente).not.toBe(
      EPISODE_STATE_LABEL.non_verifie,
    );
    expect(EPISODE_STATE_HINT.en_attente).not.toBe(
      EPISODE_STATE_HINT.non_verifie,
    );
  });

  it("says « rien de conforme » for en_attente and « pas encore » for non_verifie", () => {
    expect(FOLLOW_STATUS_HINT.en_attente).toMatch(/rien de conforme/);
    expect(FOLLOW_STATUS_HINT.non_verifie).toMatch(/[Pp]as encore vérifié/);
    expect(EPISODE_STATE_HINT.en_attente).toMatch(/rien de conforme/);
    expect(EPISODE_STATE_HINT.non_verifie).toMatch(/[Pp]as encore vérifié/);
  });
});

// ---------------------------------------------------------------------------
// X7 — no-raw-slug coverage for the WatcherPanel / queue / obligations enums
// ---------------------------------------------------------------------------

describe("X7 — les enums servis ne rendent jamais un slug brut", () => {
  it("couvre chaque outcome de run servi (success/error/killed)", () => {
    const SERVED_OUTCOMES = ["success", "error", "killed"] as const;
    for (const outcome of SERVED_OUTCOMES) {
      expect(RUN_OUTCOME_LABEL[outcome]).toBeTruthy();
      expect(RUN_OUTCOME_LABEL[outcome]).not.toBe(outcome);
      expect(RUN_OUTCOME_TONE[outcome]).toBeTruthy();
    }
  });

  it("couvre chaque raison de report du watcher (schéma DeferredTorrent)", () => {
    const SERVED_REASONS = [
      "ratio_below_threshold",
      "content_missing",
      "insufficient_space",
    ] as const;
    for (const reason of SERVED_REASONS) {
      expect(DEFERRED_REASON_LABEL[reason]).toBeTruthy();
      expect(DEFERRED_REASON_LABEL[reason]).not.toBe(reason);
    }
  });

  it("couvre chaque statut filtrable de la file et des obligations", () => {
    // Every selectable status (the « all » sentinel aside) must resolve to a
    // French STATUS_LABEL — the queue Badge and the empty-state sentence
    // both read from it.
    for (const opt of WANTED_STATUS_OPTIONS) {
      if (opt.value === "all") continue;
      expect(STATUS_LABEL[opt.value]).toBeTruthy();
      expect(STATUS_LABEL[opt.value]).not.toBe(opt.value);
    }
    for (const opt of OBLIGATION_STATUS_OPTIONS) {
      if (opt.value === "all") continue;
      expect(STATUS_LABEL[opt.value]).toBeTruthy();
      expect(STATUS_LABEL[opt.value]).not.toBe(opt.value);
    }
  });
});
