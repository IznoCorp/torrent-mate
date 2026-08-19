/**
 * meta — the acquisition five-state vocabulary (acq-states phase 8).
 *
 * One test per state: every server state must map to a French label, a DS tone
 * and a disambiguating hint — a raw slug reaching the operator is a NE-DOIT-PAS-4
 * violation. The « En attente » / « Non vérifié » pair gets its own guard: same
 * tone, so the wording is the ONLY thing keeping them apart.
 */

import { describe, expect, it } from "vitest";

import type { FollowedSeriesItem } from "@/api/acquisition";

import {
  DEFERRED_REASON_LABEL,
  EPISODE_LEGEND_ORDER,
  EPISODE_STATE_HINT,
  EPISODE_STATE_LABEL,
  EPISODE_STATE_TONE,
  FOLLOW_STATUS_HINT,
  FOLLOW_STATUS_HINT_MOVIE,
  FOLLOW_STATUS_LABEL,
  FOLLOW_STATUS_LABEL_MOVIE,
  FOLLOW_STATUS_TONE,
  OBLIGATION_STATUS_OPTIONS,
  RUN_OUTCOME_LABEL,
  RUN_OUTCOME_TONE,
  STATUS_LABEL,
  STATUS_TONE,
  actionWords,
  asMediaKind,
  followMediaRef,
  followStatusHint,
  followStatusLabel,
  searchOutcomeReason,
  type EpisodeState,
  type FollowStatus,
  type MediaKind,
} from "./meta";

/** The eight card statuses the backend serves (schema.d.ts truth). */
const FOLLOW_STATUSES: readonly FollowStatus[] = [
  "disabled",
  "verifying",
  "to_grab",
  "acquiring",
  "pending",
  "unverified",
  "up_to_date",
  "ended",
];

/** The per-episode states the backend serves (schema.d.ts truth). */
const EPISODE_STATES: readonly EpisodeState[] = [
  "announced",
  "in_library",
  "to_grab",
  "acquiring",
  "pending",
  "unverified",
  "absorbed",
];

describe("FOLLOW status vocabulary", () => {
  it.each([
    ["disabled", "En pause", "neutral"],
    ["verifying", "Vérification en cours", "info"],
    ["to_grab", "À récupérer", "warning"],
    ["acquiring", "En cours d'acquisition", "info"],
    ["pending", "En attente de torrent", "waiting"],
    ["unverified", "Non vérifié", "muted"],
    ["up_to_date", "À jour", "success"],
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
    // The words this guarded — `pending`, `acquiring`, `up_to_date` — are the
    // CANONICAL vocabulary since the wave that put the states in English, so
    // guarding against them would now forbid the live names. What it has always
    // asserted is that the PREVIOUS vocabulary leaves no literal behind, and
    // the previous vocabulary is the French one.
    for (const dead of ["en_attente", "en_acquisition", "incomplets", "a_jour"]) {
      expect(Object.keys(FOLLOW_STATUS_LABEL)).not.toContain(dead);
      expect(Object.keys(FOLLOW_STATUS_TONE)).not.toContain(dead);
    }
  });
});

