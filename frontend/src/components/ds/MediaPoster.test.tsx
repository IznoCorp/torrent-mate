import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MediaPoster } from "@/components/ds/MediaPoster";

describe("MediaPoster", () => {
  afterEach(cleanup);

  it("renders an img when a src is given", () => {
    render(<MediaPoster title="Dune" src="https://img/x.jpg" />);
    const img = screen.getByRole("img", { name: "Dune" });
    expect(img).toHaveAttribute("src", "https://img/x.jpg");
    expect(img).toHaveAttribute("loading", "lazy");
  });

  it("falls back to initials when no src", () => {
    render(<MediaPoster title="Top Chef" />);
    expect(screen.getByText("TC")).toBeInTheDocument();
  });

  it("falls back to initials when the image errors", () => {
    render(<MediaPoster title="Rick and Morty" src="https://img/broken.jpg" />);
    fireEvent.error(screen.getByRole("img", { name: "Rick and Morty" }));
    expect(screen.getByText("RA")).toBeInTheDocument();
  });

  it("renders the kind chip", () => {
    render(<MediaPoster title="Dune" kind="movie" />);
    expect(screen.getByText("Film")).toBeInTheDocument();
  });
});
