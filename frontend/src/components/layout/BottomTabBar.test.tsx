import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { BottomTabBar } from "@/components/layout/BottomTabBar";

afterEach(() => {
  cleanup();
});

/** Render the bottom tab bar behind the router context its `NavLink`s require. */
function renderBottomBar(initialPath = "/pipeline"): void {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <BottomTabBar />
    </MemoryRouter>,
  );
}

describe("BottomTabBar", () => {
  it("rend exactement Pipeline · Scraping · Acquisition · Maintenance", () => {
    renderBottomBar();

    const nav = screen.getByRole("navigation", {
      name: /navigation principale/i,
    });
    const links = within(nav).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual([
      "Pipeline",
      "Scraping",
      "Acquisition",
      "Maintenance",
    ]);
  });

  it("n'inclut ni le tableau de bord ni les stubs désactivés", () => {
    renderBottomBar();

    expect(
      screen.queryByRole("link", { name: "Tableau de bord" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Registre" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Config" }),
    ).not.toBeInTheDocument();
  });

  it("marque l'onglet courant via aria-current et text-primary", () => {
    renderBottomBar("/pipeline");

    const pipeline = screen.getByRole("link", { name: "Pipeline" });
    expect(pipeline).toHaveAttribute("aria-current", "page");
    expect(pipeline.className).toContain("text-primary");
  });
});
