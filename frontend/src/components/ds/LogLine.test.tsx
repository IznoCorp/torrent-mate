import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LogLine } from "@/components/ds/LogLine";

describe("LogLine", () => {
  it("renders the level short code, timestamp and message", () => {
    const { container } = render(
      <LogLine level="error" time="12:00:00">
        Échec du scrape
      </LogLine>,
    );

    expect(screen.getByText("ERR")).toBeInTheDocument();
    expect(screen.getByText("12:00:00")).toBeInTheDocument();
    expect(screen.getByText("Échec du scrape")).toBeInTheDocument();
    expect(container.querySelector(".ps-log--error")).not.toBeNull();
  });
});
