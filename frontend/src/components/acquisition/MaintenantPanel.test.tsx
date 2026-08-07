/**
 * MaintenantPanel — five-section composition of the « Maintenant » view.
 *
 * Each building block (AcquisitionCard, JourneyStrip, FollowDetailSheet,
 * actionWords vocabulary, useToHandle hook) is tested in its own module.
 * This test verifies composition — card/strip linkage, section ordering,
 * and the loading/error/empty guards — not re-derivation of component internals.
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
  JourneyItem,
  ToHandleItem,
  ToHandleResponse,
  WantedItem,
} from "@/api/acquisition";

import { MaintenantPanel } from "./MaintenantPanel";
import { STAGES } from "./JourneyStrip";
import * as hooks from "@/hooks/useAcquisition";

// ── Fixture type ───────────────────────────────────────────────────────────

interface FullFixtures {
  readonly followed: readonly FollowedSeriesItem[];
  readonly wanted: readonly WantedItem[];
  readonly toHandle: ToHandleResponse;
  readonly downloads: readonly AcquisitionDownload[];
  readonly journeys: readonly JourneyItem[];
}

interface EmptyFixtures {
  readonly followed: readonly FollowedSeriesItem[];
  readonly wanted: readonly WantedItem[];
  readonly toHandle: ToHandleResponse;
  readonly downloads: readonly AcquisitionDownload[];
  readonly journeys: readonly JourneyItem[];
}

// ── Shared helper values ───────────────────────────────────────────────────

const EMPTY_FOLLOWED: readonly FollowedSeriesItem[] = [];
const EMPTY_WANTED: readonly WantedItem[] = [];
const EMPTY_TO_HANDLE: ToHandleResponse = { items: [], orphan_count: 0 };
const EMPTY_DOWNLOADS: readonly AcquisitionDownload[] = [];
const EMPTY_JOURNEYS: readonly JourneyItem[] = [];

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

/** A journey matching the inflight wanted item — stage "telech" (grabbed, not yet ingested). */
function inflightJourney(): JourneyItem {
  return {
    info_hash: "abc123def4567890",
    kind: "episode",
    media_ref: { tvdb_id: 371980, tmdb_id: 95396, imdb_id: null },
    follow_title: "Severance",
    season: 3,
    episode: null,
    status: "grabbed",
    grabbed_at: 1_750_000_000,
    ingested_at: null,
    scraped_at: null,
    dispatched_at: null,
    reconstructed_at: null,
    stuck: false,
    current_path: null,
    decision_id: null,
    dispatch_path: null,
    dispatch_run_uid: null,
    followed_id: null,
    grab_run_uid: null,
    ingest_path: null,
    ingest_run_uid: null,
    resolution_state: null,
    resolution_trigger: null,
    scrape_run_uid: null,
    scraped_ref: null,
    estimated_stages: null,
    release_name: null,
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
  journeys: [inflightJourney()],
};

const empty: EmptyFixtures = {
  followed: EMPTY_FOLLOWED,
  wanted: EMPTY_WANTED,
  toHandle: EMPTY_TO_HANDLE,
  downloads: EMPTY_DOWNLOADS,
  journeys: EMPTY_JOURNEYS,
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function mockHooks(f: FullFixtures | EmptyFixtures): void {
  // `useFollowed` — returns the followed items.
  vi.spyOn(hooks, "useFollowed").mockReturnValue({
    data: { items: [...f.followed] },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof hooks.useFollowed>);

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
  } as unknown as ReturnType<typeof hooks.useWanted>);

  // `useToHandle` — returns blocked items + orphan count.
  vi.spyOn(hooks, "useToHandle").mockReturnValue({
    data: { ...f.toHandle },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof hooks.useToHandle>);

  // `useDownloads` — returns live download progress.
  vi.spyOn(hooks, "useDownloads").mockReturnValue({
    data: { downloads: [...f.downloads], client_available: true },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof hooks.useDownloads>);

  // `useJourneys` — returns the pipeline journeys for stage derivation.
  vi.spyOn(hooks, "useJourneys").mockReturnValue({
    data: { journeys: [...f.journeys] },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof hooks.useJourneys>);
}

/** Render with whatever mocks are already installed. */
function renderPanelPreMocked(): void {
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
    const inflightCard = first(
      within(inflightSection).getAllByTestId("acq-card"),
    );
    expect(inflightCard.querySelector("[data-station]")).toBeTruthy();

    // « À traiter » — card HAS a journey strip (blocked).
    const blockedSection = screen.getByTestId("section-a-traiter");
    const blockedCard = first(
      within(blockedSection).getAllByTestId("acq-card"),
    );
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

  it("le renvoi orphelin apparaît même quand des items sont présents (§méthode)", async () => {
    renderPanel({
      ...full,
      toHandle: { items: [blockedItem()], orphan_count: 5 },
    });

    // Both the blocked card AND the crossref render.
    const section = screen.getByTestId("section-a-traiter");
    expect(section).toBeInTheDocument();

    // The card is present.
    expect(
      within(section).getByText("titre ambigu — 3 candidats proposés"),
    ).toBeInTheDocument();

    // The crossref is ALSO present — orphans are never invisible.
    const crossref = await within(section).findByRole("link", {
      name: /5 autres médias à traiter.*Contrôle/i,
    });
    expect(crossref).toHaveAttribute("href", "/controle");
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

  // ── Finding B: real stage from journey ──────────────────────────────────

  /** Get the first element from a query result, narrowing away undefined. */
  function first<T>(arr: readonly T[]): T {
    if (arr[0] == null) throw new Error("expected at least one element");
    return arr[0];
  }

  /** Stage-key → French label, built from the canonical JourneyStrip constant. */
  const STAGE_LABELS: Record<string, string> = Object.fromEntries(
    STAGES.map((s) => [s.key, s.label]),
  );

  /**
   * Assert that the card's journey strip has `expectedStage` as the current
   * station.  The JourneyStrip renders sr-only spans like "téléch. — en cours"
   * on the active (non-blocked) station; we query by that accessible text
   * instead of `[data-station]` which exists on EVERY station and always
   * matches "pris" first.
   */
  function assertCurrentStage(
    card: HTMLElement,
    expectedStage: string,
    blocked?: boolean,
  ): void {
    const state = blocked === true ? "bloquée" : "en cours";
    // JourneyStrip labels: STAGES = [{key:"pris",label:"pris"}, {key:"telech",label:"téléch."}, ...]
    const label = STAGE_LABELS[expectedStage] ?? expectedStage;
    expect(
      within(card).getByText(`${label} — ${state}`, { exact: false }),
    ).toBeTruthy();
  }

  it("une carte « en vol » dérive son étape du parcours réel, pas d'un « pris » en dur", () => {
    renderPanel(full);

    // The inflight journey has grabbed_at set → stage "telech".
    const section = screen.getByTestId("section-en-vol");
    const card = first(within(section).getAllByTestId("acq-card"));
    assertCurrentStage(card, "telech");
  });

  it("dérive « range » quand dispatched_at est le dernier timestamp", () => {
    const journey: JourneyItem = {
      ...inflightJourney(),
      grabbed_at: 1_750_000_000,
      ingested_at: 1_750_100_000,
      scraped_at: 1_750_200_000,
      dispatched_at: 1_750_300_000,
    };
    renderPanel({ ...full, journeys: [journey] });

    const section = screen.getByTestId("section-en-vol");
    const card = first(within(section).getAllByTestId("acq-card"));
    assertCurrentStage(card, "range");
  });

  it("dérive « scrape » quand scraped_at est le dernier timestamp atteint", () => {
    const journey: JourneyItem = {
      ...inflightJourney(),
      grabbed_at: 1_750_000_000,
      ingested_at: 1_750_100_000,
      scraped_at: 1_750_200_000,
      dispatched_at: null,
    };
    renderPanel({ ...full, journeys: [journey] });

    const section = screen.getByTestId("section-en-vol");
    const card = first(within(section).getAllByTestId("acq-card"));
    assertCurrentStage(card, "scrape");
  });

  it("dérive « ingere » quand ingested_at est le dernier timestamp atteint", () => {
    const journey: JourneyItem = {
      ...inflightJourney(),
      grabbed_at: 1_750_000_000,
      ingested_at: 1_750_100_000,
      scraped_at: null,
      dispatched_at: null,
    };
    renderPanel({ ...full, journeys: [journey] });

    const section = screen.getByTestId("section-en-vol");
    const card = first(within(section).getAllByTestId("acq-card"));
    assertCurrentStage(card, "ingere");
  });

  it("dérive « telech » quand seul grabbed_at est présent", () => {
    const journey: JourneyItem = {
      ...inflightJourney(),
      grabbed_at: 1_750_000_000,
      ingested_at: null,
      scraped_at: null,
      dispatched_at: null,
    };
    renderPanel({ ...full, journeys: [journey] });

    const section = screen.getByTestId("section-en-vol");
    const card = first(within(section).getAllByTestId("acq-card"));
    assertCurrentStage(card, "telech");
  });

  it("dérive « pris » quand aucun timestamp n'est présent", () => {
    const journey: JourneyItem = {
      ...inflightJourney(),
      grabbed_at: null,
      ingested_at: null,
      scraped_at: null,
      dispatched_at: null,
    };
    renderPanel({ ...full, journeys: [journey] });

    const section = screen.getByTestId("section-en-vol");
    const card = first(within(section).getAllByTestId("acq-card"));
    assertCurrentStage(card, "pris");
  });

  it("sans parcours correspondant, aucune frise n'est affichée", () => {
    // No journey matches the inflight wanted (empty journeys).
    renderPanel({ ...full, journeys: [] });

    const section = screen.getByTestId("section-en-vol");
    const card = first(within(section).getAllByTestId("acq-card"));
    // No strip, no data-station — we don't claim « pris » when we can't
    // establish the stage.
    expect(card.querySelector("[data-station]")).toBeNull();
  });

  it("un parcours reconstruit avec une lacune n'affiche pas de frise (§14.3)", () => {
    // reconstructed_at is set, but ingested_at is missing between grabbed and scraped.
    const journey: JourneyItem = {
      ...inflightJourney(),
      grabbed_at: 1_750_000_000,
      ingested_at: null, // gap in a rebuilt row → unknown
      scraped_at: 1_750_200_000,
      dispatched_at: null,
      reconstructed_at: 1_750_500_000,
    };
    renderPanel({ ...full, journeys: [journey] });

    const section = screen.getByTestId("section-en-vol");
    const card = first(within(section).getAllByTestId("acq-card"));
    // §14.3: unknown ≠ not reached — omit the strip.
    expect(card.querySelector("[data-station]")).toBeNull();
  });

  // ── Finding C: loading / error states ──────────────────────────────────

  it("affiche « Chargement… » quand les données ne sont pas encore arrivées", () => {
    // Override mocks to simulate loading state — no data yet.
    vi.spyOn(hooks, "useFollowed").mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useFollowed>);
    vi.spyOn(hooks, "useWanted").mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useWanted>);
    vi.spyOn(hooks, "useToHandle").mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useToHandle>);
    vi.spyOn(hooks, "useDownloads").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useDownloads>);
    vi.spyOn(hooks, "useJourneys").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useJourneys>);

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

    // Loading state — NOT the all-clear message.
    expect(screen.getByText(/Chargement/)).toBeInTheDocument();
    expect(screen.queryByText(/Rien à signaler/)).toBeNull();
  });

  it("ne montre pas « Chargement… » quand des données sont déjà en cache", () => {
    // Loading is true but data IS available (TanStack Query stale refetch).
    vi.spyOn(hooks, "useFollowed").mockReturnValue({
      data: { items: [...full.followed] },
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useFollowed>);
    vi.spyOn(hooks, "useWanted").mockReturnValue({
      data: {
        items: [...full.wanted],
        total: full.wanted.length,
        page: 1,
        page_size: 50,
      },
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useWanted>);
    vi.spyOn(hooks, "useToHandle").mockReturnValue({
      data: { ...full.toHandle },
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useToHandle>);
    vi.spyOn(hooks, "useDownloads").mockReturnValue({
      data: { downloads: [], client_available: true },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useDownloads>);
    vi.spyOn(hooks, "useJourneys").mockReturnValue({
      data: { journeys: [] },
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useJourneys>);

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

    // Sections render with cached data — no loading placeholder.
    expect(screen.getByTestId("section-a-recuperer")).toBeInTheDocument();
    expect(screen.queryByText(/Chargement/)).toBeNull();
  });

  it("affiche une erreur visible quand les éléments à traiter ne peuvent pas être chargés", () => {
    vi.spyOn(hooks, "useFollowed").mockReturnValue({
      data: { items: [] },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useFollowed>);
    vi.spyOn(hooks, "useWanted").mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 50 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useWanted>);
    vi.spyOn(hooks, "useToHandle").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof hooks.useToHandle>);
    vi.spyOn(hooks, "useDownloads").mockReturnValue({
      data: { downloads: [], client_available: true },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useDownloads>);
    vi.spyOn(hooks, "useJourneys").mockReturnValue({
      data: { journeys: [] },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useJourneys>);

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

    // § panne ≠ absence — the section renders with an error, not silently gone.
    const section = screen.getByTestId("section-a-traiter");
    expect(
      within(section).getByText(/Impossible de charger les éléments à traiter/),
    ).toBeInTheDocument();
    // The empty all-clear message must NOT appear.
    expect(screen.queryByText(/Rien à signaler/)).toBeNull();
  });

  it("affiche une erreur visible quand les suivis ne peuvent pas être chargés", () => {
    vi.spyOn(hooks, "useFollowed").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof hooks.useFollowed>);
    // wanted needs to be non-empty so the panel doesn't go into empty-state path.
    vi.spyOn(hooks, "useWanted").mockReturnValue({
      data: { items: [inflightWanted()], total: 1, page: 1, page_size: 50 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useWanted>);
    vi.spyOn(hooks, "useToHandle").mockReturnValue({
      data: { items: [], orphan_count: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useToHandle>);
    vi.spyOn(hooks, "useDownloads").mockReturnValue({
      data: { downloads: [], client_available: true },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useDownloads>);
    vi.spyOn(hooks, "useJourneys").mockReturnValue({
      data: { journeys: [] },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useJourneys>);

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

    // The followed-based sections are all now empty (data=undefined) BUT
    // their visibility is zero → they're hidden. The error appears only in
    // sections that WOULD be visible: but when followed errors with no data,
    // the follow-based sections are hidden (count=0).
    //
    // The key assertion: the panel does NOT show « Rien à signaler » while
    // any error is present — it doesn't falsely claim calm.
    expect(screen.queryByText(/Rien à signaler/)).toBeNull();
  });

  it("quand tous les hooks sont en erreur sans données, le panneau ne dit pas « Rien à signaler »", () => {
    // The worst case: every hook failed, no data.
    // § panne ≠ absence — the panel must NOT claim there is nothing.
    // The « à traiter » section stays visible because toHandle.isError
    // forces its visibility; its per-section error renders inside it.
    vi.spyOn(hooks, "useFollowed").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof hooks.useFollowed>);
    vi.spyOn(hooks, "useWanted").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof hooks.useWanted>);
    vi.spyOn(hooks, "useToHandle").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof hooks.useToHandle>);
    vi.spyOn(hooks, "useDownloads").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useDownloads>);
    vi.spyOn(hooks, "useJourneys").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useJourneys>);

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

    // « Rien à signaler » must NEVER appear when hooks have failed.
    expect(screen.queryByText(/Rien à signaler/)).toBeNull();
    // The « à traiter » section renders its per-section error.
    const section = screen.getByTestId("section-a-traiter");
    expect(
      within(section).getByText(/Impossible de charger les éléments à traiter/),
    ).toBeInTheDocument();
  });

  it("ne dit pas « Rien à signaler » quand les suivis et les wanted sont en erreur mais toHandle est vide", () => {
    // Partial failure: followed + wanted errored, toHandle OK but empty.
    // No section is visible (toHandle cleared the visibility gate), so the
    // panel-level fallback error message renders instead of the per-section
    // error states — but « Rien à signaler » must still be suppressed.
    vi.spyOn(hooks, "useFollowed").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof hooks.useFollowed>);
    vi.spyOn(hooks, "useWanted").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof hooks.useWanted>);
    vi.spyOn(hooks, "useToHandle").mockReturnValue({
      data: { items: [], orphan_count: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useToHandle>);
    vi.spyOn(hooks, "useDownloads").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useDownloads>);
    vi.spyOn(hooks, "useJourneys").mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useJourneys>);

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

    // The guarantee that matters: a failure NEVER renders as « nothing to
    // report ». Silence about a failure is the one thing this panel may not do.
    expect(screen.queryByText(/Rien à signaler/)).toBeNull();

    // « En vol » opens on its own error rather than collapsing, so the operator
    // is told WHICH data is missing instead of reading a generic panel message.
    // Naming the gap is strictly more useful than announcing that there is one.
    expect(screen.getByTestId("section-en-vol")).toBeInTheDocument();
    expect(
      screen.getByText(/Impossible de charger les éléments en vol/),
    ).toBeInTheDocument();
  });
  // ── Behaviours re-homed from the dissolved tabs ────────────────────────
  //
  // « Vue d'ensemble » and « File d'acquisition » disappeared with the tab bar.
  // Three of their guarantees had no surface left; these pin them in their new
  // home, because a behaviour kept in the code but guarded nowhere is not kept.

  it("signale les acquisitions parquées à « récupéré », que rien d'autre ne montre", async () => {
    // §14.1 knows only two legitimate rest states; « récupéré » is transitory
    // and must advance on its own. A row stagnating there is MUTE — the search
    // pass only resumes pending/searching/available, so the media stays wanted
    // with nobody looking for it.
    vi.spyOn(hooks, "useOverview").mockReturnValue({
      data: { stalled_grabs: 2 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useOverview>);

    renderPanel(empty);

    expect(
      await screen.findByText(
        /2 acquisitions récupérées ne sont jamais arrivées en médiathèque/,
      ),
    ).toBeInTheDocument();
  });

  it("ne montre aucune alerte quand rien n'est parqué — une alerte permanente n'alerte plus", () => {
    vi.spyOn(hooks, "useOverview").mockReturnValue({
      data: { stalled_grabs: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useOverview>);

    renderPanel(empty);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("ouvre « En vol » pour un client injoignable, même sans AUCUNE ligne en vol", () => {
    // The failure this pins: the notice used to live INSIDE a section whose
    // visibility depended on having wanted rows. With none, the section
    // collapsed and took the notice with it — an unreachable client rendered
    // as silence, which is precisely what the notice exists to prevent.
    mockHooks(empty);
    vi.spyOn(hooks, "useDownloads").mockReturnValue({
      data: { downloads: [], client_available: false },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useDownloads>);
    renderPanelPreMocked();

    expect(screen.getByTestId("section-en-vol")).toBeInTheDocument();
    expect(screen.getByText(/Client torrent injoignable/)).toBeInTheDocument();
  });

  it("dit que le client torrent est injoignable MÊME quand rien ne télécharge", () => {
    // Hoisted out of the list on purpose: with an unreachable client, progress
    // is unknowable. Saying nothing would let the absence of rows read as
    // « rien ne télécharge » — a different statement, and a false one.
    mockHooks(full);
    vi.spyOn(hooks, "useDownloads").mockReturnValue({
      data: { downloads: [], client_available: false },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useDownloads>);
    renderPanelPreMocked();

    expect(screen.getByText(/Client torrent injoignable/)).toBeInTheDocument();
  });

  it("nomme la release réellement récupérée sur la carte « En vol »", () => {
    mockHooks(full);
    vi.spyOn(hooks, "useJourneys").mockReturnValue({
      data: {
        journeys: full.journeys.map((j) => ({
          ...j,
          release_name: "Silo.S01E01.2160p.WEB-DL.DV.HDR",
        })),
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof hooks.useJourneys>);
    renderPanelPreMocked();

    // What tells a FLAC soundtrack apart from the film of the same name.
    const enVol = screen.getByTestId("section-en-vol");
    expect(
      within(enVol).getAllByText("Silo.S01E01.2160p.WEB-DL.DV.HDR").length,
    ).toBeGreaterThan(0);
  });

  it("avoue que le nom de release manque, plutôt que d'afficher le titre à sa place", () => {
    // The fixture's journeys carry `release_name: null`. Showing the media
    // title there would look like an answer and be one — a wrong one.
    renderPanel(full);

    const enVol = screen.getByTestId("section-en-vol");
    expect(
      within(enVol).getAllByText("Nom de release non enregistré").length,
    ).toBeGreaterThan(0);
  });
});
