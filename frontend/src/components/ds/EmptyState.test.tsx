import { render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "@/components/ds/EmptyState";

describe("EmptyState", () => {
  it("renders the title", () => {
    render(<EmptyState title="Aucun média" />);
    expect(screen.getByText("Aucun média")).toBeInTheDocument();
  });

  it("renders the description and action when given", () => {
    render(
      <EmptyState
        title="Aucun média"
        description="Rien à afficher pour le moment"
        action={<button>Actualiser</button>}
      />,
    );
    expect(
      screen.getByText("Rien à afficher pour le moment"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Actualiser" }),
    ).toBeInTheDocument();
  });

  it("renders the icon when provided", () => {
    const { container } = render(<EmptyState icon={Inbox} title="Vide" />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
