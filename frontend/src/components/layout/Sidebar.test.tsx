import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { Sidebar } from "@/components/layout/Sidebar";

afterEach(() => {
  cleanup();
});

/** Render the sidebar behind the router context its `NavLink`s require. */
function renderSidebar(initialPath = "/"): void {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Sidebar />
    </MemoryRouter>,
  );
}

describe("Sidebar", () => {
  it("rend les trois micro-libellés de section", () => {
    renderSidebar();

    const nav = screen.getByRole("navigation", { name: /navigation latérale/i });
    expect(within(nav).getByText("Supervision")).toBeInTheDocument();
    expect(within(nav).getByText("Système")).toBeInTheDocument();
    expect(within(nav).getByText("Configuration")).toBeInTheDocument();
  });

  it("rend les destinations actives comme des liens", () => {
    renderSidebar();

    expect(
      screen.getByRole("link", { name: "Tableau de bord" }),
    ).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Pipeline" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Maintenance" })).toBeInTheDocument();
  });

  it("rend Registre (S6) et Config (S4) désactivés, jamais des liens", () => {
    renderSidebar();

    // The disabled stubs are non-interactive rows, not links.
    expect(
      screen.queryByRole("link", { name: /Registre/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /Config/ }),
    ).not.toBeInTheDocument();

    const registre = screen.getByText("Registre").closest("[aria-disabled]");
    expect(registre).toHaveAttribute("aria-disabled", "true");
    expect(within(registre as HTMLElement).getByText("S6")).toBeInTheDocument();

    const config = screen.getByText("Config").closest("[aria-disabled]");
    expect(config).toHaveAttribute("aria-disabled", "true");
    expect(within(config as HTMLElement).getByText("S4")).toBeInTheDocument();
  });

  it("marque la destination courante en actif (text-primary)", () => {
    renderSidebar("/pipeline");

    const pipeline = screen.getByRole("link", { name: "Pipeline" });
    expect(pipeline).toHaveAttribute("aria-current", "page");
    expect(pipeline.className).toContain("text-primary");
  });
});
