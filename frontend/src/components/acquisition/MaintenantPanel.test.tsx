/**
 * MaintenantPanel — five-section composition of the « Maintenant » view.
 *
 * The first ASSEMBLY task (T8). Every building block was shipped in an earlier
 * task — this test verifies composition, not re-derivation of component internals.
 *
 * Section order is a CONSTANT, not a rendering accident — what is stopped and
 * waiting on the operator comes BEFORE what advances alone (§3.1).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  AcquisitionDownload,
  FollowedSeriesItem,
  ToHandleItem,
  ToHandleResponse,
  WantedItem,
} from "@/api/acquisition";

import { MaintenantPanel } from "./MaintenantPanel";
import * as hooks from "@/hooks/useAcquisition";

// ── Fixture type ───────────────────────────────────────────────────────────

interface FullFixtures {
  readonly followed: readonly FollowedSeriesItem[];
  readonly wanted: readonly WantedItem[];
  readonly toHandle: ToHandleResponse;
  readonly downloads: readonly AcquisitionDownload[];
}

interface EmptyFixtures {
  readonly followed: readonly FollowedSeriesItem[];
  readonly wanted: readonly WantedItem[];
  readonly toHandle: ToHandleResponse;
  readonly downloads: readonly AcquisitionDownload[];
}

// ── Shared helper values ───────────────────────────────────────────────────

const EMPTY_FOLLOWED: readonly FollowedSeriesItem[] = [];
const EMPTY_WANTED: readonly WantedItem[] = [];
const EMPTY_TO_HANDLE: ToHandleResponse = { items: [], orphan_count: 0 };
const EMPTY_DOWNLOADS: readonly AcquisitionDownload[] = [];

// ── Full fixture — populates all five sections ──────────────────────────────

/** A followed item with ``a_recuperer`` — lands in « À récupérer ». */
function takeableShow(): FollowedSeriesItem {
  return {
    id: 1,
    title: "Silo",
    kind: "show",
    status: "a_recuperer",
    active: true,
    added_at: 1_750_000_000,
    wanted_pending: 3,
    wanted_grabbed: 0,
    year: 2023,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 400000, tmdb_id: 125910, imdb_id: null },
  };
}

/** A blocked decision item — lands in « À traiter ». */
function blockedItem(): ToHandleItem {
  return {
    decision_id: 42,
    title: "The Last of Us",
    reason: "titre ambigu — 3 candidats proposés",
    stage: "scrape",
    kind: "show",
    candidates_count: 3,
    created_at: 1_749_000_000,
    year: 2023,
    followed_id: 7,
    info_hash: null,
  };
}

/** A grabbed wanted item — lands in « En vol ». */
function inflightWanted(): WantedItem {
  return {
    id: 101,
    title: "Severance",
    kind: "show",
    status: "grabbed",
    season: 3,
    episode: null,
    attempts: 2,
    enqueued_at: 1_749_900_000,
    last_search_at: 1_749_800_000,
  };
}

/** A download matching the inflight wanted item — gives the strip its stage. */
function inflightDownload(): AcquisitionDownload {
  return {
    info_hash: "abc123def4567890",
    name: "Severance S03 COMPLETE",
    title: "Severance",
    kind: "show",
    state: "downloading" as const,
    progress: 42,
    size_bytes: 8_000_000_000,
    media_ref: { tvdb_id: 371980, tmdb_id: 95396, imdb_id: null },
    season: 3,
    episode: null,
    error_reason: null,
  };
}

/** A followed item with ``en_attente`` — lands in « Cherché, rien trouvé ». */
function waitingShow(): FollowedSeriesItem {
  return {
    id: 2,
    title: "From",
    kind: "show",
    status: "en_attente",
    active: true,
    added_at: 1_745_000_000,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2022,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 411000, tmdb_id: 123456, imdb_id: null },
  };
}

/** A followed item with ``a_jour`` — lands in « Rangé aujourd'hui ». */
function upToDateShow(): FollowedSeriesItem {
  return {
    id: 3,
    title: "Shōgun",
    kind: "show",
    status: "a_jour",
    active: true,
    added_at: 1_740_000_000,
    owned_count: 10,
    aired_count: 10,
    wanted_pending: 0,
    wanted_grabbed: 0,
    year: 2024,
    poster_url: null,
    tvdb_unresolved: false,
    priming_running: false,
    media_ref: { tvdb_id: 421000, tmdb_id: 234567, imdb_id: null },
  };
}

const full: FullFixtures = {
  followed: [takeableShow(), waitingShow(), upToDateShow()],
  wanted: [inflightWanted()],
  toHandle: { items: [blockedItem()], orphan_count: 0 },
  downloads: [inflightDownload()],
};

