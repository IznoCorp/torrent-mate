/**
 * VersionCard tests — X2 (ticket 250): a down /api/version renders a loud
 * danger banner, never a muted "—" placeholder; the pending state renders a
 * Skeleton instead of collapsing to the same placeholder.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VersionCard } from "@/components/dashboard/VersionCard";

const { streamMock } = vi.hoisted(() => ({
  streamMock: vi.fn(),
}));

vi.mock("@/hooks/useEventStreamContext", () => ({
  useEventStreamContext: () => streamMock() as unknown,
}));

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  // Default stream state: no live commit known (no mismatch hint).
  streamMock.mockReturnValue({
    connectionState: "connected",
    events: [],
    buildCommit: null,
    lastEventId: null,
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Render the card behind a fresh, retry-free query client. */
function renderCard(): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <VersionCard />
    </QueryClientProvider>
  );
  render(tree);
}

describe("VersionCard", () => {
  it("affiche un squelette pendant le chargement (jamais « — »)", () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined));
    renderCard();

    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(screen.queryByText("—")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("affiche une bannière d'erreur role=alert quand /api/version échoue", async () => {
    fetchMock.mockResolvedValue(buildResponse(500, { detail: "boom" }));
    renderCard();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Version indisponible");
    expect(alert).toHaveClass("text-danger");
    expect(screen.queryByText("—")).not.toBeInTheDocument();
  });

  it("affiche la version et le commit court quand la requête réussit", async () => {
    fetchMock.mockResolvedValue(
      buildResponse(200, { version: "0.75.1", build_commit: "abcdef0123456" }),
    );
    renderCard();

    expect(await screen.findByText("0.75.1")).toBeInTheDocument();
    expect(screen.getByText("commit abcdef0")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("VersionCard — indice de décalage (DASHBOARD-4, ticket 250)", () => {
  it("rend le décalage de version comme Badge warning avec le commit en mono", async () => {
    streamMock.mockReturnValue({
      connectionState: "connected",
      events: [],
      buildCommit: "fedcba9876543210",
      lastEventId: null,
    });
    fetchMock.mockResolvedValue(
      buildResponse(200, { version: "0.73.0", build_commit: "abc1234def" }),
    );
    renderCard();

    // The short live commit renders as a mono token inside a warning Badge.
    const commit = await screen.findByText("fedcba9");
    expect(commit.className).toContain("font-mono");
    const badge = commit.closest('[data-slot="badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.className).toContain("--warning");
  });

  it("aucun badge de décalage quand les commits concordent", async () => {
    streamMock.mockReturnValue({
      connectionState: "connected",
      events: [],
      buildCommit: "abc1234def",
      lastEventId: null,
    });
    fetchMock.mockResolvedValue(
      buildResponse(200, { version: "0.73.0", build_commit: "abc1234def" }),
    );
    renderCard();

    expect(await screen.findByText(/commit abc1234/)).toBeInTheDocument();
    expect(
      screen.queryByText(/Nouvelle version côté serveur/),
    ).not.toBeInTheDocument();
  });
});
