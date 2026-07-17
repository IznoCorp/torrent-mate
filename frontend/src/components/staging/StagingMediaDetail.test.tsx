/**
 * Unit tests for StagingMediaDetail egress actions (phase 04, control-medias).
 *
 * DOIT-7 matrix: every state shows ≥1 action — assert the REAL implemented gating
 * conditions, labels, and menu structure from StagingMediaDetail.tsx.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StagingMediaItem } from "@/api/client";
import { StagingMediaDetail } from "@/components/staging/StagingMediaDetail";

// ---- mocks ----

const continueMutateMock = vi.fn();
const useContinueMediaMock = vi.fn();

vi.mock("@/hooks/useContinueMedia", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useContinueMedia: () => useContinueMediaMock(),
}));

const discardMutateMock = vi.fn();
const useDiscardMediaMock = vi.fn();

vi.mock("@/hooks/useDiscardMedia", () => ({
  // eslint-disable-next-line @typescript-eslint/no-unsafe-return
  useDiscardMedia: () => useDiscardMediaMock(),
}));

// ---- helpers ----

/** Build a minimal StagingMediaItem with sane defaults. */
function stagingItem(
  overrides: Partial<StagingMediaItem> = {},
): StagingMediaItem {
  return {
    id: "abc123",
    category: "001-MOVIES",
    folder: "Fight Club (1999)",
    relative_path: "001-MOVIES/Fight Club (1999)",
    media_kind: "movie",
    title: "Fight Club",
    year: 1999,
    overview: "An insomniac forms a club.",
    provider_ids: { tmdb: "550" },
    match: "matched",
    decision_id: null,
    decision_trigger: null,
    has_nfo: true,
    has_poster: true,
    has_trailer: true,
    poster_url: "/api/staging/media/abc123/poster",
    seasons: null,
    episode_count: null,
    video_count: 1,
    size_bytes: 1_600_000_000,
    modified_at: 1750000000,
    position_stage: "dispatch",
    position_state: "pending",
    stages: [
      { key: "arrival", label: "Arrivée", state: "done" },
      { key: "scraping", label: "Scraping", state: "done" },
      { key: "dispatch", label: "Dispatch", state: "pending" },
    ],
    dispatch_target: null,
    blocked_reason: null,
    ...overrides,
  };
}

/** Configure the useContinueMedia mock return value. */
function stubContinue(overrides: Record<string, unknown> = {}): void {
  useContinueMediaMock.mockReturnValue({
    mutate: continueMutateMock,
    isPending: false,
    isSuccess: false,
    data: undefined,
    ...overrides,
  });
}

/** Configure the useDiscardMedia mock return value. */
function stubDiscard(overrides: Record<string, unknown> = {}): void {
  useDiscardMediaMock.mockReturnValue({
    mutate: discardMutateMock,
    isPending: false,
    isSuccess: false,
    ...overrides,
  });
}

/** Render StagingMediaDetail inside a QueryClientProvider. */
function renderDetail(
  item: StagingMediaItem,
  onResolve?: (decisionId?: number) => void,
): void {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={qc}>
      <StagingMediaDetail
        item={item}
        {...(onResolve !== undefined ? { onResolve } : {})}
      />
    </QueryClientProvider>
  );
  render(tree);
}

// ---- setup / teardown ----

