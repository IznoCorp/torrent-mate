// The application is served under a Content-Security-Policy without
// `'unsafe-inline'`: a markup string carrying `style="…"`, or a script that sets
// the attribute, is dropped by the browser and the element is drawn unstyled.
// (React's `style={{…}}` and `element.style.x = …` go through the CSSOM, which the
// policy allows.) This reads the sources, because nothing else would notice.
import { describe, expect, it } from "vitest";
import document from "../../index.html?raw";

const SOURCES = import.meta.glob<string>(
  ["../**/*.ts", "../**/*.tsx", "../**/*.css", "!../**/*.test.ts", "!../**/*.test.tsx"],
  { query: "?raw", import: "default", eager: true },
);

describe("what a policy without 'unsafe-inline' would drop", () => {
  const files = Object.keys(SOURCES);

  it("finds the sources it reads", () => {
    expect(files.length).toBeGreaterThan(100);
  });

  it("has no inline style attribute in any markup string", () => {
    const offenders = files.filter((file) => /\sstyle=["']|setAttribute\(\s*["']style["']/.test(SOURCES[file]));
    expect(offenders).toEqual([]);
  });

  it("inlines no `data:` URL in a stylesheet", () => {
    const offenders = files
      .filter((file) => file.endsWith(".css"))
      .filter((file) => /url\(\s*["']?data:/.test(SOURCES[file]));
    expect(offenders).toEqual([]);
  });

  it("names every script of the document as a file", () => {
    const markup = document.replace(/<!--[\s\S]*?-->/g, "");
    const inline = [...markup.matchAll(/<script(?![^>]*\bsrc=)[^>]*>/g)];
    expect(inline).toEqual([]);
  });
});
