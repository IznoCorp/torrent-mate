import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Kbd } from "@/components/ds/Kbd";

describe("Kbd", () => {
  it("renders its children inside a kbd element", () => {
    render(<Kbd>⏎</Kbd>);
    const el = screen.getByText("⏎");
    expect(el.tagName.toLowerCase()).toBe("kbd");
  });
});
