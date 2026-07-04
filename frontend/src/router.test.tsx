import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  // Default: an authenticated session so the guard admits the shell routes.
  fetchMock.mockImplementation((input) => {
    const url = requestUrl(input);
    if (url.includes("/api/auth/me")) {
      return Promise.resolve(buildResponse(200, { username: "izno" }));
    }
    return Promise.resolve(buildResponse(200, {}));
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
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
      await screen.findByRole("heading", { name: /tableau de bord/i }),
    ).toBeInTheDocument();
    // Shell chrome present: the top bar's user menu and the mobile nav.
    expect(
      screen.getByRole("button", { name: /menu utilisateur/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: /navigation principale/i }),
    ).toBeInTheDocument();
  });

  it("affiche le placeholder « À venir » (vague S2) sur « /pipeline »", async () => {
    renderAt("/pipeline");

    expect(await screen.findByText(/à venir/i)).toBeInTheDocument();
    expect(screen.getByText("S2")).toBeInTheDocument();
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
    // …inactive tabs do not.
    expect(
      within(bottomBar).getByRole("link", { name: "Tableau de bord" }),
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
    expect(await screen.findByText(/à venir/i)).toBeInTheDocument();
    expect(screen.getByText("S2")).toBeInTheDocument();
  });

  it("rejette un « ?redirect » protocol-relative et retombe sur « / »", async () => {
    renderAt("/login?redirect=//evil.example/pwned");

    // Open-redirect guard: `//evil` collapses to the app root (Dashboard).
    expect(
      await screen.findByRole("heading", { name: /tableau de bord/i }),
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
        screen.queryByRole("heading", { name: /tableau de bord/i }),
      ).not.toBeInTheDocument();
    });
  });
});
