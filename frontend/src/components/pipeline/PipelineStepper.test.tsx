import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PipelineStepper } from "@/components/pipeline/PipelineStepper";
import type { components } from "@/api/schema";

type StepTiming = components["schemas"]["StepTiming"];

afterEach(cleanup);

describe("PipelineStepper", () => {
  describe("mode LIVE (currentStep)", () => {
    it("affiche les 9 étapes avec les labels français", () => {
      render(<PipelineStepper currentStep="scrape" />);

      expect(screen.getByText("Collecte")).toBeInTheDocument();
      expect(screen.getByText("Tri")).toBeInTheDocument();
      expect(screen.getByText("Nettoyage")).toBeInTheDocument();
      expect(screen.getByText("Scraping")).toBeInTheDocument();
      expect(screen.getByText("Nettoyage final")).toBeInTheDocument();
      expect(screen.getByText("Conformité")).toBeInTheDocument();
      expect(screen.getByText("Vérification")).toBeInTheDocument();
      expect(screen.getByText("Bandes-annonces")).toBeInTheDocument();
      expect(screen.getByText("Dispatch")).toBeInTheDocument();
    });

    it("marque l'étape courante comme running et les précédentes comme done", () => {
      render(<PipelineStepper currentStep="scrape" />);

      // The stepper renders each step as a listitem with its status class.
      const steps = screen.getAllByRole("listitem");

      // Step indices: 0=ingest, 1=sort, 2=clean, 3=scrape, ...
      // Before scrape (0-2): done
      expect(steps[0]).toHaveClass("ps-step--done");
      expect(steps[1]).toHaveClass("ps-step--done");
      expect(steps[2]).toHaveClass("ps-step--done");
      // Current (3): running
      expect(steps[3]).toHaveClass("ps-step--running");
      // After scrape (4-8): queued
      expect(steps[4]).toHaveClass("ps-step--queued");
      expect(steps[5]).toHaveClass("ps-step--queued");
    });

    it("met toutes les étapes en queued quand currentStep est absent (pipeline idle)", () => {
      render(<PipelineStepper />);

      const steps = screen.getAllByRole("listitem");
      for (const step of steps) {
        expect(step).toHaveClass("ps-step--queued");
      }
    });

    it("met toutes les étapes en queued avec currentStep=null", () => {
      render(<PipelineStepper currentStep={null} />);

      const steps = screen.getAllByRole("listitem");
      for (const step of steps) {
        expect(step).toHaveClass("ps-step--queued");
      }
    });

    it("marque la dernière étape comme running quand currentStep est dispatch", () => {
      render(<PipelineStepper currentStep="dispatch" />);

      const steps = screen.getAllByRole("listitem");
      // All 8 before dispatch → done
      for (let i = 0; i < 8; i++) {
        expect(steps[i]).toHaveClass("ps-step--done");
      }
      // dispatch (index 8) → running
      expect(steps[8]).toHaveClass("ps-step--running");
    });

    it("gère un currentStep inconnu en mettant tout en queued", () => {
      render(<PipelineStepper currentStep="unknown_step" />);

      const steps = screen.getAllByRole("listitem");
      for (const step of steps) {
        expect(step).toHaveClass("ps-step--queued");
      }
    });
  });

  describe("mode READ-ONLY (steps)", () => {
    function makeStep(
      name: string,
      status: string,
      elapsed_s?: number | null,
    ): StepTiming {
      return {
        name,
        status,
        elapsed_s: elapsed_s ?? null,
        started_at: null,
        ended_at: null,
      };
    }

    it("affiche les statuts fournis par l'API", () => {
      const steps: StepTiming[] = [
        makeStep("ingest", "done", 2.3),
        makeStep("sort", "done", 1.1),
        makeStep("clean", "running"),
        makeStep("scrape", "pending"),
        makeStep("cleanup", "pending"),
        makeStep("enforce", "pending"),
        makeStep("verify", "pending"),
        makeStep("trailers", "pending"),
        makeStep("dispatch", "pending"),
      ];

      render(<PipelineStepper steps={steps} />);

      const items = screen.getAllByRole("listitem");
      expect(items[0]).toHaveClass("ps-step--done");
      expect(items[1]).toHaveClass("ps-step--done");
      expect(items[2]).toHaveClass("ps-step--running");
      expect(items[3]).toHaveClass("ps-step--queued");
    });

    it("affiche le temps écoulé quand elapsed_s est fourni", () => {
      const steps: StepTiming[] = [
        makeStep("ingest", "done", 2.3),
        makeStep("sort", "done", 65.7),
        makeStep("clean", "done", 0.5),
      ];

      render(<PipelineStepper steps={steps} />);

      expect(screen.getByText("2.3s")).toBeInTheDocument();
      expect(screen.getByText("1m 05s")).toBeInTheDocument();
      expect(screen.getByText("0.5s")).toBeInTheDocument();
    });

    it("complète les étapes manquantes avec le statut idle", () => {
      // Only 3 of 9 steps provided — the rest should be padded as idle.
      const steps: StepTiming[] = [
        makeStep("ingest", "done", 1.0),
        makeStep("sort", "done", 0.5),
      ];

      render(<PipelineStepper steps={steps} />);

      const items = screen.getAllByRole("listitem");
      expect(items).toHaveLength(9);
      // The padded steps (clean..dispatch) should be idle.
      expect(items[2]).toHaveClass("ps-step--idle");
      expect(items[8]).toHaveClass("ps-step--idle");
    });

    it("affiche le statut error correctement", () => {
      const steps: StepTiming[] = [
        makeStep("ingest", "done", 1.0),
        makeStep("sort", "error", 0.3),
      ];

      render(<PipelineStepper steps={steps} />);

      const items = screen.getAllByRole("listitem");
      expect(items[1]).toHaveClass("ps-step--error");
    });

    it("affiche le statut skipped correctement", () => {
      const steps: StepTiming[] = [
        makeStep("ingest", "done", 1.0),
        makeStep("sort", "done", 0.5),
        makeStep("clean", "skipped"),
      ];

      render(<PipelineStepper steps={steps} />);

      const items = screen.getAllByRole("listitem");
      expect(items[2]).toHaveClass("ps-step--skipped");
    });
  });

  it("porte l'attribut role=list et un aria-label", () => {
    render(<PipelineStepper currentStep="ingest" />);

    const list = screen.getByRole("list");
    expect(list).toHaveAttribute("aria-label", "Étapes du pipeline");
  });
});
