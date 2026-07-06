import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/layout/AppShell";
import { AuthProvider } from "@/components/AuthProvider";

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/**
 * Inert WebSocket stub — the shell mounts `EventStreamProvider`, which opens a
 * socket. The live-stream behaviour is covered by `useEventStream.test.tsx`.
 */
class NoopWebSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  send(): void {
    // No-op: the shell tests never drive the socket.
  }
  close(): void {
    // No-op: nothing to tear down for the inert stub.
  }
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  // Authenticated identity so the TopBar's UserMenu has a session to read.
  fetchMock.mockResolvedValue(buildResponse(200, { username: "izno" }));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", NoopWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** Render the shell as a layout route with a trivial index child. */
function renderShell(): void {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const router = createMemoryRouter(
    [
      {
        element: <AppShell />,
        children: [{ index: true, element: <div>Contenu de page</div> }],
      },
    ],
    { initialEntries: ["/"] },
  );
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("AppShell mobile nav Sheet", () => {
  it("ouvre le tiroir de navigation via le bouton hamburger", async () => {
    renderShell();

    // The mobile nav Sheet is closed initially — its landmark is absent.
    expect(
      screen.queryByRole("navigation", { name: /navigation mobile/i }),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /ouvrir le menu de navigation/i }),
    );

    // The Sheet mounts the grouped nav with its section micro-labels.
    const sheetNav = await screen.findByRole("navigation", {
      name: /navigation mobile/i,
    });
    expect(within(sheetNav).getByText("Supervision")).toBeInTheDocument();
    expect(within(sheetNav).getByText("Configuration")).toBeInTheDocument();

    // The disabled stub is a non-interactive row carrying its wave chip.
    const registre = within(sheetNav)
      .getByText("Registre")
      .closest("[aria-disabled]");
    expect(registre).toHaveAttribute("aria-disabled", "true");
    expect(within(registre as HTMLElement).getByText("S6")).toBeInTheDocument();
  });

  it("ferme le tiroir lorsqu'une destination est choisie", async () => {
    renderShell();

    fireEvent.click(
      screen.getByRole("button", { name: /ouvrir le menu de navigation/i }),
    );

    const sheetNav = await screen.findByRole("navigation", {
      name: /navigation mobile/i,
    });
    fireEvent.click(within(sheetNav).getByRole("link", { name: "Pipeline" }));

    // Tapping an entry closes the Sheet (its landmark disappears).
    await waitFor(() => {
      expect(
        screen.queryByRole("navigation", { name: /navigation mobile/i }),
      ).not.toBeInTheDocument();
    });
  });
});
