import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EventStreamProvider } from "@/components/EventStreamProvider";
import { Sidebar } from "@/components/layout/Sidebar";
import { MockWebSocket } from "@/test/mockWebSocket";

/** Build a minimal ``Response``-shaped object. */
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
  MockWebSocket.reset();
  fetchMock.mockReset();
  fetchMock.mockImplementation((input) => {
    const url =
      typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes("/api/version")) {
      return Promise.resolve(
        buildResponse(200, { version: "0.40.0", build_commit: "abcdef1" }),
      );
    }
    return Promise.resolve(
      buildResponse(200, { status: "ok", redis: true, db: true }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Render the sidebar behind the router, query, and event-stream contexts. */
function renderSidebar(initialPath = "/"): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree: ReactElement = (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <EventStreamProvider>
          <Sidebar />
        </EventStreamProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(tree);
}

describe("Sidebar", () => {
  it("rend les trois micro-libellés de section", () => {
    renderSidebar();

    const nav = screen.getByRole("navigation", {
      name: /navigation latérale/i,
    });
    expect(within(nav).getByText("Supervision")).toBeInTheDocument();
    // « Système » is now BOTH the section micro-label and the collapsed nav
    // entry (V5) — assert at least the section label exists.
    expect(within(nav).getAllByText("Système").length).toBeGreaterThanOrEqual(1);
    expect(within(nav).getByText("Configuration")).toBeInTheDocument();
  });

  it("rend les destinations actives comme des liens", () => {
    renderSidebar();

    expect(screen.getByRole("link", { name: "Contrôle" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: "Pipeline" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Système" }),
    ).toBeInTheDocument();
  });

  it("rend Config comme lien actif (Registre fusionné dans /systeme)", () => {
    renderSidebar();

    // Config is an active link.
    expect(screen.getByRole("link", { name: "Config" })).toHaveAttribute(
      "href",
      "/config",
    );

    // Registre is gone — merged into /systeme (systeme-hub Phase 02).
    expect(
      screen.queryByRole("link", { name: "Registre" }),
    ).not.toBeInTheDocument();
  });

  it("marque la destination courante en actif (text-primary)", () => {
    renderSidebar("/pipeline");

    const pipeline = screen.getByRole("link", { name: "Pipeline" });
    expect(pipeline).toHaveAttribute("aria-current", "page");
    expect(pipeline.className).toContain("text-primary");
  });

  it("affiche la version dans le footer quand le menu est déplié", async () => {
    renderSidebar();

    // VersionCard renders the version string from GET /api/version.
    expect(await screen.findByText("Version")).toBeInTheDocument();
  });
});
