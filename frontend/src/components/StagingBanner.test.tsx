import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StagingBanner } from "@/components/StagingBanner";

vi.mock("@/lib/env", () => ({
  isStaging: vi.fn(),
}));

import { isStaging } from "@/lib/env";

const mockedIsStaging = vi.mocked(isStaging);

describe("StagingBanner", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders the unmissable staging badge on staging", () => {
    mockedIsStaging.mockReturnValue(true);
    render(<StagingBanner />);
    expect(screen.getByText(/STAGING/)).toBeInTheDocument();
  });

  it("renders nothing in production (byte-for-byte unchanged prod UI)", () => {
    mockedIsStaging.mockReturnValue(false);
    const { container } = render(<StagingBanner />);
    expect(container).toBeEmptyDOMElement();
  });
});
