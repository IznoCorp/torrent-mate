import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, queryClient } from "@/api/client";
import { AuthProvider } from "@/components/AuthProvider";
import { routes } from "@/router";

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

/** Extract the request URL from a `fetch` first argument without stringifying. */
function requestUrl(input: Parameters<typeof fetch>[0]): string {
  if (typeof input === "string") {
    return input;
  }
  return input instanceof URL ? input.href : input.url;
}

/**
 * Inert WebSocket stub — the authenticated shell mounts `EventStreamProvider`,
 * which opens a socket. jsdom's real WebSocket would attempt a live connection;
 * this no-op keeps the routing tests hermetic (the stream's own behaviour is
 * covered by `useEventStream.test.tsx`).
 */
class NoopWebSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  send(): void {
    // No-op: the routing tests never drive the socket.
  }
  close(): void {
    // No-op: nothing to tear down for the inert stub.
  }
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  // Default: an authenticated session so the guard admits the shell routes.
  fetchMock.mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.includes("/api/auth/me")) {
      return Promise.resolve(buildResponse(200, { username: "izno" }));
    }
    if (url.includes("/api/decisions")) {
      return Promise.resolve(
        buildResponse(200, {
          items: [],
          pending_count: 0,
          total: 0,
          page: 1,
          page_size: 50,
        }),
      );
    }
    // Contrôle dashboard panels (phase 5.3) — minimal well-shaped payloads
    // so the page renders without crashing.
    if (url.includes("/api/staging/media")) {
      return Promise.resolve(
        buildResponse(200, { items: [], total: 0, page: 1, page_size: 100 }),
      );
    }
    if (url.includes("/api/decisions/activity")) {
      return Promise.resolve(
        buildResponse(200, { in_progress: [], pending_count: 0 }),
      );
    }
    if (url.includes("/api/pipeline/history")) {
      return Promise.resolve(buildResponse(200, { runs: [], total: 0 }));
    }
    if (url.includes("/api/pipeline/status")) {
      return Promise.resolve(
        buildResponse(200, {
          state: "idle",
          paused: false,
          watcher_enabled: true,
        }),
      );
    }
    if (url.includes("/api/acquisition/wanted")) {
      return Promise.resolve(
        buildResponse(200, { items: [], total: 0, page: 1, page_size: 1 }),
      );
    }
    if (url.includes("/api/acquisition/downloads")) {
      return Promise.resolve(
        buildResponse(200, { downloads: [], client_available: true }),
      );
    }
    if (url.includes("/api/acquisition/status")) {
      return Promise.resolve(
        buildResponse(200, {
          watcher_enabled: true,
          last_successful_run_at: null,
          recent_runs: [],
          deferred: [],
        }),
      );
    }
    if (url.includes("/api/maintenance/disks")) {
      return Promise.resolve(buildResponse(200, { disks: [] }));
    }
    if (url.includes("/api/maintenance/index-health")) {
      return Promise.resolve(
        buildResponse(200, {
          items: 0,
          movies: 0,
          shows: 0,
          files: 0,
          size_gb: 0,
          nfo: { valid: 0, invalid: 0, missing: 0 },
          repair_queue_pending: 0,
          repair_queue_oldest_age_s: null,
          outbox_pending: 0,
          outbox_oldest_age_s: null,
          last_scan_id: null,
          last_scan_mode: null,
          last_scan_status: null,
          last_scan_started_at: null,
          last_scan_finished_at: null,
          last_scan_stuck: false,
          soft_deleted: 0,
          canonical_null: 0,
          degraded: false,
          error: null,
        }),
      );
    }
    if (url.includes("/api/maintenance/schedulers")) {
      return Promise.resolve(buildResponse(200, { schedulers: [] }));
    }
    // Unmocked endpoints: an honest 404 — panels show their error state
    // instead of crashing on a fake 200 with a non-contract body.
    return Promise.resolve(buildResponse(404, { detail: "not mocked" }));
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", NoopWebSocket);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // The B4/B5 tests exercise the app singleton `queryClient` (the only client
  // wired with the global 401 policy); drop its state so nothing leaks forward.
  queryClient.clear();
});

