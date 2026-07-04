import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HealthCard } from "@/components/dashboard/HealthCard";

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
      <HealthCard />
    </QueryClientProvider>
  );
  render(tree);
}

describe("HealthCard", () => {
  it("affiche une bannière dégradée quand Redis est hors ligne", async () => {
    fetchMock.mockResolvedValue(
      buildResponse(200, { status: "ok", redis: false, db: true }),
    );
    renderCard();

    // Wait for the resolved payload (db:true) — the banner also shows during the
    // loading state, so gating on "Base indexée" proves we assert post-fetch.
    expect(await screen.findByText("Base indexée")).toBeInTheDocument();
    expect(screen.getByText("Redis hors ligne")).toBeInTheDocument();
    expect(
      screen.getByText("Redis injoignable — le flux temps réel est dégradé."),
    ).toBeInTheDocument();
  });

  it("n’affiche aucune bannière quand tout est en ligne", async () => {
    fetchMock.mockResolvedValue(
      buildResponse(200, { status: "ok", redis: true, db: true }),
    );
    renderCard();

    expect(await screen.findByText("Redis en ligne")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("affiche une bannière quand la sonde de santé échoue", async () => {
    fetchMock.mockResolvedValue(buildResponse(500, { detail: "boom" }));
    renderCard();

    expect(
      await screen.findByText("Service dégradé — état de santé indisponible."),
    ).toBeInTheDocument();
  });
});
