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
});
