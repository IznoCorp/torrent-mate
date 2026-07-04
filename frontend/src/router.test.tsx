import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { routes } from "@/router";

/**
 * Render the real route table at `path` via a fresh memory router, wrapped in a
 * retry-free Query provider (the shell's UserMenu reads the query client).
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
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
});

describe("router", () => {
  it("monte le shell et le tableau de bord sur « / »", async () => {
    renderAt("/");

    // Dashboard page rendered inside the shell.
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
});