/**
 * Render the real route table at `path` via a fresh memory router, wrapped in a
 * retry-free Query provider and the `AuthProvider` the shell's guard reads.
 */
function renderAt(path: string): void {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("router", () => {
  it("monte le shell et le tableau de bord sur « / »", async () => {
    renderAt("/");

    // Dashboard page rendered inside the shell (once `me` resolves authed).
    expect(
      await screen.findByRole("heading", { name: /contrôle/i }),
    ).toBeInTheDocument();
    // Shell chrome present: the top bar's user menu and the mobile nav.
    expect(
      screen.getByRole("button", { name: /menu utilisateur/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: /navigation principale/i }),
    ).toBeInTheDocument();
  });

  it("monte la page Maintenance (vague S3) sur « /maintenance »", async () => {
    renderAt("/maintenance");

    // S3 replaced the ComingSoon placeholder with the real dashboard: assert
    // the page heading (the h1, not the bottom-nav link) mounts.
    expect(
      await screen.findByRole("heading", { name: "Maintenance" }),
    ).toBeInTheDocument();
  });

  it("redirige /maintenance?run=<uid> vers /pipeline?run=<uid> (DOIT-10)", async () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    const router = createMemoryRouter(routes, {
      initialEntries: ["/maintenance?run=abc123def456"],
    });
    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/pipeline");
      expect(router.state.location.search).toBe("?run=abc123def456");
    });
  });

  it("ne redirige PAS /maintenance (sans ?run=) — rend la page Maintenance", async () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    const router = createMemoryRouter(routes, {
      initialEntries: ["/maintenance"],
    });
    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>,
    );

    // The heading "Maintenance" renders — no Navigate redirect.
    expect(
      await screen.findByRole("heading", { name: "Maintenance" }),
    ).toBeInTheDocument();
    // The location stays on /maintenance.
    expect(router.state.location.pathname).toBe("/maintenance");
  });

  it("monte la page Médias sur « /medias »", async () => {
    renderAt("/medias");

    // The Medias page heading replaces the old Decisions page (S3).
    expect(
      await screen.findByRole("heading", { name: "Médias" }),
    ).toBeInTheDocument();
  });

  it("redirige « /scraping » vers « /medias »", async () => {
    renderAt("/scraping");

    // /scraping → LegacyRedirect → Navigate to /medias → Medias heading visible.
    expect(
      await screen.findByRole("heading", { name: "Médias" }),
    ).toBeInTheDocument();
  });

  it("transmet ?media=X de /scraping vers /medias (memory-router)", async () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    const router = createMemoryRouter(routes, {
      initialEntries: ["/scraping?media=tt0123456"],
    });
    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/medias");
      expect(router.state.location.search).toBe("?media=tt0123456");
    });
  });

  it("transmet ?decision=N de /scraping vers /medias (memory-router)", async () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    const router = createMemoryRouter(routes, {
      initialEntries: ["/scraping?decision=42"],
    });
    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/medias");
      expect(router.state.location.search).toBe("?decision=42");
    });
  });

  it("marque l’onglet actif du bottom tab bar via aria-current", async () => {
    renderAt("/pipeline");

    const bottomBar = await screen.findByRole("navigation", {
      name: /navigation principale/i,
    });
    // Active tab carries aria-current="page"…
    expect(
      within(bottomBar).getByRole("link", { name: "Pipeline" }),
    ).toHaveAttribute("aria-current", "page");
    // …inactive tabs do not (Contrôle leads the bar since the
    // 2026-07-15 operator review; Maintenance left it).
    expect(
      within(bottomBar).getByRole("link", { name: "Contrôle" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("rend la page 404 française sur une route inconnue", async () => {
    renderAt("/route-inexistante");

    expect(
      await screen.findByRole("heading", { name: /page introuvable/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("depuis « /login » authentifié, revient à la cible « ?redirect » sûre", async () => {
    renderAt("/login?redirect=/pipeline");

    // Already authenticated → the login route redirects to the safe target.
    expect(
      await screen.findByRole("heading", { name: "Pipeline" }),
    ).toBeInTheDocument();
  });

  it("rejette un « ?redirect » protocol-relative et retombe sur « / »", async () => {
    renderAt("/login?redirect=//evil.example/pwned");

    // Open-redirect guard: `//evil` collapses to the app root (Dashboard).
    expect(
      await screen.findByRole("heading", { name: /contrôle/i }),
    ).toBeInTheDocument();
  });

  it("redirige « / » vers « /login » quand la session est absente", async () => {
    fetchMock.mockImplementation((input) => {
      const url = requestUrl(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(buildResponse(401, { detail: "unauthorized" }));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    renderAt("/");

    // Unauthenticated → the guard sends us to the login form (unique submit CTA).
    expect(
      await screen.findByRole("button", { name: /se connecter/i }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.queryByRole("heading", { name: /contrôle/i }),
      ).not.toBeInTheDocument();
    });
  });

  // --- B4 / B5: session-expiry 401 handling (app singleton `queryClient`) ----

  /** Render the real routes at `path` behind the *singleton* client (401-wired). */
  function renderAtWithSingleton(
    path: string,
  ): ReturnType<typeof createMemoryRouter> {
    const router = createMemoryRouter(routes, { initialEntries: [path] });
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </QueryClientProvider>,
    );
    return router;
  }

  it("B4 — un 401 en session efface le cache `me` périmé : atterrit sur /login et y reste", async () => {
    // `me` is valid until the first `/api/health` 401 (session expiring
    // mid-use); afterwards `me` also 401s, exactly as a lost session behaves.
    let sessionValid = true;
    fetchMock.mockImplementation((input) => {
      const url = requestUrl(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(
          sessionValid
            ? buildResponse(200, { username: "izno" })
            : buildResponse(401, { detail: "unauthorized" }),
        );
      }
      if (url.includes("/api/health")) {
        sessionValid = false;
        return Promise.resolve(buildResponse(401, { detail: "unauthorized" }));
      }
      // A lost session 401s everywhere — panels error out, never crash.
      return Promise.resolve(
        sessionValid
          ? buildResponse(404, { detail: "not mocked" })
          : buildResponse(401, { detail: "unauthorized" }),
      );
    });

    renderAtWithSingleton("/");

    // The stale-success `me` is invalidated on the health 401 → we land on the
    // login form and STAY there (no bounce back to the dashboard, no loop).
    expect(
      await screen.findByRole("button", { name: /se connecter/i }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(
        screen.queryByRole("heading", { name: /contrôle/i }),
      ).not.toBeInTheDocument();
    });
    // Settle any pending microtasks, then re-assert we did not ping-pong back.
    await act(async () => {
      await Promise.resolve();
    });
    expect(
      screen.getByRole("button", { name: /se connecter/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /contrôle/i }),
    ).not.toBeInTheDocument();
  });

  it("B5 — un 401 survenant déjà sur /login préserve le paramètre ?redirect", async () => {
    fetchMock.mockImplementation((input) => {
      const url = requestUrl(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(buildResponse(401, { detail: "unauthorized" }));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    const router = renderAtWithSingleton("/login?redirect=/pipeline");

    // Unauthenticated → the login form shows (the `me` 401 is exempt from the
    // redirect handler, so nothing has navigated yet).
    expect(
      await screen.findByRole("button", { name: /se connecter/i }),
    ).toBeInTheDocument();

    // A non-`me` query 401s while sitting on /login → the handler must keep us on
    // /login WITHOUT stripping the redirect target.
    await act(async () => {
      await queryClient
        .fetchQuery({
          queryKey: ["__probe_401__"],
          queryFn: () => Promise.reject(new ApiError(401, "expired")),
          retry: false,
        })
        .catch(() => undefined);
    });

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/login");
      expect(router.state.location.search).toBe("?redirect=/pipeline");
    });
  });
});
