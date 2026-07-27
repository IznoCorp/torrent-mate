/**
 * meta — the acquisition five-state vocabulary (acq-states phase 8).
 *
 * One test per state: every server state must map to a French label, a DS tone
 * and a disambiguating hint — a raw slug reaching the operator is a NE-DOIT-PAS-4
 * violation. The « En attente » / « Non vérifié » pair gets its own guard: same
 * tone, so the wording is the ONLY thing keeping them apart.
 */

import { describe, expect, it } from "vitest";

import {
  EPISODE_STATE_HINT,
  EPISODE_STATE_LABEL,
  EPISODE_STATE_TONE,
  FOLLOW_STATUS_HINT,
  FOLLOW_STATUS_LABEL,
  FOLLOW_STATUS_TONE,
  followStatusHint,
  followStatusLabel,
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

/** The five per-episode states the backend serves (schema.d.ts truth). */
const EPISODE_STATES: readonly EpisodeState[] = [
  "en_mediatheque",
  "a_recuperer",
  "en_acquisition",
  "en_attente",
  "non_verifie",
];

describe("FOLLOW status vocabulary", () => {
  it.each([
    ["disabled", "En pause", "neutral"],
    ["verification_en_cours", "Vérification en cours", "info"],
    ["a_recuperer", "À récupérer", "warning"],
    ["en_acquisition", "En cours d'acquisition", "info"],
    ["en_attente", "En attente", "neutral"],
    ["non_verifie", "Non vérifié", "neutral"],
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
    ["en_attente", "En attente", "neutral"],
    ["non_verifie", "Non vérifié", "neutral"],
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
});

describe("« En attente » vs « Non vérifié » (must not be confusable)", () => {
  it("gives the two neutral states distinct labels AND distinct hints", () => {
    expect(FOLLOW_STATUS_TONE.en_attente).toBe(FOLLOW_STATUS_TONE.non_verifie);
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
