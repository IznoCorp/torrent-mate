import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "@/App";

describe("App", () => {
  it("affiche l’écran « interface en construction »", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /interface en construction/i }),
    ).toBeInTheDocument();
  });
});
