import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { NavCountBadge } from "@/components/ds/NavCountBadge";

describe("NavCountBadge", () => {
  afterEach(cleanup);

  it("renders nothing at zero or below", () => {
    const { container } = render(<NavCountBadge count={0} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the count with an accessible label", () => {
    render(<NavCountBadge count={3} />);
    const badge = screen.getByText("3");
    expect(badge).toHaveAttribute("data-slot", "nav-count");
    expect(badge).toHaveAttribute("aria-label", "3 en attente");
  });

  it("is a solid high-contrast pill — PRIMARY, per the maquette (amber counts)", () => {
    // Pending work is attention, not failure: the maquette paints every nav
    // count with the primary amber; the danger tone stays reserved for the
    // « ? » unknown state, which IS a failure to know.
    render(<NavCountBadge count={1} />);
    const cls = screen.getByText("1").className;
    expect(cls).toContain("bg-primary");
    expect(cls).toContain("text-primary-foreground");
    expect(cls).not.toContain("bg-danger");
  });

  it("caps large counts at 99+", () => {
    render(<NavCountBadge count={250} />);
    expect(screen.getByText("99+")).toBeInTheDocument();
  });
});
