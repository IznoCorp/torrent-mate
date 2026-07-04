import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "@/App";

afterEach(() => {
  cleanup();
});

describe("App", () => {
  it("monte le shell et rend le tableau de bord à la racine", async () => {
    render(<App />);

    // The browser router boots at jsdom's default path ("/") → Dashboard + shell.
    expect(
      await screen.findByRole("heading", { name: /tableau de bord/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /menu utilisateur/i }),
    ).toBeInTheDocument();
  });
});
