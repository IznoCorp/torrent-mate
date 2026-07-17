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

    const nav = screen.getByRole("navigation", {
      name: /navigation latérale/i,
    });
    expect(within(nav).getByText("Supervision")).toBeInTheDocument();
    expect(within(nav).getByText("Système")).toBeInTheDocument();
    expect(within(nav).getByText("Configuration")).toBeInTheDocument();
  });

  it("rend les destinations actives comme des liens", () => {
    renderSidebar();

    expect(screen.getByRole("link", { name: "Contrôle" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.getByRole("link", { name: "Pipeline" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Maintenance" }),
    ).toBeInTheDocument();
  });

  it("rend Config et Registre comme des liens actifs", () => {
    renderSidebar();

    // Config is an active link.
    expect(screen.getByRole("link", { name: "Config" })).toHaveAttribute(
      "href",
      "/config",
    );

    // Registre is now an active link (S6 shipped).
    expect(screen.getByRole("link", { name: "Registre" })).toHaveAttribute(
      "href",
      "/registry",
    );
  });

  it("marque la destination courante en actif (text-primary)", () => {
    renderSidebar("/pipeline");

    const pipeline = screen.getByRole("link", { name: "Pipeline" });
    expect(pipeline).toHaveAttribute("aria-current", "page");
    expect(pipeline.className).toContain("text-primary");
  });
});
