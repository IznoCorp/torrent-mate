import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Switch } from "@/components/ui/switch";

afterEach(cleanup);

describe("Switch", () => {
  it("renders with role switch and correct aria-checked when off", () => {
    render(
      <Switch checked={false} onCheckedChange={vi.fn()} aria-label="Test" />,
    );
    const el = screen.getByRole("switch");
    expect(el).toBeInTheDocument();
    expect(el).toHaveAttribute("aria-checked", "false");
  });

  it("renders aria-checked true when on", () => {
    render(
      <Switch checked={true} onCheckedChange={vi.fn()} aria-label="Test" />,
    );
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("calls onCheckedChange with the negated value on click", () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onCheckedChange={onChange} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("applies the disabled attribute", () => {
    render(
      <Switch
        checked={false}
        onCheckedChange={vi.fn()}
        disabled
        aria-label="Test"
      />,
    );
    expect(screen.getByRole("switch")).toBeDisabled();
  });

  it("applies the success tone track class", () => {
    render(
      <Switch
        checked={true}
        onCheckedChange={vi.fn()}
        tone="success"
        aria-label="Test"
      />,
    );
    const track = screen.getByRole("switch").firstChild as HTMLElement;
    expect(track.className).toMatch(/success/);
  });

  it("respects aria-label", () => {
    render(
      <Switch
        checked={false}
        onCheckedChange={vi.fn()}
        aria-label="Activer le watcher"
      />,
    );
    expect(
      screen.getByRole("switch", { name: "Activer le watcher" }),
    ).toBeInTheDocument();
  });
});
