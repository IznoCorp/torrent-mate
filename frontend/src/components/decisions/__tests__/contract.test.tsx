/**
 * R57 in the app — what a decision IS, checked where the prototype cannot run.
 *
 * `frontend/maquette/harness/decision.py` states the rule against the drawing;
 * this states the same rule against the code, so the two cannot drift apart
 * silently. Every check here mirrors one of its checks:
 *
 *   · the subject is the FOLDER, in the mono face — the extracted title is the
 *     one thing that cannot be trusted on this screen;
 *   · a decision is not a medium: no bottom panel, no poster link;
 *   · the score is printed only when it SEPARATES;
 *   · the engine's own words never reach a screen.
 */
import type { DecisionCandidate } from "@/api/decisions";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { decisionFacts, folderName } from "@/components/decisions/decisionFacts";
import { tiedLeaders, tieNotice } from "@/components/decisions/tie";
import { CandidateCard } from "@/components/decisions/CandidateCard";
import { DecisionRow } from "@/components/ds/DecisionRow";

/** The engine's vocabulary. None of it may reach a screen. */
const FRENCH_TOKENS = [
  "below_threshold",
  "mid_band",
  "ambiguous",
  "search_override",
  "staging_path",
  "dismissed",
  "superseded",
];

/** One real row, shaped as the API returns it. */
const REGLEE = {
  staging_path: "/Volumes/disk/A TRIER/002-TVSHOWS/Lucky",
  media_kind: "tvshow",
  trigger: "ambiguous",
  status: "resolved",
  resolved_at: 1_752_591_300,
  resolution_json: {
    provider: "tvdb",
    provider_id: 457437,
    via: "pick",
    title: "Lucky (2026)",
  },
};

/** The five candidates TVDB really returned for that folder — four of them tied. */
const CANDIDATS = [
  { provider: "tvdb" as const, provider_id: 427619, title: "Lucky!", year: 2022, score: 1, poster_url: null, overview: "…" },
  { provider: "tvdb" as const, provider_id: 457437, title: "Lucky (2026)", year: 2026, score: 1, poster_url: null, overview: "…" },
  { provider: "tvdb" as const, provider_id: 317944, title: "Lucky (2006)", year: 2006, score: 1, poster_url: null, overview: "…" },
  { provider: "tvdb" as const, provider_id: 70876, title: "Lucky (2003)", year: 2003, score: 1, poster_url: null, overview: "…" },
  { provider: "tvdb" as const, provider_id: 298989, title: "Lucky Chances", year: 1990, score: 0.9, poster_url: null, overview: "…" },
] as const satisfies readonly DecisionCandidate[];

describe("R57 — une décision est un DOSSIER", () => {
  afterEach(cleanup);

  it("le dossier est le sujet, en chasse fixe, jamais le titre extrait", () => {
    render(<DecisionRow {...decisionFacts(REGLEE)} />);
    const folder = screen.getByTestId("decision-folder");
    expect(folder).toHaveTextContent("Lucky");
    expect(folder.className).toContain("font-mono");
    // The full path is the tooltip; the row shows the folder.
    expect(folder).toHaveAttribute("title", REGLEE.staging_path);
    expect(folderName(REGLEE.staging_path)).toBe("Lucky");
  });

  it("ne promet ni fiche ni panneau", () => {
    render(<DecisionRow {...decisionFacts(REGLEE)} />);
    const card = screen.getByTestId("decision-card");
    expect(card).toHaveAttribute("data-nonmedia", "decision");
    expect(within(card).queryByRole("link")).toBeNull();
    // The poster is never a control: there is no medium here, only a folder.
    expect(card.querySelector("button > img, button [data-slot=poster]")).toBeNull();
  });

  it("dit son motif ET ce qu'elle est devenue, en français", () => {
    render(<DecisionRow {...decisionFacts(REGLEE)} />);
    expect(screen.getByText("Candidats ambigus")).toBeInTheDocument();
    expect(screen.getByText("Réglée")).toBeInTheDocument();
    expect(screen.getByText(/TVDB 457437 · choisi dans la liste/)).toBeInTheDocument();
  });

  it("aucun jeton du moteur n'atteint l'écran", () => {
    const { container } = render(<DecisionRow {...decisionFacts(REGLEE)} />);
    const text = container.textContent;
    const attributes = container.innerHTML;
    for (const token of FRENCH_TOKENS) {
      expect(text).not.toContain(token);
      expect(attributes).not.toContain(`>${token}<`);
    }
  });

  it("une décision en attente ne montre aucune affiche devinée", () => {
    const attente = { ...REGLEE, status: "pending", resolution_json: null };
    render(<DecisionRow {...decisionFacts(attente)} />);
    const card = screen.getByTestId("decision-card");
    expect(card.querySelector("img")).toBeNull();
    expect(screen.queryByText("Réglée")).toBeNull();
  });
});

describe("R57 — le score ne s'affiche que s'il sépare", () => {
  afterEach(cleanup);

  it("marque les meneurs à égalité, et eux seuls", () => {
    expect(tiedLeaders(CANDIDATS)).toEqual([true, true, true, true, false]);
    expect(tieNotice(CANDIDATS)).toContain("ne tranche pas");
  });

  it("un meneur SEUL garde son score", () => {
    const seul = [{ score: 1 }, { score: 0.9 }, { score: 0.5 }];
    expect(tiedLeaders(seul)).toEqual([false, false, false]);
    expect(tieNotice(seul)).toBeNull();
  });

  it("une carte à égalité n'affiche pas de pourcentage", () => {
    render(
      <CandidateCard candidate={CANDIDATS[0]} isSelected={false} tied onClick={vi.fn()} />,
    );
    expect(screen.queryByText(/%/)).toBeNull();
    expect(screen.getByText(/le score ne tranche pas/i)).toBeInTheDocument();
  });

  it("une carte qui se détache affiche le sien", () => {
    render(
      <CandidateCard candidate={CANDIDATS[4]} isSelected={false} onClick={vi.fn()} />,
    );
    // 90 also appears in the candidate's year (1990), so the assertion names
    // the percentage itself.
    expect(screen.getByText(/90\s*%/)).toBeInTheDocument();
  });

  it("aucun candidat n'invite à quitter l'écran pour décider", () => {
    const { container } = render(
      <CandidateCard candidate={CANDIDATS[0]} isSelected={false} onClick={vi.fn()} />,
    );
    expect(container.querySelector("a")).toBeNull();
  });
});
