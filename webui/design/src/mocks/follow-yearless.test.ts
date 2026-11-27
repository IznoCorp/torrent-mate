// The dial a named state turns to show a follow nothing dates: the list serves `year: null` for that one follow.
import { afterEach, describe, expect, it } from "vitest";
import { mockDials, mockState, resetMockState } from "./state";

afterEach(resetMockState);

describe("setFollowYearless", () => {
  it("serves one follow with no year and leaves the others dated", () => {
    const title = mockState().follows[0].title;

    mockDials.setFollowYearless(title);

    const [yearless, ...others] = mockState().follows.map((follow) => follow.year);
    expect(yearless).toBeNull();
    expect(others.every((year) => year !== null)).toBe(true);
  });

  it("is lifted by the next reset to the seed", () => {
    mockDials.setFollowYearless(mockState().follows[0].title);
    resetMockState();

    expect(mockState().follows.every((follow) => follow.year !== null)).toBe(true);
  });
});
