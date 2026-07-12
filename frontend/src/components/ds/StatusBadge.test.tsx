import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/ds/StatusBadge";

describe("StatusBadge", () => {
  it("renders the label", () => {
    render(<StatusBadge tone="success" label="À jour" />);
    expect(screen.getByText("À jour")).toBeInTheDocument();
  });

  it("renders a leading dot by default", () => {
    const { container } = render(
      <StatusBadge tone="warning" label="En cours" />,
    );
    // The Badge renders a leading dot span (aria-hidden) when dot is true.
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument();
  });

  it("omits the dot when dot=false", () => {
    const { container } = render(
      <StatusBadge tone="neutral" label="Désactivé" dot={false} />,
    );
    expect(
      container.querySelector('[aria-hidden="true"]'),
    ).not.toBeInTheDocument();
  });
});
