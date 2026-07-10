import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MediaCard } from "@/components/ds/MediaCard";

describe("MediaCard", () => {
  afterEach(cleanup);

  it("renders title, year and overview", () => {
    render(
      <MediaCard
        title="Dune"
        year={2021}
        overview="Paul Atreides sur Arrakis."
      />,
    );
    expect(screen.getByText("Dune")).toBeInTheDocument();
    expect(screen.getByText("2021")).toBeInTheDocument();
    expect(screen.getByText("Paul Atreides sur Arrakis.")).toBeInTheDocument();
  });

  it("fires onOpen when the card region is clicked", () => {
    const onOpen = vi.fn();
    render(<MediaCard title="Dune" onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("renders badges and footer slots", () => {
    render(
      <MediaCard
        title="Dune"
        badges={<span>tvdb 123</span>}
        footer={<button>Suivre</button>}
      />,
    );
    expect(screen.getByText("tvdb 123")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suivre" })).toBeInTheDocument();
  });
});