const empty: EmptyFixtures = {
  followed: EMPTY_FOLLOWED,
  wanted: EMPTY_WANTED,
  toHandle: EMPTY_TO_HANDLE,
  downloads: EMPTY_DOWNLOADS,
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function mockHooks(f: FullFixtures | EmptyFixtures): void {
  // `useFollowed` — returns the followed items.
  vi.spyOn(hooks, "useFollowed").mockReturnValue({
    data: { items: [...f.followed] },
    isLoading: false,
    isError: false,
  } as ReturnType<typeof hooks.useFollowed>);

  // `useWanted` — returns the wanted items (status=grabbed for « En vol »).
  vi.spyOn(hooks, "useWanted").mockReturnValue({
    data: {
      items: [...f.wanted],
      total: f.wanted.length,
      page: 1,
      page_size: 50,
    },
    isLoading: false,
    isError: false,
  } as ReturnType<typeof hooks.useWanted>);

  // `useToHandle` — returns blocked items + orphan count.
  vi.spyOn(hooks, "useToHandle").mockReturnValue({
    data: { ...f.toHandle },
    isLoading: false,
    isError: false,
  } as ReturnType<typeof hooks.useToHandle>);

  // `useDownloads` — returns live download progress.
  vi.spyOn(hooks, "useDownloads").mockReturnValue({
    data: { downloads: [...f.downloads], client_available: true },
    isLoading: false,
    isError: false,
  } as ReturnType<typeof hooks.useDownloads>);
}

function renderPanel(f: FullFixtures | EmptyFixtures): void {
  mockHooks(f);
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <MaintenantPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// ── Tests ───────────────────────────────────────────────────────────────────

describe("MaintenantPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("ordonne les sections par ce qui attend l'opérateur d'abord", async () => {
    renderPanel(full);
    const heads = await screen.findAllByTestId("section-head");
    expect(heads.map((h) => h.textContent)).toEqual([
      expect.stringContaining("À récupérer"),
      expect.stringContaining("À traiter"),
      expect.stringContaining("En vol"),
      expect.stringContaining("Cherché, rien trouvé"),
      expect.stringContaining("Rangé aujourd'hui"),
    ]);
  });

  it("la frise n'apparaît QUE sur « en vol » et « à traiter » (A5)", async () => {
    renderPanel(full);

    // « À récupérer » — card exists but NO journey strip inside it.
    const takeableSection = await screen.findByTestId("section-a-recuperer");
    const takeableCard = within(takeableSection).queryByTestId("acq-card");
    expect(takeableCard).toBeInTheDocument();
    expect(takeableCard?.querySelector("[data-station]")).toBeNull();

    // « En vol » — card HAS a journey strip.
    const inflightSection = screen.getByTestId("section-en-vol");
    const inflightCards = within(inflightSection).getAllByTestId("acq-card");
    expect(inflightCards.length).toBeGreaterThan(0);
    const inflightCard = inflightCards[0] as HTMLElement;
    expect(inflightCard.querySelector("[data-station]")).toBeTruthy();

    // « À traiter » — card HAS a journey strip (blocked).
    const blockedSection = screen.getByTestId("section-a-traiter");
    const blockedCards = within(blockedSection).getAllByTestId("acq-card");
    expect(blockedCards.length).toBeGreaterThan(0);
    const blockedCard = blockedCards[0] as HTMLElement;
    expect(blockedCard.querySelector("[data-station]")).toBeTruthy();

    // « Cherché, rien trouvé » — card exists but no strip.
    const waitingSection = screen.getByTestId("section-cherche-rien-trouve");
    const waitingCard = within(waitingSection).queryByTestId("acq-card");
    expect(waitingCard).toBeInTheDocument();
    expect(waitingCard?.querySelector("[data-station]")).toBeNull();
  });

  it("un bloqué affiche sa raison ENTIÈRE et l'action sous la frise (§12)", async () => {
    renderPanel(full);

    // The full blocking reason is visible, not truncated.
    expect(
      await screen.findByText("titre ambigu — 3 candidats proposés"),
    ).toBeInTheDocument();

    // The « Résoudre → » link is inside the card.
    const section = screen.getByTestId("section-a-traiter");
    const card = within(section).getByTestId("acq-card");
    const resolve = within(card).getByRole("link", {
      name: /Résoudre/,
    });

    // The strip (data-station) comes BEFORE « Résoudre → » in document order (§12).
    const strip = card.querySelector("[data-station]");
    expect(strip).not.toBeNull();
    if (strip == null) throw new Error("unreachable — asserted above");
    expect(
      strip.compareDocumentPosition(resolve) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    // The resolve link targets the resolution deck with the decision id.
    expect(resolve).toHaveAttribute("href", "/medias?decision=42");
  });

  it("les bloqués sans provenance ne sont pas listés mais ne sont pas tus non plus", async () => {
    renderPanel({
      ...full,
      toHandle: { items: [], orphan_count: 2 },
    });

    // Section still renders because orphans > 0.
    expect(screen.queryByTestId("section-a-traiter")).toBeInTheDocument();

    // The crossref link appears with the orphan count.
    const link = await screen.findByRole("link", {
      name: /2 autres médias à traiter.*Contrôle/i,
    });
    expect(link).toHaveAttribute("href", "/controle");
  });

  it("« À traiter » disparaît quand il n'y a ni item ni orphelin", () => {
    renderPanel({
      ...full,
      toHandle: { items: [], orphan_count: 0 },
    });

    expect(screen.queryByTestId("section-a-traiter")).toBeNull();
  });

  it("l'état vide ne prétend jamais que tout va bien alors qu'une pile est non nulle", () => {
    renderPanel({
      ...empty,
      toHandle: { items: [], orphan_count: 3 },
    });

    // With orphans > 0, the panel must NOT claim « Rien en vol » (or any
    // all-clear message) — something still waits on the operator.
    expect(screen.queryByText(/Rien en vol/)).toBeNull();
    // The « À traiter » section IS present (orphans > 0).
    expect(screen.queryByTestId("section-a-traiter")).toBeInTheDocument();
  });
});
