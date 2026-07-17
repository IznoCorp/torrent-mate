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
import { decisionsKeys } from "@/api/decisions";

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

/**
 * Render the shell as a layout route with a trivial index child.
 *
 * Args:
 *   client: Optional pre-configured QueryClient (for tests that need to
 *       seed cache data or observe invalidation).
 *
 * Returns:
 *   The QueryClient used (the caller's or a freshly created one).
 */
function renderShell(client?: QueryClient): QueryClient {
  const qc =
    client ??
    new QueryClient({
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
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return qc;
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

  it("n'affiche pas de badge et pas de dot quand tout est à zéro / idle (zero-state)", async () => {
    renderShell();

    // Wait until both the staging AND wanted URLs were actually fetched
    // (the initial fetchMock call alone does not prove both queries settled).
    await waitFor(() => {
      const stagingFetched = fetchMock.mock.calls.some((c) => {
        const arg = c[0];
        const u =
          typeof arg === "string"
            ? arg
            : arg instanceof URL
              ? arg.href
              : arg.url;
        return u.includes("/api/staging/media") && u.includes("page_size=1");
      });
      const wantedFetched = fetchMock.mock.calls.some((c) => {
        const arg = c[0];
        const u =
          typeof arg === "string"
            ? arg
            : arg instanceof URL
              ? arg.href
              : arg.url;
        return (
          u.includes("/api/acquisition/wanted") && u.includes("status=pending")
        );
      });
      expect(stagingFetched && wantedFetched).toBe(true);
    });

    // No nav-count badge element should be in the document — every badge
    // source is at its zero state.
    expect(
      document.querySelector('[data-slot="nav-count"]'),
    ).not.toBeInTheDocument();

    // No pipeline running dot should appear (pipeline is idle).
    expect(
      screen.queryByLabelText(/Pipeline en cours d/),
    ).not.toBeInTheDocument();

    // No paused pipeline dot either.
    expect(
      screen.queryByLabelText("Pipeline en pause"),
    ).not.toBeInTheDocument();
  });

  it("affiche un badge Scraping avec le compte awaiting_action, scoped au lien nav", async () => {
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

    // The badge must appear inside a Scraping nav link — a wiring swap
    // (e.g. badge placed on Acquisition) must fail this assertion.
    const scrapingLinks = screen.getAllByRole("link", { name: /Scraping/ });
    const scrapingLink = scrapingLinks[0];
    expect(scrapingLink).toBeDefined();
    const badge = await within(scrapingLink).findByText("3");
    expect(badge.getAttribute("data-slot")).toBe("nav-count");
  });

  it("affiche un badge Acquisition avec le pending wanted, scoped au lien nav", async () => {
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

    // The badge must appear inside an Acquisition nav link.
    const acqLinks = screen.getAllByRole("link", { name: /Acquisition/ });
    const acqLink = acqLinks[0];
    expect(acqLink).toBeDefined();
    const badge = await within(acqLink).findByText("3");
    expect(badge.getAttribute("data-slot")).toBe("nav-count");
  });

  it("affiche un dot Pipeline quand le pipeline est en cours, scoped au lien nav", async () => {
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

    // The running dot must appear inside a Pipeline nav link.
    const pipelineLinks = screen.getAllByRole("link", { name: /Pipeline/ });
    const runningDot = await within(
      pipelineLinks[0] as HTMLElement,
    ).findByLabelText(/Pipeline en cours d/);
    expect(runningDot).toBeInTheDocument();
  });

  it("affiche un dot Pipeline avec aria-label 'Pipeline en pause' quand paused", async () => {
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
          buildResponse(200, pipelineStatusPayload("paused")),
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

    // The paused dot has its own truthful label, scoped to the nav link.
    const pipelineLinks = screen.getAllByRole("link", { name: /Pipeline/ });
    const pausedDot = await within(
      pipelineLinks[0] as HTMLElement,
    ).findByLabelText("Pipeline en pause");
    expect(pausedDot).toBeInTheDocument();

    // Must NOT claim "en cours" — that label is only for running.
    expect(
      within(pipelineLinks[0] as HTMLElement).queryByLabelText(
        /Pipeline en cours d/,
      ),
    ).not.toBeInTheDocument();
  });

  it("affiche un marqueur '?' Compteur indisponible quand staging est en erreur (500)", async () => {
    // Return 500 for the staging badge query (the default 200s are set in
    // beforeEach; we override only the staging URL here).  The retry: false
    // on the default QueryClient makes the query error immediately.
    fetchMock.mockImplementation((input) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url.includes("/api/staging/media") && url.includes("page_size=1")) {
        return Promise.resolve(
          buildResponse(500, { detail: "Internal Server Error" }),
        );
      }
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(buildResponse(200, { username: "izno" }));
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

    // The "?" indeterminate marker appears inside a Scraping nav link with
    // the correct accessible name.  Scoping to within the link avoids the
    // duplicate-label collision with the BottomTabBar (both render the same
    // badge at different breakpoints).
    const scrapingLinks = screen.getAllByRole("link", { name: /Scraping/ });
    const scrapingLink = scrapingLinks[0];
    expect(scrapingLink).toBeDefined();
    const errorMarker = await within(
      scrapingLink as HTMLElement,
    ).findByLabelText("Compteur indisponible");
    expect(errorMarker).toHaveTextContent("?");
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
    // and the badge should appear scoped to the Scraping link.
    const scrapingLinks = screen.getAllByRole("link", { name: /Scraping/ });
    const badge = await within(
      (() => {
        const [l] = scrapingLinks;
        expect(l).toBeDefined();
        return l;
      })(),
    ).findByText("5");
    expect(badge.getAttribute("data-slot")).toBe("nav-count");
  });

  it("rafraîchit le badge staging sur un événement WS PipelineEnded", async () => {
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

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    expect(
      document.querySelector('[data-slot="nav-count"]'),
    ).not.toBeInTheDocument();

    act(() => {
      latestSocket().emitOpen();
      latestSocket().emitMessage({
        type: "ws.hello",
        data: { build_commit: "test-sha" },
      });
    });

    awaitingSent = 3;

    act(() => {
      latestSocket().emitMessage({
        id: "1680000000001-0",
        type: "PipelineEnded",
        data: { run_uid: "run-001" },
      });
    });

    const scrapingLinks = screen.getAllByRole("link", { name: /Scraping/ });
    const badge = await within(
      (() => {
        const [l] = scrapingLinks;
        expect(l).toBeDefined();
        return l;
      })(),
    ).findByText("3");
    expect(badge.getAttribute("data-slot")).toBe("nav-count");
  });

  it("invalide le cache decisions quand un événement WS ItemProgressed arrive (cache observation)", async () => {
    const qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    // Seed the decisions cache so we can observe the invalidation.
    qc.setQueryData(decisionsKeys.all, [
      { id: 1, status: "pending", staging_path: "/s/Test" },
    ]);
    expect(qc.getQueryState(decisionsKeys.all)?.isInvalidated).toBeFalsy();

    renderShell(qc);

    // Wait for the initial badge queries to settle.
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    // Drive the WebSocket handshake.
    act(() => {
      latestSocket().emitOpen();
      latestSocket().emitMessage({
        type: "ws.hello",
        data: { build_commit: "test-sha" },
      });
    });

    // Emit ItemProgressed with status queued_for_decision — the useEffect
    // must invalidate decisionsKeys.all.
    act(() => {
      latestSocket().emitMessage({
        id: "1680000000002-0",
        type: "ItemProgressed",
        data: {
          step: "scrape",
          status: "queued_for_decision",
          staging_path: "/staging/001-MOVIES/Test (2024)",
        },
      });
    });

    // After invalidation, the decisions query state is marked invalidated.
    await waitFor(() => {
      expect(qc.getQueryState(decisionsKeys.all)?.isInvalidated).toBe(true);
    });
  });
});
