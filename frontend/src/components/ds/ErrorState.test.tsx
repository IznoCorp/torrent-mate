import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ErrorState } from "@/components/ds/ErrorState";

describe("ErrorState", () => {
  afterEach(cleanup);

  it("renders an alert with the default title", () => {
    render(<ErrorState />);
    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText("Une erreur est survenue")).toBeInTheDocument();
  });

  it("renders the detail message", () => {
    render(<ErrorState message="502 Bad Gateway" />);
    expect(screen.getByText("502 Bad Gateway")).toBeInTheDocument();
  });

  it("calls onRetry when the retry button is clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("does not render a retry button without onRetry", () => {
    render(<ErrorState />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
