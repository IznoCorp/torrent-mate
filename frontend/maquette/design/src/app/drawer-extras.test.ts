// The drawer owns no maquette control: the harness contributes its group through
// `drawer-extras.ts`, and a build without the harness draws the product's drawer.
//
// WHAT MAKES THIS NON-VACUOUS. The first test reads the registry as the drawer
// does, with nothing contributed; the second and third prove the seam is live
// (a contribution appears, and its disposal takes it away), so « empty » is a
// fact about this build and not about a seam that never carries anything; the
// last reads every module of the frame and fails on one that reaches into
// `harness/`, which is how the group would end up shipped with the app.
import { afterEach, describe, expect, it } from "vitest";
import { contributeDrawerGroup, drawerExtraGroups } from "./drawer-extras";

const group = {
  part: "test/group",
  title: () => "t",
  entries: [{ id: "x", icon: "", label: () => "x", onPress: () => undefined }],
};

const SOURCES = import.meta.glob<string>(["./**/*.ts", "./**/*.tsx", "!./**/*.test.ts", "!./**/*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
});

describe("the drawer's extra groups", () => {
  const disposers: (() => void)[] = [];
  afterEach(() => disposers.splice(0).forEach((dispose) => dispose()));

  it("are none when the harness is not loaded", () => {
    expect(drawerExtraGroups()).toEqual([]);
  });

  it("carry a contribution, and lose it when it is taken away", () => {
    const dispose = contributeDrawerGroup(group);
    disposers.push(dispose);
    expect(drawerExtraGroups()).toEqual([group]);
    dispose();
    expect(drawerExtraGroups()).toEqual([]);
  });

  it("are never imported from the harness by the frame", () => {
    const reaching = Object.entries(SOURCES)
      .filter(([, source]) => /from\s+"(\.\.\/)+harness\//.test(source))
      .map(([path]) => path);
    expect(reaching).toEqual([]);
  });
});
