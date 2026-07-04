import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EventStreamProvider } from "@/components/EventStreamProvider";
import { TopBar } from "@/components/layout/TopBar";
import { AuthProvider } from "@/components/AuthProvider";
import { MockWebSocket } from "@/test/mockWebSocket";

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Return the latest constructed socket, asserting one exists. */
function latestSocket(): MockWebSocket {
  const socket = MockWebSocket.latest();
  if (socket === null) {
    throw new Error("Aucune instance WebSocket construite.");
  }
  return socket;
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  MockWebSocket.reset();
  fetchMock.mockReset();
  // Authenticated identity so the TopBar's UserMenu has a session to read.
  fetchMock.mockResolvedValue(buildResponse(200, { username: "izno" }));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Render the TopBar behind the providers it and the event stream require. */
function renderTopBar(): void {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter>
          <EventStreamProvider>
            <TopBar />
          </EventStreamProvider>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("EventStreamProvider ↔ TopBar StatusDot", () => {
  it("reflète la progression connecting → connected → reconnecting", async () => {
    renderTopBar();

    // Initial: the socket is opening.
    expect(await screen.findByText("Connexion…")).toBeInTheDocument();

    // Handshake → connected (success dot + French tooltip).
    act(() => {
      latestSocket().emitMessage({
        type: "ws.hello",
        data: { build_commit: "abc1234" },
      });
    });
    expect(screen.getByText("En ligne")).toBeInTheDocument();
    expect(screen.getByTitle("Flux temps réel connecté")).toBeInTheDocument();

    // A drop → the dot reports reconnection (warning).
    act(() => {
      latestSocket().emitClose(1000);
    });
    expect(screen.getByText("Reconnexion…")).toBeInTheDocument();
  });

  it("n’ouvre qu’un seul socket derrière le provider partagé", () => {
    renderTopBar();
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
