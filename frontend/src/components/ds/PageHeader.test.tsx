import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader } from "@/components/ds/PageHeader";

describe("PageHeader", () => {
  it("renders the title as a heading", () => {
    render(<PageHeader title="Pipeline" />);
    expect(
      screen.getByRole("heading", { name: "Pipeline" }),
    ).toBeInTheDocument();
  });

  it("renders the description when given", () => {
    render(<PageHeader title="Pipeline" description="Flux en direct" />);
    expect(screen.getByText("Flux en direct")).toBeInTheDocument();
  });

  it("renders the actions node", () => {
    render(<PageHeader title="Pipeline" actions={<button>Lancer</button>} />);
    expect(screen.getByRole("button", { name: "Lancer" })).toBeInTheDocument();
  });
});
