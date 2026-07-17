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

/** A staging payload carrying the ``counts.awaiting_action`` the badge reads. */
function stagingPayload(awaitingAction: number): Record<string, unknown> {
  return {
    items: [],
    counts: {
      absent: 0,
      ambiguous: 0,
      awaiting_action: awaitingAction,
      matched: 0,
      scraped: 0,
      total: 0,
    },
    total: 0,
    page: 1,
    page_size: 1,
  };
}

/** A pipeline status payload for the running-dot badge. */
function pipelineStatusPayload(
  state: "idle" | "running" | "paused",
): Record<string, unknown> {
  return {
    state,
    run_uid: state === "idle" ? null : "run-123",
    step: state === "idle" ? null : "scrape",
    paused: state === "paused",
    watcher_enabled: true,
    pid: state === "idle" ? null : 12345,
  };
}

/** A wanted payload carrying the ``total`` the badge reads. */
function wantedPayload(total: number): Record<string, unknown> {
  return {
    items: [],
    total,
    page: 1,
    page_size: 1,
  };
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  MockWebSocket.reset();
  // Provide sensible defaults for every endpoint AppShellInner hits so
  // tests that don't override fetchMock still get well-shaped responses.
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
    if (url.includes("/api/staging/media") && url.includes("page_size=1")) {
      return Promise.resolve(buildResponse(200, stagingPayload(0)));
    }
    if (url.includes("/api/pipeline/status")) {
      return Promise.resolve(buildResponse(200, pipelineStatusPayload("idle")));
    }
    if (
      url.includes("/api/acquisition/wanted") &&
      url.includes("status=pending")
    ) {
      return Promise.resolve(buildResponse(200, wantedPayload(0)));
    }
    return Promise.resolve(buildResponse(200, {}));
  });
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

describe("AppShell nav badges", () => {
  beforeEach(() => {
    // Stub the three badge sources — all idle/zero by default so the zero-
    // state test works without per-test overrides.
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
      if (url.includes("/api/staging/media") && url.includes("page_size=1")) {
        return Promise.resolve(buildResponse(200, stagingPayload(0)));
      }
      if (url.includes("/api/pipeline/status")) {
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("idle")),
        );
      }
      if (
        url.includes("/api/acquisition/wanted") &&
        url.includes("status=pending")
      ) {
        return Promise.resolve(buildResponse(200, wantedPayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });
  });

  it("n'affiche pas de badge quand awaiting_action = 0, pipeline idle et wanted = 0", async () => {
    renderShell();

    // Let the badge queries resolve.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    // No nav-count badge element should be in the document — every badge
    // source is at its zero state.
    expect(
      document.querySelector('[data-slot="nav-count"]'),
    ).not.toBeInTheDocument();
  });

  it("affiche un badge avec le compte awaiting_action depuis le staging", async () => {
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
      if (url.includes("/api/staging/media") && url.includes("page_size=1")) {
        return Promise.resolve(buildResponse(200, stagingPayload(3)));
      }
      if (url.includes("/api/pipeline/status")) {
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("idle")),
        );
      }
      if (
        url.includes("/api/acquisition/wanted") &&
        url.includes("status=pending")
      ) {
        return Promise.resolve(buildResponse(200, wantedPayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // Two nav surfaces render the badge (Sidebar + BottomTabBar); both
    // carry the same count and data-slot="nav-count".
    const badges = await screen.findAllByText("3");
    const badgeSpans = badges.filter(
      (el) => el.getAttribute("data-slot") === "nav-count",
    );
    expect(badgeSpans.length).toBeGreaterThanOrEqual(1);
  });

  it("affiche un badge Acquisition avec le pending wanted", async () => {
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
      if (url.includes("/api/staging/media") && url.includes("page_size=1")) {
        return Promise.resolve(buildResponse(200, stagingPayload(0)));
      }
      if (url.includes("/api/pipeline/status")) {
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("idle")),
        );
      }
      if (
        url.includes("/api/acquisition/wanted") &&
        url.includes("status=pending")
      ) {
        return Promise.resolve(buildResponse(200, wantedPayload(3)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    const badges = await screen.findAllByText("3");
    const badgeSpans = badges.filter(
      (el) => el.getAttribute("data-slot") === "nav-count",
    );
    expect(badgeSpans.length).toBeGreaterThanOrEqual(1);
  });

  it("affiche un dot Pipeline quand le pipeline est en cours", async () => {
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
      if (url.includes("/api/staging/media") && url.includes("page_size=1")) {
        return Promise.resolve(buildResponse(200, stagingPayload(0)));
      }
      if (url.includes("/api/pipeline/status")) {
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("running")),
        );
      }
      if (
        url.includes("/api/acquisition/wanted") &&
        url.includes("status=pending")
      ) {
        return Promise.resolve(buildResponse(200, wantedPayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // StatusDot renders with showLabel={false} → no visible text, no
    // aria-label, only the CSS class .ps-dot--running reaches the DOM.
    // findAllByLabelText (as the plan originally suggested) cannot match;
    // fall back to a CSS-class selector via document.querySelectorAll.
    await waitFor(() => {
      expect(
        document.querySelectorAll(".ps-dot--running").length,
      ).toBeGreaterThanOrEqual(1);
    });
  });

  it("rafraîchit le badge staging lorsqu'un événement WS ItemProgressed arrive", async () => {
    let awaitingSent = 0;
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
      if (url.includes("/api/staging/media") && url.includes("page_size=1")) {
        return Promise.resolve(
          buildResponse(200, stagingPayload(awaitingSent)),
        );
      }
      if (url.includes("/api/pipeline/status")) {
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("idle")),
        );
      }
      if (
        url.includes("/api/acquisition/wanted") &&
        url.includes("status=pending")
      ) {
        return Promise.resolve(buildResponse(200, wantedPayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // Wait for the initial badge queries to settle.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    // No badge initially (awaiting_action = 0).
    expect(
      document.querySelector('[data-slot="nav-count"]'),
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
    awaitingSent = 5;

    // Emit an ItemProgressed event — the AppShell's useEffect should catch
    // it (any status now, not just queued_for_decision) and invalidate the
    // staging-media cache.
    act(() => {
      latestSocket().emitMessage({
        id: "1680000000000-0",
        type: "ItemProgressed",
        data: {
          step: "scrape",
          status: "blocked",
          staging_path: "/staging/001-MOVIES/Test (2024)",
        },
      });
    });

    // After the invalidation, the refetch should bring back awaiting_action=5
    // and the badge should appear on both nav surfaces.
    const badges = await screen.findAllByText("5");
    const badgeSpans = badges.filter(
      (el) => el.getAttribute("data-slot") === "nav-count",
    );
    expect(badgeSpans.length).toBeGreaterThanOrEqual(1);
  });
});
