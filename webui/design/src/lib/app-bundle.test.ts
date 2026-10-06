// What the app build leaves out (`app-bundle.mjs`), on the real sources.
//
// WHAT MAKES THIS NON-VACUOUS. The leak check is read against the maquette's own
// sources — the mock seam, the harness's publisher, the frame stylesheet and the
// document — so a needle that stopped matching the layer it names fails here,
// and against the app's own stylesheets, so a needle that started matching the
// app fails too. What the app keeps is lifted from the real `harness.css`.
import { describe, expect, it } from "vitest";
import mockSeam from "../mocks/index.ts?raw";
import harnessPublisher from "../harness/drive.ts?raw";
import harnessPanel from "../harness/panel.ts?raw";
import documentSource from "../../index.html?raw";
import { findLeaks, isLeftOut, keptBlocks, leftOutModules, readSources } from "../../app-bundle.mjs";

// The stylesheets read from disk: the suite's CSS pipeline answers an empty
// string for a `?raw` stylesheet.
const [frameSheet, themeSheet, baseSheet] = readSources(
  new URL("../styles/", import.meta.url).pathname,
  ["harness.css", "theme.css", "base.css"],
).map((file) => file.text);

/** The `what` of every leak found in one text. */
function leaksIn(text: string): string[] {
  return findLeaks([{ name: "file", text }]).map((leak) => leak.what);
}

describe("findLeaks", () => {
  it("finds the mock layer in its own seam", () => {
    expect(leaksIn(mockSeam)).toEqual(
      expect.arrayContaining(["the mock layer's fetch seam", "the mock layer's window seam"]),
    );
  });

  it("finds the harness's hooks and parts in its own modules", () => {
    expect(leaksIn(harnessPublisher + harnessPanel)).toEqual(
      expect.arrayContaining([
        "the harness's named states",
        "the harness's measuring switch",
        "a harness part (data-part harness/...)",
      ]),
    );
  });

  it("finds the frame in its stylesheet and in the document", () => {
    expect(leaksIn(frameSheet)).toEqual(
      expect.arrayContaining(["the phone frame's way out", "a phone frame declaration"]),
    );
    expect(leaksIn(documentSource)).toEqual(
      expect.arrayContaining(["the phone frame's way out", "a harness part (data-part harness/...)"]),
    );
  });

  it("finds nothing in the app's own stylesheets, which name the switch inertly", () => {
    // Without their comments, as the build emits them: a comment may cite a
    // harness rule by its path, and none of it ships.
    const shipped = (themeSheet + baseSheet).replace(/\/\*[\s\S]*?\*\//g, "");
    expect(shipped).toContain("#desktop-switch:not(:checked)");
    expect(leaksIn(shipped)).toEqual([]);
  });

  it("finds nothing in the document once the harness region is cut", () => {
    const cut = documentSource.replace(/<!-- harness:start -->[\s\S]*?<!-- harness:end -->/g, "");
    expect(leaksIn(cut)).toEqual([]);
  });

  it("names the file each leak is in", () => {
    const found = findLeaks([
      { name: "clean.js", text: "export const app = 1;" },
      { name: "leaky.js", text: "window.__mocks = {};" },
    ]);
    expect(found).toEqual([{ file: "leaky.js", needle: "__mocks\\b", what: "the mock layer's window seam" }]);
  });
});

describe("leftOutModules", () => {
  it("keeps a left-out module only when it renders a byte", () => {
    const modules = {
      "/repo/webui/design/src/mocks/state.ts": { renderedLength: 0 },
      "/repo/webui/design/src/harness/drive.ts": { renderedLength: 12 },
      "/repo/webui/design/src/styles/harness.css": { renderedLength: 3 },
      "/repo/webui/design/src/app/shell.tsx": { renderedLength: 900 },
    };
    expect(leftOutModules(modules)).toEqual([
      "/repo/webui/design/src/harness/drive.ts",
      "/repo/webui/design/src/styles/harness.css",
    ]);
  });

  it("does not take a longer name for a left-out directory", () => {
    expect(isLeftOut("/repo/webui/design/src/lib/mocks-free.ts")).toBe(false);
    expect(isLeftOut("/repo/webui/design/src/mocks/index.ts")).toBe(true);
  });
});

describe("keptBlocks", () => {
  it("keeps the stage, the device and the notes' hidden default, and nothing scoped", () => {
    const kept = keptBlocks(frameSheet);
    expect(kept).toMatch(/^\.stage \{/);
    expect(kept).toContain("\n.device {");
    expect(kept).toContain("position: relative");
    expect(kept).toMatch(/\n\.note \{\n {2}display: none;/);
    expect(kept).not.toContain("desktop-switch");
    expect(kept).not.toContain("border-radius: 22px");
    expect(kept).not.toContain(":root.notes");
  });

  it("refuses a stylesheet without the device block", () => {
    expect(() => keptBlocks(".stage {\n  display: grid;\n}\n")).toThrow(/0 unscoped \.device blocks/);
  });
});
