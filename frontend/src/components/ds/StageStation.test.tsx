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

  it("shows an error pastille when blocked with a non-zero count", () => {
    render(
      <StageStation label="Scraping" count={4} state="blocked" blocked={2} />,
    );
    expect(screen.getByText(/2 erreurs/)).toBeInTheDocument();
  });

  it("surfaces a temporal caption", () => {
    render(
      <StageStation
        label="Scraping"
        count={4}
        state="ok"
        timeframe="dernier run"
      />,
    );
    expect(screen.getByText("dernier run")).toBeInTheDocument();
  });

  it("exposes a dialog-opening a11y label when clickable (C20)", () => {
    render(
      <StageStation
        label="Matching"
        count={3}
        state="attention"
        onClick={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-haspopup", "dialog");
    expect(btn.getAttribute("aria-label")).toContain("Matching");
  });
});
