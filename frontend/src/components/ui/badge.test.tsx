import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Badge } from "@/components/ui/badge";

afterEach(cleanup);

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>error</Badge>);
    expect(screen.getByText("error")).toBeInTheDocument();
  });

  it("applies the tone variant class", () => {
    render(<Badge tone="danger">error</Badge>);
    // The danger tone drives the --danger token colour via an arbitrary util.
    expect(screen.getByText("error").className).toMatch(/danger/);
  });

  it("renders a leading dot when dot is set", () => {
    const { container } = render(
      <Badge tone="success" dot>
        seeding
      </Badge>,
    );
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });
});
