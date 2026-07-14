import { describe, expect, it } from "vitest";

import type { EventMessage } from "@/api/events";
import {
  interpretRun,
  type InterpretedLine,
} from "@/components/pipeline/interpretRun";

/** Build an EventMessage with an incrementing id. */
function ev(
  type: string,
  data: Record<string, unknown>,
  id = "1-0",
): EventMessage {
  return { id, type, data };
}

describe("interpretRun", () => {
  it("returns no lines for an empty stream", () => {
    expect(interpretRun([])).toEqual([]);
  });

  it("emits a step header for StepStarted and ignores the started item events", () => {
    const lines = interpretRun([
      ev("StepStarted", { step: "ingest" }),
      ev("ItemProgressed", { step: "ingest", item: "Foo.mkv", status: "started" }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      { step: "ingest", text: "Récupération des téléchargements…", tone: "info" },
    ]);
  });

  it("folds a full happy-path run into ordered French lines (golden)", () => {
    const events: EventMessage[] = [
      ev("StepStarted", { step: "ingest" }),
      ev("ItemProgressed", {
        step: "ingest",
        item: "The.Movie.2024.1080p",
        status: "copied",
        details: { action: "copied", dest: "/staging/097-TEMP/The.Movie.2024.1080p" },
      }),
      ev("StepStarted", { step: "sort" }),
      ev("ItemProgressed", {
        step: "sort",
        item: "The.Movie.2024.1080p",
        status: "moved",
        details: { destination: "/staging/001-MOVIES/The.Movie.2024.1080p" },
      }),
      ev("StepStarted", { step: "clean" }),
      // The backend emits status "cleaned"/"skipped"/"error" for a clean step —
      // never "recleaned" (that is only a structlog detail key). Use the real
      // vocab so this golden covers the actual code path.
      ev("ItemProgressed", { step: "clean", item: "001-MOVIES", status: "cleaned" }),
      ev("StepStarted", { step: "scrape" }),
      ev("ItemProgressed", {
        step: "scrape",
        item: "The.Movie.2024.1080p",
        status: "matched",
        details: { action: "created", provider: "tmdb" },
      }),
      ev("StepStarted", { step: "trailers" }),
      ev("ItemProgressed", {
        step: "trailers",
        item: "The Movie (2024)",
        status: "downloaded",
        details: { reason: "downloaded" },
      }),
      ev("StepStarted", { step: "dispatch" }),
      ev("ItemProgressed", {
        step: "dispatch",
        item: "The Movie (2024)",
        status: "moved",
        details: { dest: "/Volumes/Disk2/001-MOVIES/The Movie (2024)", disk: "Disk2" },
      }),
    ];

    expect(interpretRun(events)).toEqual<InterpretedLine[]>([
      { step: "ingest", text: "Récupération des téléchargements…", tone: "info" },
      {
        step: "ingest",
        text: "Nouveau téléchargement collecté : The.Movie.2024.1080p vers The.Movie.2024.1080p",
        tone: "success",
      },
      { step: "sort", text: "Tri vers la zone de préparation…", tone: "info" },
      {
        step: "sort",
        text: "Déplacé en préparation : The.Movie.2024.1080p → The.Movie.2024.1080p",
        tone: "success",
      },
      { step: "clean", text: "Nettoyage des fichiers parasites…", tone: "info" },
      { step: "clean", text: "Nettoyé : 001-MOVIES", tone: "success" },
      { step: "scrape", text: "Recherche des métadonnées…", tone: "info" },
      {
        step: "scrape",
        text: "Métadonnées trouvées : The.Movie.2024.1080p (tmdb)",
        tone: "success",
      },
      { step: "trailers", text: "Bandes-annonces…", tone: "info" },
      {
        step: "trailers",
        text: "Bande-annonce téléchargée : The Movie (2024)",
        tone: "success",
      },
      { step: "dispatch", text: "Rangement vers le stockage…", tone: "info" },
      {
        step: "dispatch",
        text: "Rangé sur Disk2 : The Movie (2024)",
        tone: "success",
      },
    ]);
  });

  it("narrates an ambiguous scrape awaiting a decision as a warning line", () => {
    const lines = interpretRun([
      ev("ItemProgressed", {
        step: "scrape",
        item: "Unknown.Show.S01",
        status: "queued_for_decision",
        details: { trigger: "ambiguous", confidence: 0.42 },
      }),
      ev("ItemProgressed", {
        step: "scrape",
        item: "Blurry.Movie",
        status: "skipped_low_confidence",
        details: { provider: "tmdb", confidence: 0.31 },
      }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      {
        step: "scrape",
        text: "Ambigu — en attente d'une décision : Unknown.Show.S01",
        tone: "warning",
      },
      {
        step: "scrape",
        text: "Correspondance trop incertaine, laissé de côté : Blurry.Movie",
        tone: "warning",
      },
    ]);
  });

  it("narrates dispatch merge/replace and trailer-unavailable cases", () => {
    const lines = interpretRun([
      ev("ItemProgressed", {
        step: "dispatch",
        item: "Some Show (2020)",
        status: "merged",
        details: { dest: "/Volumes/Disk1/002-TVSHOWS/Some Show (2020)", disk: "Disk1" },
      }),
      ev("ItemProgressed", {
        step: "dispatch",
        item: "Old Movie (1999)",
        status: "replaced",
        details: { dest: "", disk: "Disk3" },
      }),
      ev("ItemProgressed", {
        step: "trailers",
        item: "Rare Film (1975)",
        status: "no_trailer",
        details: { reason: "no_trailer" },
      }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      { step: "dispatch", text: "Fusionné sur Disk1 : Some Show (2020)", tone: "success" },
      { step: "dispatch", text: "Remplacé sur Disk3 : Old Movie (1999)", tone: "success" },
      {
        step: "trailers",
        text: "Aucune bande-annonce disponible : Rare Film (1975)",
        tone: "info",
      },
    ]);
  });

  it("narrates a step error line", () => {
    const lines = interpretRun([
      ev("StepErrored", {
        step: "scrape",
        error_class: "TimeoutError",
        error_message: "TMDB timeout",
      }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      {
        step: "scrape",
        text: "Recherche des métadonnées — échec de l'étape : TMDB timeout",
        tone: "danger",
      },
    ]);
  });

  it("narrates artwork-only recovery as a distinct 'Posters récupérés' line (§2)", () => {
    // The backend emits status='matched' for BOTH a fresh scrape and an
    // artwork-only recovery; details.action distinguishes them. §2 lists
    // "posters récupérés" as its own visible state — it must not fold into
    // "Métadonnées trouvées".
    const lines = interpretRun([
      ev("ItemProgressed", {
        step: "scrape",
        item: "Fight Club (1999)",
        status: "matched",
        details: { action: "artwork_recovered", provider: "tmdb" },
      }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      { step: "scrape", text: "Posters récupérés : Fight Club (1999) (tmdb)", tone: "success" },
    ]);
  });

  it("ignores unknown event types and unknown step/status (no throw)", () => {
    const lines = interpretRun([
      ev("PipelineStarted", { report: {} }),
      ev("StepCompleted", { step: "ingest", report: {}, elapsed_s: 1.2 }),
      ev("ItemProgressed", { step: "unknownstep", item: "x", status: "weird" }),
      ev("ItemProgressed", { step: "scrape", item: "x", status: "brand_new_status" }),
      ev("SomeFutureEvent", { foo: "bar" }),
    ]);
    expect(lines).toEqual([]);
  });

  it("tolerates a Pipeline-prefixed event type", () => {
    const lines = interpretRun([
      ev("PipelineStepStarted", { step: "dispatch" }),
    ]);
    expect(lines).toEqual<InterpretedLine[]>([
      { step: "dispatch", text: "Rangement vers le stockage…", tone: "info" },
    ]);
  });
});
