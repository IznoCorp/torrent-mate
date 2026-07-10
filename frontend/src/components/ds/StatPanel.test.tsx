import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatPanel } from "@/components/ds/StatPanel";

describe("StatPanel", () => {
  it("renders label, value, unit and the trend delta", () => {
    const { container } = render(
      <StatPanel
        label="Bibliothèque"
        value="1 909"
        unit="items"
        delta="+12 / 24h"
        deltaDir="up"
      />,
    );

    expect(screen.getByText("Bibliothèque")).toBeInTheDocument();
    expect(screen.getByText("1 909")).toBeInTheDocument();
    expect(screen.getByText("items")).toBeInTheDocument();
    expect(screen.getByText("+12 / 24h")).toBeInTheDocument();
    expect(container.querySelector(".ps-stat__delta--up")).not.toBeNull();
  });

  it("renders a wrapping secondary line below the value", () => {
    const { container } = render(
      <StatPanel
        label="Items"
        value="1 837"
        secondary="245 films / 90 séries"
      />,
    );

    const sub = container.querySelector(".ps-stat__sub");
    expect(sub).not.toBeNull();
    expect(sub).toHaveTextContent("245 films / 90 séries");
    // The secondary line must NOT be nested inside the headline value span
    // (that inline placement is what caused the desktop overlap).
    expect(container.querySelector(".ps-stat__value .ps-stat__sub")).toBeNull();
  });
});
