import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StageStation } from "@/components/ds/StageStation";

describe("StageStation", () => {
  afterEach(cleanup);

  it("renders the label and count", () => {
    render(<StageStation label="Matching" count={7} state="attention" />);
    expect(screen.getByText("Matching")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("renders split sub-counts", () => {
    render(
      <StageStation
        label="Matching"
        count={7}
        state="attention"
        split={[
          { label: "ambigu", count: 3, tone: "warning" },
          { label: "sans match", count: 1, tone: "danger" },
        ]}
      />,
    );
    expect(screen.getByText("ambigu")).toBeInTheDocument();
    expect(screen.getByText("sans match")).toBeInTheDocument();
  });

  it("fires onClick when clicked", () => {
    const onClick = vi.fn();
    render(
      <StageStation label="Dispatch" count={2} state="ok" onClick={onClick} />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