beforeEach(() => {
  stubContinue();
  stubDiscard();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("StagingMediaDetail egress actions", () => {
  // -----------------------------------------------------------------------
  // DOIT-7 item 1: matched + blocked_reason → « Relancer et terminer »
  // -----------------------------------------------------------------------

  describe("matched + blocked", () => {
    it("renders « Relancer et terminer le pipeline » button", () => {
      renderDetail(
        stagingItem({
          match: "matched",
          blocked_reason: "Épisodes non renommés (verify gate)",
        }),
      );
      expect(
        screen.getByRole("button", {
          name: "Relancer et terminer le pipeline",
        }),
      ).toBeInTheDocument();
    });

    it("shows the blocked_reason in an alert", () => {
      renderDetail(
        stagingItem({
          match: "matched",
          blocked_reason: "Épisodes non renommés (verify gate)",
        }),
      );
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Épisodes non renommés (verify gate)",
      );
    });

    it("disables the button and shows « Envoi… » while pending", () => {
      stubContinue({ isPending: true });
      renderDetail(
        stagingItem({
          match: "matched",
          blocked_reason: "Verify gate blocked",
        }),
      );
      const btn = screen.getByRole("button", { name: "Envoi…" });
      expect(btn).toBeDisabled();
    });

    it("calls continue mutate with the item id on click", () => {
      renderDetail(
        stagingItem({
          match: "matched",
          blocked_reason: "Test block",
        }),
      );
      fireEvent.click(
        screen.getByRole("button", {
          name: "Relancer et terminer le pipeline",
        }),
      );
      expect(continueMutateMock).toHaveBeenCalledWith(
        "abc123",
        expect.objectContaining({
          onSuccess: expect.any(Function) as () => void,
          onError: expect.any(Function) as () => void,
        }),
      );
    });
  });

  // -----------------------------------------------------------------------
  // DOIT-7 item 6: deferred continue → server detail string rendered
  // -----------------------------------------------------------------------

  it("renders the server detail string when the continue is deferred", () => {
    const deferredSentence =
      "En file — un autre run est en cours. Le pipeline reprendra automatiquement.";
    stubContinue({
      isSuccess: true,
      data: {
        deferred: true,
        detail: deferredSentence,
        ok: true,
        media_id: "abc123",
      },
    });
    renderDetail(
      stagingItem({
        match: "matched",
        blocked_reason: "Test block",
      }),
    );
    expect(screen.getByText(deferredSentence)).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // DOIT-7 item 2: matched + clean → secondary menu with « Re-scraper »
  // -----------------------------------------------------------------------

  describe("matched + clean", () => {
    it("does NOT render the primary « Relancer » button", () => {
      renderDetail(stagingItem({ match: "matched", blocked_reason: null }));
      expect(
        screen.queryByRole("button", {
          name: "Relancer et terminer le pipeline",
        }),
      ).not.toBeInTheDocument();
    });

    it("shows the secondary actions trigger (MoreHorizontal)", () => {
      renderDetail(stagingItem({ match: "matched", blocked_reason: null }));
      // The trigger wraps a MoreHorizontal icon with an sr-only "Actions" span.
      expect(
        screen.getByRole("button", { name: "Actions" }),
      ).toBeInTheDocument();
    });

    it("opens the DropdownMenu to reveal « Re-scraper cet élément »", async () => {
      renderDetail(stagingItem({ match: "matched", blocked_reason: null }));
      // Radix DropdownMenuTrigger listens for pointerdown, not click.
      fireEvent.pointerDown(
        screen.getByRole("button", { name: "Actions" }),
        { button: 0, pointerType: "mouse" },
      );
      await waitFor(() => {
        expect(
          screen.getByRole("menuitem", {
            name: "Re-scraper cet élément",
          }),
        ).toBeInTheDocument();
      });
    });

    it("« Re-scraper cet élément » calls continue mutate on select", async () => {
      renderDetail(stagingItem({ match: "matched", blocked_reason: null }));
      // Open the dropdown via pointerdown (Radix Trigger convention).
      fireEvent.pointerDown(
        screen.getByRole("button", { name: "Actions" }),
        { button: 0, pointerType: "mouse" },
      );
      await waitFor(() => {
        expect(
          screen.getByRole("menuitem", {
            name: "Re-scraper cet élément",
          }),
        ).toBeInTheDocument();
      });
      // Selecting the menu item fires the Radix onSelect → our mutate call.
      fireEvent.click(
        screen.getByRole("menuitem", {
          name: "Re-scraper cet élément",
        }),
      );
      expect(continueMutateMock).toHaveBeenCalledWith(
        "abc123",
        expect.objectContaining({
          onSuccess: expect.any(Function) as () => void,
          onError: expect.any(Function) as () => void,
        }),
      );
    });

    it("treats empty-string blocked_reason as clean (secondary menu)", () => {
      // Empty string yields the same gating as null — the component checks
      // blocked_reason == null || blocked_reason === "".
      renderDetail(stagingItem({ match: "matched", blocked_reason: "" }));
      expect(
        screen.getByRole("button", { name: "Actions" }),
      ).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // DOIT-7 item 3: ambiguous → « Résoudre le matching »
  // -----------------------------------------------------------------------

  describe("ambiguous", () => {
    it("renders « Résoudre le matching » when onResolve is provided", () => {
      renderDetail(
        stagingItem({ match: "ambiguous", decision_id: 42 }),
        vi.fn(),
      );
      expect(
        screen.getByRole("button", { name: "Résoudre le matching" }),
      ).toBeInTheDocument();
    });

    it("calls onResolve with the decision_id on click", () => {
      const onResolve = vi.fn();
      renderDetail(
        stagingItem({ match: "ambiguous", decision_id: 42 }),
        onResolve,
      );
      fireEvent.click(
        screen.getByRole("button", { name: "Résoudre le matching" }),
      );
      expect(onResolve).toHaveBeenCalledWith(42);
    });

    it("does NOT render « Résoudre le matching » when onResolve is absent", () => {
      // The gating is: match === "ambiguous" && onResolve !== undefined.
      renderDetail(stagingItem({ match: "ambiguous", decision_id: 42 }));
      expect(
        screen.queryByRole("button", { name: "Résoudre le matching" }),
      ).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // DOIT-7 item 4: absent (kind known) → « Rechercher / résoudre manuellement »
  // -----------------------------------------------------------------------

  describe("absent with known kind", () => {
    it("renders « Rechercher / résoudre manuellement » for absent movie", () => {
      renderDetail(
        stagingItem({ match: "absent", media_kind: "movie", has_nfo: false }),
      );
      expect(
        screen.getByRole("button", {
          name: "Rechercher / résoudre manuellement",
        }),
      ).toBeInTheDocument();
    });

    it("renders « Rechercher / résoudre manuellement » for absent tvshow", () => {
      renderDetail(
        stagingItem({ match: "absent", media_kind: "tvshow", has_nfo: false }),
      );
      expect(
        screen.getByRole("button", {
          name: "Rechercher / résoudre manuellement",
        }),
      ).toBeInTheDocument();
    });

    it("does NOT show the Film/Série chooser for a known kind", () => {
      renderDetail(
        stagingItem({ match: "absent", media_kind: "movie", has_nfo: false }),
      );
      expect(
        screen.queryByRole("button", { name: "Film" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Série" }),
      ).not.toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // DOIT-7 item 5: other/needsKind → Film/Série chooser + « Ignorer / nettoyer »
  // -----------------------------------------------------------------------

  describe("other (needsKind)", () => {
    it("renders the Film/Série chooser", () => {
      renderDetail(
        stagingItem({
          match: "absent",
          media_kind: "other",
          has_nfo: false,
        }),
      );
      expect(screen.getByRole("button", { name: "Film" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Série" })).toBeInTheDocument();
    });

    it("renders « Ignorer / nettoyer » for other items", () => {
      renderDetail(
        stagingItem({
          match: "absent",
          media_kind: "other",
          has_nfo: false,
        }),
      );
      expect(
        screen.getByRole("button", { name: "Ignorer / nettoyer" }),
      ).toBeInTheDocument();
    });

    it("disables « Rechercher / résoudre manuellement » until a kind is chosen", () => {
      renderDetail(
        stagingItem({
          match: "absent",
          media_kind: "other",
          has_nfo: false,
        }),
      );
      expect(
        screen.getByRole("button", {
          name: "Rechercher / résoudre manuellement",
        }),
      ).toBeDisabled();
    });

    it("enables the button after choosing Film", () => {
      renderDetail(
        stagingItem({
          match: "absent",
          media_kind: "other",
          has_nfo: false,
        }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Film" }));
      expect(
        screen.getByRole("button", {
          name: "Rechercher / résoudre manuellement",
        }),
      ).not.toBeDisabled();
    });

    it("enables the button after choosing Série", () => {
      renderDetail(
        stagingItem({
          match: "absent",
          media_kind: "other",
          has_nfo: false,
        }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Série" }));
      expect(
        screen.getByRole("button", {
          name: "Rechercher / résoudre manuellement",
        }),
      ).not.toBeDisabled();
    });
  });

  // -----------------------------------------------------------------------
  // Negative: non-other items do NOT leak the « Ignorer / nettoyer » button
  // -----------------------------------------------------------------------

  it("does NOT render « Ignorer / nettoyer » for non-other items", () => {
    renderDetail(stagingItem({ match: "matched", media_kind: "movie" }));
    expect(
      screen.queryByRole("button", { name: "Ignorer / nettoyer" }),
    ).not.toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // « Ignorer / nettoyer » opens the confirmation dialog
  // -----------------------------------------------------------------------

  it("clicking « Ignorer / nettoyer » opens the confirmation dialog", () => {
    renderDetail(
      stagingItem({
        match: "absent",
        media_kind: "other",
        has_nfo: false,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Ignorer / nettoyer" }));
    expect(screen.getByText("Ignorer cet élément ?")).toBeInTheDocument();
    expect(
      screen.getByText(/Ce dossier ne contient pas un média identifiable/),
    ).toBeInTheDocument();
  });
});
