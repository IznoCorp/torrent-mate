import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
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

/** A decisions list payload carrying the ``pending_count`` the badge reads. */
function decisionsPayload(pendingCount: number): Record<string, unknown> {
  return {
    items: [],
    pending_count: pendingCount,
    total: pendingCount,
    page: 1,
    page_size: 1,
  };
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  MockWebSocket.reset();
  // Authenticated identity so the TopBar's UserMenu has a session to read.
  fetchMock.mockResolvedValue(buildResponse(200, { username: "izno" }));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

/** Return the latest constructed MockWebSocket, asserting one exists. */
function latestSocket(): MockWebSocket {
  const socket = MockWebSocket.latest();
  if (socket === null) {
    throw new Error("Aucune instance WebSocket construite.");
  }
  return socket;
}

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

    // Registre is now an active link (S6 shipped).
    const registre = within(sheetNav).getByRole("link", { name: "Registre" });
    expect(registre).toHaveAttribute("href", "/registry");
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

describe("AppShell pending-count badge", () => {
  beforeEach(() => {
    // The badge query fires a lightweight count-only request
    // (page_size=1).  Stub it with the pending_count the test wants.
    fetchMock.mockImplementation((input) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(buildResponse(200, { username: "izno" }));
      }
      if (url.includes("/api/decisions") && url.includes("page_size=1")) {
        return Promise.resolve(buildResponse(200, decisionsPayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });
  });

  it("n'affiche pas de badge quand le nombre de décisions en attente est zéro", async () => {
    renderShell();

    // Let the badge query resolve.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    // No badge element with data-slot="badge" should be in the document —
    // the badge map is undefined when pending_count is 0.
    expect(
      document.querySelector('[data-slot="badge"]'),
    ).not.toBeInTheDocument();
  });

  it("affiche un badge avec le compte exact de décisions en attente", async () => {
    fetchMock.mockImplementation((input) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(buildResponse(200, { username: "izno" }));
      }
      if (url.includes("/api/decisions") && url.includes("page_size=1")) {
        return Promise.resolve(buildResponse(200, decisionsPayload(3)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // Two nav surfaces render the badge (Sidebar + BottomTabBar); both
    // carry the same count and data-slot="badge".
    const badges = await screen.findAllByText("3");
    // At least one badge must appear — filtering to <span> elements with
    // data-slot="badge" confirms these are Badge components.
    const badgeSpans = badges.filter(
      (el) => el.getAttribute("data-slot") === "badge",
    );
    expect(badgeSpans.length).toBeGreaterThanOrEqual(1);
  });

  it("rafraîchit le badge lorsqu'un événement WS « queued_for_decision » arrive", async () => {
    let countSent = 0;
    fetchMock.mockImplementation((input) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(buildResponse(200, { username: "izno" }));
      }
      if (url.includes("/api/decisions") && url.includes("page_size=1")) {
        return Promise.resolve(buildResponse(200, decisionsPayload(countSent)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // Wait for the initial badge query to settle.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    // No badge initially (count = 0).
    expect(
      document.querySelector('[data-slot="badge"]'),
    ).not.toBeInTheDocument();

    // Now drive the WebSocket: complete the handshake so the event-stream
    // state goes "connected" and the events ring starts receiving.
    act(() => {
      latestSocket().emitOpen();
      latestSocket().emitMessage({
        type: "ws.hello",
        data: { build_commit: "test-sha" },
      });
    });

    // Bump the mocked response for the refetch that the invalidation triggers.
    countSent = 5;

    // Emit an ItemProgressed event with status "queued_for_decision" — the
    // AppShell's useEffect should catch it and invalidate the decisions cache.
    act(() => {
      latestSocket().emitMessage({
        id: "1680000000000-0",
        type: "ItemProgressed",
        data: {
          step: "scrape",
          status: "queued_for_decision",
          staging_path: "/staging/001-MOVIES/Test (2024)",
        },
      });
    });

    // After the invalidation, the refetch should bring back pending_count=5
    // and the badge should appear on both nav surfaces.
    const badges = await screen.findAllByText("5");
    const badgeSpans = badges.filter(
      (el) => el.getAttribute("data-slot") === "badge",
    );
    expect(badgeSpans.length).toBeGreaterThanOrEqual(1);
  });
});
