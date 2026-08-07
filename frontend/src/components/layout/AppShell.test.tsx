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

/** A followed payload for the acquisition badge (takeable count). */
function followedPayload(
  items: readonly { status: string }[],
): Record<string, unknown> {
  return { items };
}

/** A to-handle payload for the acquisition badge. */
function toHandlePayload(count: number): Record<string, unknown> {
  return {
    items: Array.from({ length: count }, (_, i) => ({
      decision_id: i + 1,
      title: "Bloqué " + String(i + 1),
      kind: "movie",
      reason: "titre non résolu",
      stage: "scrape",
      candidates_count: 2,
      created_at: 1_700_000_000 + i,
    })),
    orphan_count: 0,
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
    // The shell's Acquisition badge now reads these two sources (D6). The global
    // mock must serve them, otherwise EVERY other describe renders the shell with
    // empty bodies — hiding their real subject behind a crash.
    if (url.includes("/api/acquisition/followed")) {
      return Promise.resolve(buildResponse(200, followedPayload([])));
    }
    if (url.includes("/api/acquisition/to-handle")) {
      return Promise.resolve(buildResponse(200, toHandlePayload(0)));
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
 * First nav link matching ``name`` — narrowed via a runtime guard so the
 * suite satisfies both no-non-null-assertion and assertion-style rules.
 */
function firstLink(name: RegExp | string): HTMLElement {
  const links = screen.getAllByRole("link", { name });
  const link = links[0];
  if (!link) {
    throw new Error(`no nav link matching ${String(name)}`);
  }
  return link;
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

    // Système (ex-Maintenance + Registre fusionnés, systeme-hub Phase 02).
    const systeme = within(sheetNav).getByRole("link", { name: "Système" });
    expect(systeme).toHaveAttribute("href", "/systeme");
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

  it("montre la VersionCard dans le tiroir mobile (tâche #11)", async () => {
    renderShell();

    // The version card lives in the desktop rail's `hidden md:flex` sidebar, so
    // it is invisible on a phone. Task #11 adds the SAME single-source
    // VersionCard to the mobile drawer — the redeploy hint must reach the phone.
    fireEvent.click(
      screen.getByRole("button", { name: /ouvrir le menu de navigation/i }),
    );

    const sheet = await screen.findByRole("dialog");
    // The card's StatPanel label + its commit line, scoped to the drawer.
    // findBy: the card shows a Skeleton until /api/version resolves (X2).
    expect(await within(sheet).findByText("Version")).toBeInTheDocument();
    expect(within(sheet).getByText(/^commit /)).toBeInTheDocument();
  });
});

describe("AppShell clampe le débordement horizontal (garde structurelle)", () => {
  // Class-contract guard, NOT a layout guard. The harness is vitest + jsdom,
  // which does not lay out — `scrollWidth`/`innerWidth` are always 0 there, so
  // an assertion on `documentElement.scrollWidth <= innerWidth` would pass
  // vacuously on ANY markup. What CAN regress and IS catchable here is the
  // shell losing its structural clamp: this test pins the exact classes that
  // make a page-level horizontal scroll impossible, so "someone removed
  // overflow-x-clip from the shell" breaks CI. The real-layout proof (390 px
  // Chrome, scrollWidth-innerWidth == 0 on every route) is ACC-05, run out of
  // band by the orchestrator.
  it("le root porte overflow-x-clip, <main> porte min-w-0 + overflow-x-clip, la bottom-bar est fixed", () => {
    renderShell();

    // The bottom bar is position:fixed — the DESIGN's whole point is that its
    // stability comes from the root clamping, never from the page happening not
    // to scroll. Lock `fixed` so a refactor cannot quietly make it flow.
    const bottomBar = screen.getByRole("navigation", {
      name: /navigation principale/i,
    });
    expect(bottomBar.className).toContain("fixed");

    // The shell root is the bottom bar's parent: BottomTabBar is a direct child
    // of AppShellInner's outer <div>, so this anchors on the real render tree
    // rather than on a brittle class selector. It MUST clip horizontal overflow
    // (clip, not hidden — no accidental scroll container) so no page-level
    // horizontal scroll is ever possible, whatever a child does.
    const root = bottomBar.parentElement;
    expect(root).not.toBeNull();
    expect(root?.className).toContain("overflow-x-clip");

    // <main> carries BOTH protections: min-w-0 so a wide child cannot push the
    // flex column wider than the viewport, and overflow-x-clip so a child that
    // still overflows is cut here instead of propagating up to the page.
    const main = screen.getByRole("main");
    expect(main.className).toContain("min-w-0");
    expect(main.className).toContain("overflow-x-clip");
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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(buildResponse(200, followedPayload([])));
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });
  });

  it("n'affiche pas de badge et pas de dot quand tout est à zéro / idle (zero-state)", async () => {
    renderShell();

    // Wait until the staging, followed AND toHandle URLs were actually fetched
    // (the initial fetchMock call alone does not prove the queries settled).
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
      const followedFetched = fetchMock.mock.calls.some((c) => {
        const arg = c[0];
        const u =
          typeof arg === "string"
            ? arg
            : arg instanceof URL
              ? arg.href
              : arg.url;
        return u.includes("/api/acquisition/followed");
      });
      expect(stagingFetched && followedFetched).toBe(true);
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

  it("affiche un badge Médias avec le compte awaiting_action, scoped au lien nav", async () => {
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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(buildResponse(200, followedPayload([])));
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // The badge must appear inside a Scraping nav link — a wiring swap
    // (e.g. badge placed on Acquisition) must fail this assertion.
    const badge = await within(firstLink(/Médias/)).findByText("3");
    expect(badge.getAttribute("data-slot")).toBe("nav-count");
  });

  it("le badge compte ce qui M'ATTEND : à récupérer + à traiter (D6)", async () => {
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
      if (url.includes("/api/acquisition/followed")) {
        // 2 takeable + 7 in-flight (en_acquisition) = 9 items, but only the
        // 2 « a_recuperer » count toward the badge.
        return Promise.resolve(
          buildResponse(
            200,
            followedPayload([
              { status: "a_recuperer" },
              { status: "a_recuperer" },
              { status: "en_acquisition" },
              { status: "en_acquisition" },
              { status: "en_acquisition" },
              { status: "en_acquisition" },
              { status: "en_acquisition" },
              { status: "en_acquisition" },
              { status: "en_acquisition" },
            ]),
          ),
        );
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(2)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // Expected total: 2 (takeable) + 2 (to handle) = 4.
    // The 7 « en_acquisition » (in-flight) do NOT count — they await nothing
    // from the operator.
    const badge = await within(firstLink(/Acquisition/)).findByText("4");
    expect(badge.getAttribute("data-slot")).toBe("nav-count");
  });

  it("le badge Acquisition affiche '?' quand useFollowed est en erreur, même si useToHandle est ok", async () => {
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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(
          buildResponse(500, { detail: "Internal Server Error" }),
        );
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(2)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    const errorMarker = await within(firstLink(/Acquisition/)).findByLabelText(
      "Compteur indisponible",
    );
    expect(errorMarker).toHaveTextContent("?");
  });

  it("le badge Acquisition affiche '?' quand useToHandle est en erreur, même si useFollowed est ok", async () => {
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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(
          buildResponse(
            200,
            followedPayload([{ status: "a_recuperer" }, { status: "a_recuperer" }]),
          ),
        );
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(
          buildResponse(500, { detail: "Internal Server Error" }),
        );
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    const errorMarker = await within(firstLink(/Acquisition/)).findByLabelText(
      "Compteur indisponible",
    );
    expect(errorMarker).toHaveTextContent("?");
  })

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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(buildResponse(200, followedPayload([])));
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // The running dot must appear inside a Pipeline nav link.
    const runningDot = await within(firstLink(/Pipeline/)).findByLabelText(
      /Pipeline en cours d/,
    );
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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(buildResponse(200, followedPayload([])));
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // The paused dot has its own truthful label, scoped to the nav link.
    const pausedDot = await within(firstLink(/Pipeline/)).findByLabelText(
      "Pipeline en pause",
    );
    expect(pausedDot).toBeInTheDocument();

    // Must NOT claim "en cours" — that label is only for running.
    expect(
      within(firstLink(/Pipeline/)).queryByLabelText(/Pipeline en cours d/),
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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(buildResponse(200, followedPayload([])));
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(0)));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderShell();

    // The "?" indeterminate marker appears inside a Scraping nav link with
    // the correct accessible name.  Scoping to within the link avoids the
    // duplicate-label collision with the BottomTabBar (both render the same
    // badge at different breakpoints).
    const errorMarker = await within(firstLink(/Médias/)).findByLabelText(
      "Compteur indisponible",
    );
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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(buildResponse(200, followedPayload([])));
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(0)));
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
    const badge = await within(firstLink(/Médias/)).findByText("5");
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
      if (url.includes("/api/acquisition/followed")) {
        return Promise.resolve(buildResponse(200, followedPayload([])));
      }
      if (url.includes("/api/acquisition/to-handle")) {
        return Promise.resolve(buildResponse(200, toHandlePayload(0)));
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

    const badge = await within(firstLink(/Médias/)).findByText("3");
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
  it("le badge Acquisition affiche '?' quand le serveur avoue une lecture dégradée", async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(buildResponse(200, { username: "izno" }));
      }
      if (url.includes("/api/staging/media")) {
        return Promise.resolve(buildResponse(200, stagingPayload(0)));
      }
      if (url.includes("/api/pipeline/status")) {
        return Promise.resolve(
          buildResponse(200, pipelineStatusPayload("idle")),
        );
      }
      if (url.includes("/api/acquisition/followed")) {
        // Two takeable rows — a number the badge must NOT show, because the
        // other half of the sum is unknowable.
        return Promise.resolve(
          buildResponse(200, followedPayload([
            { status: "a_recuperer" },
            { status: "a_recuperer" },
          ])),
        );
      }
      if (url.includes("/api/acquisition/to-handle")) {
        // HTTP 200, empty items — but the server SAYS the read failed.
        return Promise.resolve(
          buildResponse(200, { items: [], orphan_count: 0, degraded: true }),
        );
      }
      return Promise.resolve(buildResponse(200, {}));
    });
    renderShell();

    // Sidebar and bottom bar both render the badge map — two is correct.
    const marks = await screen.findAllByLabelText("Compteur indisponible");
    expect(marks.length).toBeGreaterThan(0);
    // And no numeric count coexists with the admission of ignorance.
    expect(screen.queryByText("2")).toBeNull();
  });
});
