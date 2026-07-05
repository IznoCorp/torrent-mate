import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusDot } from "@/components/ds/StatusDot";

describe("StatusDot", () => {
  it("renders the default status label and the status modifier class", () => {
    const { container } = render(<StatusDot status="running" />);

    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(container.querySelector(".ps-dot--running")).not.toBeNull();
  });

  it("honours a custom label and hides text when showLabel is false", () => {
    const { container } = render(
      <StatusDot status="done" label="Terminé" showLabel={false} />,
    );

    expect(screen.queryByText("Terminé")).toBeNull();
    expect(container.querySelector(".ps-dot__d")).not.toBeNull();
  });
});