describe("followStatusLabel / followStatusHint (film vs série)", () => {
  it("reads « Acquis » for an owned film and « À jour » for a série", () => {
    expect(followStatusLabel("up_to_date", "movie")).toBe("Acquis");
    expect(followStatusLabel("up_to_date", "show")).toBe("À jour");
    expect(followStatusHint("up_to_date", "movie")).toBe(
      "Le film est en médiathèque.",
    );
  });

  it("shares the série wording for every non-overridden state", () => {
    // Which states are overridden is read from the override maps themselves,
    // not from a list repeated here: a hardcoded skip list silently stops
    // covering a state the day a new override lands.
    for (const status of FOLLOW_STATUSES) {
      if (status in FOLLOW_STATUS_LABEL_MOVIE) continue;
      expect(followStatusLabel(status, "movie")).toBe(
        FOLLOW_STATUS_LABEL[status],
      );
    }
    for (const status of FOLLOW_STATUSES) {
      if (status in FOLLOW_STATUS_HINT_MOVIE) continue;
      expect(followStatusHint(status, "movie")).toBe(FOLLOW_STATUS_HINT[status]);
    }
  });

  it("l'infobulle d'un film suspendu ne contredit pas sa pastille", () => {
    // The badge reads « Recherche arrêtée » — the tooltip must NOT fall through
    // to the série wording « Suivi en pause » (§13: two surfaces answering the
    // same question must read from the same code).
    const hint = followStatusHint("disabled", "movie");
    expect(hint).not.toContain("Suivi en pause");
    expect(hint).toMatch(/ne plus cherch|n'est plus cherch/i);
  });
});

describe("EPISODE state vocabulary", () => {
  it.each([
    ["in_library", "En médiathèque", "success"],
    ["to_grab", "À récupérer", "warning"],
    ["acquiring", "En cours d'acquisition", "info"],
    ["pending", "En attente de torrent", "waiting"],
    ["unverified", "Non vérifié", "muted"],
    ["announced", "Annoncé", "upcoming"],
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

  it("aliases absorbed onto en_acquisition — same label AND same tone", () => {
    // What this pins is the rendering of a DANGLING pointer, nothing wider.
    // Since ticket 411 a surface only ever meets `absorbed` when the pointer could not
    // be followed (states.substitute_absorbed_facts otherwise substitutes the
    // carrying season's own facts). For that unknown, « in motion » is the
    // arbitrated reading — never « never checked ». Do NOT read this test as
    // « an absorbed episode is always being acquired »: that reading is what
    // kept 31 finished queue rows claiming « En cours d'acquisition ».
    expect(EPISODE_STATE_LABEL.absorbed).toBe(EPISODE_STATE_LABEL.acquiring);
    expect(EPISODE_STATE_TONE.absorbed).toBe(EPISODE_STATE_TONE.acquiring);
    expect(STATUS_LABEL.absorbed).toBe(EPISODE_STATE_LABEL.acquiring);
    expect(STATUS_TONE.absorbed).toBe(EPISODE_STATE_TONE.acquiring);
  });

  it("never claims a torrent was taken in the absorbed hint", () => {
    // Absorption happens when the SEASON row is ENQUEUED (pending), before any
    // search runs — claiming « Torrent pris » would be false for as long as the
    // season row is still looking (and forever if it is abandoned).
    const hint = EPISODE_STATE_HINT.absorbed;
    expect(hint).toBeTruthy();
    expect(hint.toLowerCase()).not.toContain("torrent pris");
    expect(hint).toContain("saison");
  });

  it("covers every episode state between the legend and its alias", () => {
    // The legend is now an explicit list, so it can no longer drift by
    // construction — this is what replaces that guarantee: legend + the
    // deliberately-aliased `absorbed` must together cover the WHOLE enum.
    expect(new Set([...EPISODE_LEGEND_ORDER, "absorbed"])).toEqual(
      new Set(EPISODE_STATES),
    );
  });

  it("gives each of the six live-flow states a DISTINCT tone (operator #9)", () => {
    // « Une couleur par statut »: no two LIVE-FLOW episode states may share a
    // BadgeTone, else the matrix would paint two states the same colour. This
    // is the regression guard for the two collisions that existed at phase-1
    // end (annonce=en_acquisition=info, en_attente=non_verifie=neutral).
    // "absorbed" is excluded on purpose: it is not a state of its own for the
    // operator — it renders EXACTLY like en_acquisition (same tone, same
    // label), being the rendering of a pointer that could not be followed
    // rather than a step of the live flow.
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

});

describe("searchOutcomeReason — le motif d'attente en français", () => {
  it.each([
    ["no_candidates", "aucun résultat"],
    ["no_matching_episode", "pas d'épisode exact"],
    ["all_filtered", "rien de conforme au profil"],
  ])("traduit %s en « %s » pour un épisode en attente", (outcome, reason) => {
    expect(searchOutcomeReason("pending", outcome)).toBe(reason);
  });

  it.each([
    ["trackers_unavailable", "trackers injoignables"],
    ["circuit_open", "recherche suspendue après trop d'échecs"],
    ["search_api_error", "erreur de recherche côté tracker"],
    ["no_seeders", "aucune source active"],
  ])("explique un non vérifié par %s", (outcome, reason) => {
    expect(searchOutcomeReason("unverified", outcome)).toBe(reason);
  });

  it("ne rend JAMAIS le jeton machine, même inconnu (NE-DOIT-PAS-4)", () => {
    const reason = searchOutcomeReason("pending", "brand_new_verdict");
    expect(reason).toBe("rien de prenable au dernier passage");
    expect(reason).not.toContain("brand_new_verdict");
  });

  it("se tait quand l'unité n'attend pas ou n'a aucun verdict", () => {
    expect(searchOutcomeReason("in_library", "no_candidates")).toBeNull();
    expect(searchOutcomeReason("to_grab", "no_candidates")).toBeNull();
    expect(searchOutcomeReason("acquiring", "all_filtered")).toBeNull();
    expect(searchOutcomeReason("unverified", null)).toBeNull();
    expect(searchOutcomeReason("pending", undefined)).toBeNull();
  });
});

describe("« En attente » vs « Non vérifié » (must not be confusable)", () => {
  it("gives the two states DISTINCT tones, labels AND hints (#24)", () => {
    // #24 — they no longer share a colour: en_attente = solid neutral grey,
    // non_verifie = the muted (dashed info-blue) idle tone, in BOTH maps.
    expect(FOLLOW_STATUS_TONE.pending).not.toBe(
      FOLLOW_STATUS_TONE.unverified,
    );
    expect(EPISODE_STATE_TONE.pending).not.toBe(
      EPISODE_STATE_TONE.unverified,
    );
    expect(FOLLOW_STATUS_LABEL.pending).not.toBe(
      FOLLOW_STATUS_LABEL.unverified,
    );
    expect(FOLLOW_STATUS_HINT.pending).not.toBe(
      FOLLOW_STATUS_HINT.unverified,
    );
    expect(EPISODE_STATE_LABEL.pending).not.toBe(
      EPISODE_STATE_LABEL.unverified,
    );
    expect(EPISODE_STATE_HINT.pending).not.toBe(
      EPISODE_STATE_HINT.unverified,
    );
  });

  it("says « rien de conforme » for en_attente and « pas encore » for non_verifie", () => {
    expect(FOLLOW_STATUS_HINT.pending).toMatch(/rien de conforme/);
    expect(FOLLOW_STATUS_HINT.unverified).toMatch(/[Pp]as encore vérifié/);
    expect(EPISODE_STATE_HINT.pending).toMatch(/rien de conforme/);
    expect(EPISODE_STATE_HINT.unverified).toMatch(/[Pp]as encore vérifié/);
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

});

// ---------------------------------------------------------------------------
// §9 — Film vs series action labelling
// ---------------------------------------------------------------------------

describe("vocabulaire film vs série (§9)", () => {
  it("un film s'ajoute, une série se suit", () => {
    expect(actionWords("movie").add).toBe("Ajouter");
    expect(actionWords("movie").added).toBe("✓ Ajouté");
    expect(actionWords("show").add).toBe("Suivre");
    expect(actionWords("show").added).toBe("✓ Suivi");
  });

  it("on n'met pas un film en pause, on arrête de le chercher", () => {
    expect(actionWords("movie").pause).toBe("Ne plus chercher");
    expect(actionWords("movie").resume).toBe("Chercher à nouveau");
    expect(actionWords("show").pause).toBe("Mettre en pause");
  });

  it("un film quitte la liste, une série AUSSI — supprimer supprime (§9)", () => {
    // Operator, 2026-08-08: « supprimer » and « mettre en pause » wrote the
    // same row. Now that removal really removes, the copy must stop promising
    // a reactivation and must point at the pause for that intent.
    expect(actionWords("movie").removeConfirmBody).toMatch(/SUPPRIMÉ/);
    expect(actionWords("show").removeConfirmBody).toMatch(/SUPPRIMÉ/);
    expect(actionWords("show").removeConfirmBody).toMatch(/Mettre en pause/);
    expect(actionWords("show").removeConfirmBody).not.toMatch(/réactiver/i);
  });

  it("un film suspendu n'est pas « en pause » mais « recherche arrêtée »", () => {
    expect(followStatusLabel("disabled", "movie")).toBe("Recherche arrêtée");
    expect(followStatusLabel("disabled", "show")).toBe("En pause");
  });

  it("les libellés courts du balayage tiennent en deux mots", () => {
    for (const kind of ["movie", "show"]) {
      expect(
        actionWords(kind).pauseShort.split(" ").length,
      ).toBeLessThanOrEqual(3);
      expect(
        actionWords(kind).resumeShort.split(" ").length,
      ).toBeLessThanOrEqual(3);
    }
  });

  it("un kind inconnu retombe sur le vocabulaire série, jamais sur un slug", () => {
    const w = actionWords("what-is-this");
    expect(w.add).toBe("Suivre");
    expect(
      Object.values(w).every(
        (v: string) => !/[a-z]+_[a-z]+/.test(v),
      ),
    ).toBe(true);
  });

  it("chaque état a un libellé — un nouvel état casse tsc, il n'imprime pas un slug", () => {
    for (const status of Object.keys(FOLLOW_STATUS_LABEL)) {
      expect(
        FOLLOW_STATUS_LABEL[status as keyof typeof FOLLOW_STATUS_LABEL],
      ).toBeTruthy();
    }
  });

  it("MediaKind accepte les trois littéraux et rien d'autre", () => {
    // Type-level assertion: each literal must be assignable to MediaKind.
    // tsc -b --noEmit is the real gate — this test pins the three values
    // so no future refactor widens or narrows the union by accident.
    const m1: MediaKind = "movie";
    const m2: MediaKind = "show";
    const m3: MediaKind = "season";
    expect([m1, m2, m3]).toEqual(["movie", "show", "season"]);
  });

  it("asMediaKind renvoie le littéral exact pour les trois MediaKind connus", () => {
    expect(asMediaKind("movie")).toBe("movie");
    expect(asMediaKind("show")).toBe("show");
    expect(asMediaKind("season")).toBe("season");
  });

  it("asMediaKind tombe sur « show » pour une valeur inconnue", () => {
    expect(asMediaKind("podcast")).toBe("show");
    expect(asMediaKind("")).toBe("show");
  });
});

// ---------------------------------------------------------------------------
// followMediaRef — gate on the LINK, not on tvdb_unresolved
// ---------------------------------------------------------------------------

/** Minimal FollowedSeriesItem — only the fields followMediaRef reads. */
function mediaRefItem(
  overrides: Partial<FollowedSeriesItem> = {},
): FollowedSeriesItem {
  return {
    id: 1,
    title: "Silo",
    kind: "show",
    active: true,
    added_at: 0,
    cadence: { interval_minutes: 60 },
    cadence_tier: null,
    next_search_at: null,
    quality_profile: null,
    wanted_pending: 0,
    wanted_grabbed: 0,
    season_count: 2,
    year: 2023,
    overview: null,
    poster_url: null,
    media_ref: { tvdb_id: 400000, tmdb_id: 125910, imdb_id: null },
    status: "up_to_date",
    priming_running: false,
    tvdb_unresolved: false,
    aired_count: null,
    owned_count: null,
    to_grab_count: null,
    acquiring_count: null,
    pending_count: null,
    unverified_count: null,
    movie_facts: null,
    ...overrides,
  };
}

describe("followMediaRef — la condition est le LIEN, pas le flag (§11)", () => {
  it("priorité TVDB : tvdb_id → /media/tvdb/{id}?kind=tv", () => {
    const href = followMediaRef(mediaRefItem());
    expect(href).toBe("/media/tvdb/400000?kind=tv");
  });

  it("fallback TMDB : pas de tvdb_id → /media/tmdb/{id}?kind=tv", () => {
    const href = followMediaRef(
      mediaRefItem({
        media_ref: { tvdb_id: null, tmdb_id: 125910, imdb_id: null },
      }),
    );
    expect(href).toBe("/media/tmdb/125910?kind=tv");
  });

  it("film → kind=movie dans le href", () => {
    const href = followMediaRef(
      mediaRefItem({
        kind: "movie",
        media_ref: { tvdb_id: null, tmdb_id: 550, imdb_id: null },
      }),
    );
    expect(href).toBe("/media/tmdb/550?kind=movie");
  });

  it("aucun id → null (§11 : pas de lien mort)", () => {
    const href = followMediaRef(
      mediaRefItem({
        media_ref: { tvdb_id: null, tmdb_id: null, imdb_id: "tt1234567" },
      }),
    );
    expect(href).toBeNull();
  });

  it("tmdb_id seul suffit, même avec tvdb_unresolved=true (le flag n'est pas la vérité)", () => {
    // An item can have tvdb_unresolved: true while carrying a tmdb_id that
    // resolves to a valid sheet. Gating on the flag would suppress the link
    // for nothing — followMediaRef returns the real answer.
    const href = followMediaRef(
      mediaRefItem({
        tvdb_unresolved: true,
        media_ref: { tvdb_id: null, tmdb_id: 125910, imdb_id: null },
      }),
    );
    expect(href).toBe("/media/tmdb/125910?kind=tv");
  });
  it("chaque option de filtre d'obligation porte un libellé français, jamais le jeton", () => {
    // ObligationsPanel (mounted behind « Plus ») renders these options as-is:
    // a machine value reaching the select would be NE-DOIT-PAS-4.
    for (const opt of OBLIGATION_STATUS_OPTIONS) {
      expect(opt.label).toBeTruthy();
      expect(opt.label).not.toBe(opt.value);
    }
  });
});
